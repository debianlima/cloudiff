import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
MODPATH=ROOT/'components/control-plane/usr/local/sbin/cloudif-project-backup.py'
spec=importlib.util.spec_from_file_location('cloudif_project_backup_test',MODPATH)
mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod)

class ProjectBackupSleepingTenantTests(unittest.TestCase):
    def test_sleeping_tenant_db_is_started_waited_and_restored(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); tenant='iff0001-testesofa'; tdir=root/tenant; tdir.mkdir(); (tdir/'.env').write_text('POSTGRES_USER=postgres\n'); (tdir/'docker-compose.yml').write_text('services:\n  db:\n    image: postgres\n')
            old=mod.TENANTS; mod.TENANTS=root
            calls=[]
            def co(cmd, text=True, **kw):
                calls.append(tuple(cmd))
                if cmd[-3:]==['ps','-q','db']:
                    # before `up`: no running cid; after `up`: return cid
                    return 'cid123\n' if any(c[-3:]==('up','-d','db') for c in calls) else ''
                if cmd[:4]==['docker','inspect','-f','{{.Name}}']:
                    return '/cloudif_iff0001-testesofa-db-1\n'
                if cmd[:4]==['docker','inspect','-f','{{.State.Running}}']:
                    return 'false\n'
                raise AssertionError(cmd)
            def run(cmd, **kw):
                calls.append(tuple(cmd))
                if cmd[:2]==['docker','exec']:
                    return mock.Mock(returncode=0)
                return mock.Mock(returncode=0)
            try:
                with mock.patch.object(mod.subprocess,'check_output',side_effect=co), mock.patch.object(mod.subprocess,'run',side_effect=run):
                    name,restore=mod.project_db_runtime(tenant)
                self.assertEqual(name,'cloudif_iff0001-testesofa-db-1')
                self.assertTrue(restore and restore[-2:]==['stop','db'])
                self.assertTrue(any(c[-3:]==('up','-d','db') for c in calls))
                self.assertTrue(any(c[:2]==('docker','exec') for c in calls))
            finally: mod.TENANTS=old

    def test_make_database_restores_db_state_in_finally(self):
        source=MODPATH.read_text()
        block=source[source.index('def make_database'):source.index('def remote_publication_metadata')]
        self.assertIn('c,restore=project_db_runtime(tenant)',block)
        self.assertIn('if restore: subprocess.run(restore',block)

if __name__=='__main__':unittest.main()
