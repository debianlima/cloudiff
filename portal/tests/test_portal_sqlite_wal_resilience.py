from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
LEGACY=ROOT/'portal/legacy/cloudif-admin-portal-base.py'
DELETE=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


def load_delete_module():
    stub=types.ModuleType('cloudif_delete_git_komodo_action')
    stub.forja_rollback=lambda *args,**kwargs:{'ok':True}
    sys.modules['cloudif_delete_git_komodo_action']=stub
    spec=importlib.util.spec_from_file_location('delete_backup_wal_test',DELETE)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


class PortalSQLiteWalResilienceTests(unittest.TestCase):
    def test_portal_keeps_process_lifetime_anchor(self):
        for path in (BASE,LEGACY):
            source=path.read_text()
            for marker in (
                '_DB_ANCHOR = None',
                '_DB_ANCHOR_LOCK = threading.Lock()',
                'def _ensure_db_anchor():',
                'check_same_thread=False',
                "connection.execute('PRAGMA journal_mode=WAL')",
                "connection.execute('PRAGMA busy_timeout=30000')",
                'atexit.register(_close_db_anchor)',
                '_ensure_db_anchor()\n\n\ndef init_db():',
                'sqlite3.connect(DB, timeout=30)',
            ):
                self.assertIn(marker,source)

    def test_open_anchor_prevents_wal_and_shm_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            db=Path(temporary)/'portal.db'
            setup=sqlite3.connect(db);setup.execute('pragma journal_mode=wal');setup.execute('create table items(id integer)');setup.commit();setup.close()
            anchor=sqlite3.connect(db,check_same_thread=False);anchor.execute('pragma journal_mode=wal');anchor.execute('select 1')
            for value in range(4):
                connection=sqlite3.connect(db);connection.execute('insert into items values(?)',(value,));connection.commit();connection.close()
            self.assertTrue(Path(str(db)+'-wal').exists())
            self.assertTrue(Path(str(db)+'-shm').exists())
            anchor.close()
            self.assertFalse(Path(str(db)+'-wal').exists())
            self.assertFalse(Path(str(db)+'-shm').exists())

    def test_sqlite_backup_contains_uncheckpointed_wal_rows(self):
        module=load_delete_module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'live.db';destination=root/'audit.db'
            anchor=sqlite3.connect(source,check_same_thread=False)
            anchor.execute('pragma journal_mode=wal');anchor.execute('pragma wal_autocheckpoint=0')
            anchor.execute('create table records(value text)');anchor.commit()
            writer=sqlite3.connect(source);writer.execute('pragma wal_autocheckpoint=0');writer.execute("insert into records values('from-wal')");writer.commit();writer.close()
            self.assertTrue(Path(str(source)+'-wal').exists())
            module._backup_if_exists(source,destination)
            copied=sqlite3.connect(destination)
            self.assertEqual(copied.execute('select value from records').fetchall(),[('from-wal',)])
            self.assertEqual(copied.execute('pragma quick_check').fetchone()[0],'ok')
            copied.close();anchor.close()
            self.assertEqual(destination.stat().st_mode & 0o777,0o600)

    def test_non_database_backup_remains_byte_identical(self):
        module=load_delete_module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'secret.json';destination=root/'copy.json'
            payload={'safe':'value'};source.write_text(json.dumps(payload),encoding='utf-8')
            module._backup_if_exists(source,destination)
            self.assertEqual(destination.read_bytes(),source.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777,0o600)

    def test_database_errors_return_controlled_503(self):
        source=COEXIST.read_text()
        self.assertIn('import sqlite3',source)
        start=source.index('except sqlite3.Error:')
        end=source.index('except Exception:',start)
        block=source[start:end]
        self.assertIn("return send(self, 503",block)
        self.assertIn("('Retry-After', '3')",block)
        self.assertIn('Portal temporariamente ocupado',block)
        self.assertNotIn('previous_get(self)',block)

    def test_sqlite_audit_does_not_use_raw_copy(self):
        source=DELETE.read_text()
        start=source.index('def _backup_if_exists')
        end=source.index('def _delete_agent_identity',start)
        block=source[start:end]
        self.assertIn('source_connection.backup(destination_connection',block)
        self.assertIn("source.suffix.lower() in {'.db','.sqlite','.sqlite3'}",block)
        self.assertIn('shutil.copy2(source,destination)',block)


if __name__=='__main__':unittest.main()
