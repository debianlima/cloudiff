import importlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'


class ProjectCheckActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.db_path=cls.root/'portal.db'
        cls.provision_root=cls.root/'provisioning'/'projects'
        cls.provision_root.mkdir(parents=True)
        sys.path.insert(0,str(LIB))
        cls.safe=importlib.import_module('cloudif_project_action_safe')
        cls.status=importlib.import_module('cloudif_project_provision_status')
        cls.old_safe_db=cls.safe.DB
        cls.old_status_db=cls.status.DB
        cls.old_status_root=cls.status.PROVISION_ROOT
        cls.safe.DB=str(cls.db_path)
        cls.status.DB=cls.db_path
        cls.status.PROVISION_ROOT=cls.provision_root

    @classmethod
    def tearDownClass(cls):
        cls.safe.DB=cls.old_safe_db
        cls.status.DB=cls.old_status_db
        cls.status.PROVISION_ROOT=cls.old_status_root
        if str(LIB) in sys.path:sys.path.remove(str(LIB))
        cls.tmp.cleanup()

    def setUp(self):
        if self.db_path.exists():self.db_path.unlink()
        with sqlite3.connect(self.db_path) as con:
            con.executescript('''
            CREATE TABLE projects(
              slug TEXT PRIMARY KEY,
              name TEXT,
              tenant TEXT,
              owner TEXT,
              description TEXT,
              repo_url TEXT,
              komodo_status TEXT,
              updated_at TEXT
            );
            INSERT INTO projects(slug,name,tenant,owner,description,repo_url,komodo_status,updated_at)
            VALUES('demo','Demo','alice-db','alice','descricao-original','https://old.invalid/demo.git','stale','2026-08-27T20:00:00Z');
            ''')
            con.commit()
        project_root=self.provision_root/'demo'
        project_root.mkdir(parents=True,exist_ok=True)
        (project_root/'provision-report.json').write_text('''{
          "ok": false,
          "finished_at": "2026-08-27T23:40:00Z",
          "components": {
            "forgejo": {"ok": true, "status": "ready", "url": "https://git.example.invalid/alice/demo"},
            "komodo": {"ok": true, "status": "running"},
            "supabase": {"ok": false, "status": "degraded"}
          }
        }''',encoding='utf-8')
        (project_root/'managed-runtime.json').write_text('''{
          "runtime_template":"node22","php_version":"8.3","layout":"managed-root-v1"
        }''',encoding='utf-8')
        (project_root/'template-applied.json').write_text('''{
          "runtime_template":"node22","php_version":"8.3","runtime_layout":"managed-root-v1","template_kind":"links"
        }''',encoding='utf-8')

    def _row(self):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row
            return dict(con.execute('SELECT * FROM projects WHERE slug=?',('demo',)).fetchone())

    def test_check_observes_repository_database_and_container_without_configuration_mutation(self):
        before=self._row()
        result=self.safe.check_project({'slug':['demo']},{})
        after=self._row()

        self.assertTrue(result['checked'])
        self.assertEqual(result['slug'],'demo')
        self.assertEqual(result['tenant'],'alice-db')
        self.assertEqual(result['observed'],{
            'repository':{'ok':True,'status':'ready'},
            'database':{'ok':False,'status':'degraded'},
            'container':{'ok':True,'status':'running'},
        })
        self.assertFalse(result['all_ok'])
        self.assertEqual(after['repo_url'],'https://git.example.invalid/alice/demo')
        self.assertEqual(after['komodo_status'],'running')
        self.assertNotEqual(after['updated_at'],before['updated_at'])
        # Check is observational: project configuration must not be rewritten.
        self.assertEqual(after['name'],before['name'])
        self.assertEqual(after['tenant'],before['tenant'])
        self.assertEqual(after['owner'],before['owner'])
        self.assertEqual(after['description'],before['description'])

    def test_check_without_report_preserves_known_links_and_reports_unknown_observation(self):
        root=self.provision_root/'demo'
        for name in ('provision-report.json','managed-runtime.json','template-applied.json'):
            try:(root/name).unlink()
            except FileNotFoundError:pass
        before=self._row()
        result=self.safe.check_project({'slug':['demo']},{})
        after=self._row()
        self.assertEqual(result['observed'],{
            'repository':{'ok':False,'status':'pending'},
            'database':{'ok':False,'status':'pending'},
            'container':{'ok':False,'status':'pending'},
        })
        self.assertFalse(result['all_ok'])
        self.assertEqual(after['repo_url'],before['repo_url'])
        self.assertEqual(after['komodo_status'],before['komodo_status'])


if __name__=='__main__':unittest.main()
