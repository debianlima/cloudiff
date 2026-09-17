from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from portal.core.auth import Identity
from portal.modules.taiga import service, views
from portal.modules.projects import service as projects_service

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "portal/ui/shell.py"
WIRING = ROOT / "portal/wiring.py"
COEXIST = ROOT / "components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py"
PROJECTS = ROOT / "portal/modules/projects/service.py"


class TaigaModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "portal.db"
        con = sqlite3.connect(self.db)
        con.executescript("""
        create table projects(slug text primary key,name text,tenant text,owner text,description text,repo_url text,komodo_status text,status text,updated_at text,repo_name text,stack_name text);
        create table project_acl(slug text,subject_type text,subject text);
        create table tenant_acl(tenant text,subject_type text,subject text);
        create table node_metrics_cache(node text,ok integer,payload text,updated_at text);
        insert into projects values('alpha','Alpha','','alice','Projeto Alpha','','ok','active','2026-09-17T10:00:00Z','','');
        insert into projects values('beta','Beta','','bob','Projeto Beta','','ok','active','2026-09-17T10:00:00Z','','');
        insert into project_acl values('beta','user','prof');
        """)
        payload = {"hostname":"faro","memory":{"used":10,"total":100},"network":{"rx_bps":1,"tx_bps":2},"docker":{"containers":[{"name":"taiga-current-taiga-back-1","image":"cloudif-local/taiga-back-oidc","status":"Up 2 days"},{"name":"other","image":"x","status":"Up"}]}}
        con.execute("insert into node_metrics_cache values(?,?,?,?)", ("faro", 1, json.dumps(payload), "2026-09-17T12:00:00Z"))
        con.commit(); con.close()
        self.old_db = service._DB
        self.old_projects_db = projects_service._DB
        self.old_audit = service._AUDIT_TOKEN
        self.old_forja = service._FORJA_ENV
        self.old_taiga_token = service._TAIGA_TOKEN
        service._DB = str(self.db)
        projects_service._DB = str(self.db)
        service._AUDIT_TOKEN = "audit"
        service._TAIGA_TOKEN = ""
        env = Path(self.temp.name) / "forja.env"
        env.write_text("FORJA_AGENT_URL=http://forja.invalid\nFORJA_AGENT_TOKEN=forja\n")
        service._FORJA_ENV = str(env)
        self.calls = []
        self.old_http = service._http_json

        def fake_http(url, *, headers=None, timeout=4.0):
            self.calls.append((url, headers or {}))
            if url.endswith('/api/v1/'):
                return 200, {"projects":"/api/v1/projects"}
            if '/v1/events?' in url:
                q = parse_qs(urlsplit(url).query)
                subject = (q.get('subject') or [''])[0]
                events = [
                    {"ts":"2026-09-17T11:00:00Z","actor_id":"alice","delegated_user_id":"","source":"forgejo","action":"commit","result":"success","duration_ms":0,"attrs":{"sha":"abc","auth_token":"never"}},
                    {"ts":"2026-09-17T11:01:00Z","actor_id":"bob","delegated_user_id":"","source":"forgejo","action":"commit","result":"success","duration_ms":0,"attrs":{"sha":"def"}},
                ]
                if subject:
                    events = [event for event in events if event['actor_id'] == subject]
                return 200, {"ok":True,"events":events}
            if '/project/status?' in url:
                return 200, {"ok":True,"project":{"last_forgejo_automation_at":"2026-09-17T11:02:00Z","last_forgejo_automation_status":"completed","last_forgejo_automation_ok":True,"last_forgejo_automation_commit":"abc","forgejo":{"url":"https://cloudiff.duckdns.org/git/alice/cloudif-alpha.git"}}}
            return 503, {"ok":False}
        service._http_json = fake_http

    def tearDown(self):
        service._DB = self.old_db
        projects_service._DB = self.old_projects_db
        service._AUDIT_TOKEN = self.old_audit
        service._FORJA_ENV = self.old_forja
        service._TAIGA_TOKEN = self.old_taiga_token
        service._http_json = self.old_http
        self.temp.cleanup()

    def test_student_sees_only_visible_project_and_own_activity(self):
        identity = Identity('alice','alice@example.invalid',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertEqual([p['slug'] for p in data['projects']], ['alpha'])
        self.assertFalse(data['can_view_members'])
        self.assertEqual([e['actor_id'] for e in data['activity']], ['alice'])
        audit_url = next(url for url,_headers in self.calls if '/v1/events?' in url)
        self.assertEqual(parse_qs(urlsplit(audit_url).query)['subject'], ['alice'])
        self.assertNotIn('auth_token', json.dumps(data))

    def test_professor_with_acl_sees_project_member_summary(self):
        identity = Identity('prof','prof@example.invalid',frozenset({'CloudIF-Professor'}))
        data = service.taiga_data(identity, 'beta')
        self.assertEqual([p['slug'] for p in data['projects']], ['beta'])
        self.assertTrue(data['can_view_members'])
        self.assertEqual({x['username'] for x in data['actors']}, {'alice','bob'})
        audit_url = next(url for url,_headers in self.calls if '/v1/events?' in url)
        self.assertNotIn('subject', parse_qs(urlsplit(audit_url).query))

    def test_faro_telemetry_is_filtered_to_taiga_containers(self):
        identity = Identity('alice','',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertEqual(len(data['faro']['containers']), 1)
        self.assertIn('taiga-back', data['faro']['containers'][0]['image'])

    def test_private_taiga_degrades_without_server_credential(self):
        identity = Identity('alice','',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertFalse(data['taiga_project']['configured'])
        self.assertEqual(data['taiga_project']['error'], 'taiga_service_credential_unconfigured')
        markup = views.taiga_body(data)
        self.assertIn('Credencial server-side pendente', markup)
        self.assertIn('Atividade do projeto', markup)

    def test_navigation_adds_taiga_without_replacing_projects(self):
        shell = SHELL.read_text()
        self.assertIn('(\"projetos\", \"Projetos\")', shell)
        self.assertIn('(\"taiga\", \"Taiga\")', shell)
        self.assertLess(shell.index('(\"projetos\", \"Projetos\")'), shell.index('(\"taiga\", \"Taiga\")'))
        self.assertIn('projects, taiga, overview', WIRING.read_text())
        coexist = COEXIST.read_text()
        self.assertIn('native_taiga', coexist)
        self.assertIn('/cloudiff/portal/pagina/taiga', coexist)

    def test_projects_module_was_not_extended_with_taiga_logic(self):
        self.assertNotIn('taiga', PROJECTS.read_text().lower())


if __name__ == '__main__':
    unittest.main()
