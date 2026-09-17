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
        self.old_taiga_reconciler_env = service._TAIGA_RECONCILER_ENV
        service._DB = str(self.db)
        projects_service._DB = str(self.db)
        service._AUDIT_TOKEN = "audit"
        reconciler_env = Path(self.temp.name) / "taiga-reconciler-client.env"
        reconciler_env.write_text("TAIGA_RECONCILER_URL=http://faro.invalid:19010\nTAIGA_RECONCILER_TOKEN=reconciler\n")
        service._TAIGA_RECONCILER_ENV = str(reconciler_env)
        env = Path(self.temp.name) / "forja.env"
        env.write_text("FORJA_AGENT_URL=http://forja.invalid\nFORJA_AGENT_TOKEN=forja\n")
        service._FORJA_ENV = str(env)
        self.calls = []
        self.post_calls = []
        self.old_http = service._http_json
        self.old_http_post = service._http_json_post

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
            if '/v1/projects/' in url and '/summary?' in url:
                q = parse_qs(urlsplit(url).query)
                subject = (q.get('subject') or [''])[0]
                include_members = (q.get('include_members') or ['0'])[0] == '1'
                members = [
                    {"username":"alice","full_name":"Alice","role":"Membro CloudIFF","tasks_assigned":3,"tasks_closed":2,"stories_assigned":2,"stories_closed":1,"history_events":4,"last_login":"2026-09-17T10:00:00Z","last_activity":"2026-09-17T11:00:00Z"},
                    {"username":"bob","full_name":"Bob","role":"Membro CloudIFF","tasks_assigned":1,"tasks_closed":1,"stories_assigned":1,"stories_closed":0,"history_events":2,"last_login":"2026-09-17T09:00:00Z","last_activity":"2026-09-17T11:01:00Z"},
                ] if include_members else []
                subj = next((x for x in [
                    {"username":"alice","tasks_assigned":3,"tasks_closed":2,"stories_assigned":2,"stories_closed":1,"history_events":4,"last_login":"2026-09-17T10:00:00Z","last_activity":"2026-09-17T11:00:00Z"},
                    {"username":"bob","tasks_assigned":1,"tasks_closed":1,"stories_assigned":1,"stories_closed":0,"history_events":2,"last_login":"2026-09-17T09:00:00Z","last_activity":"2026-09-17T11:01:00Z"},
                ] if x['username'] == subject), None)
                timeline = [
                    {"ts":"2026-09-17T11:00:00Z","actor":"alice","type":"change","key":"task:1"},
                    {"ts":"2026-09-17T11:01:00Z","actor":"bob","type":"change","key":"task:2"},
                ]
                if subject:
                    timeline = [x for x in timeline if x['actor'] == subject]
                return 200, {"ok":True,"project":{"id":1,"slug":"alpha","name":"Alpha"},"counts":{"tasks":4,"tasks_closed":3,"userstories":3,"userstories_closed":1,"milestones":1,"milestones_closed":0,"members":2},"subject":subj,"members":members,"timeline":timeline,"secrets_exposed":False}
            return 503, {"ok":False}
        service._http_json = fake_http

        def fake_http_post(url, payload, *, headers=None, timeout=8.0):
            self.post_calls.append((url, payload, headers or {}))
            if '/access/grant' in url:
                return 200, {"ok": True, "taiga_username": payload.get("username"), "created_user": True, "created_membership": True, "secrets_exposed": False}
            return 503, {"ok": False, "error": "unexpected"}
        service._http_json_post = fake_http_post

    def tearDown(self):
        service._DB = self.old_db
        projects_service._DB = self.old_projects_db
        service._AUDIT_TOKEN = self.old_audit
        service._FORJA_ENV = self.old_forja
        service._TAIGA_RECONCILER_ENV = self.old_taiga_reconciler_env
        service._http_json = self.old_http
        service._http_json_post = self.old_http_post
        self.temp.cleanup()

    def test_student_sees_only_visible_project_and_own_activity(self):
        identity = Identity('alice','alice@example.invalid',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertEqual([p['slug'] for p in data['projects']], ['alpha'])
        self.assertFalse(data['can_view_members'])
        self.assertTrue(data['activity'])
        self.assertTrue(all(e['actor_id'] == 'alice' for e in data['activity']))
        self.assertEqual({e['source'] for e in data['activity']}, {'forgejo','taiga'})
        audit_url = next(url for url,_headers in self.calls if '/v1/events?' in url)
        self.assertEqual(parse_qs(urlsplit(audit_url).query)['subject'], ['alice'])
        self.assertNotIn('auth_token', json.dumps(data))
        summary_url = next(url for url,_headers in self.calls if '/summary?' in url)
        q = parse_qs(urlsplit(summary_url).query)
        self.assertEqual(q['subject'], ['alice'])
        self.assertEqual(q['include_members'], ['0'])
        self.assertEqual(data['taiga_project']['members'], [])
        self.assertEqual(data['subject']['tasks_assigned'], 3)

    def test_professor_with_acl_sees_project_member_summary(self):
        identity = Identity('prof','prof@example.invalid',frozenset({'CloudIF-Professor'}))
        data = service.taiga_data(identity, 'beta')
        self.assertEqual([p['slug'] for p in data['projects']], ['beta'])
        self.assertTrue(data['can_view_members'])
        self.assertEqual({x['username'] for x in data['actors']}, {'alice','bob'})
        audit_url = next(url for url,_headers in self.calls if '/v1/events?' in url)
        self.assertNotIn('subject', parse_qs(urlsplit(audit_url).query))
        summary_url = next(url for url,_headers in self.calls if '/summary?' in url)
        q = parse_qs(urlsplit(summary_url).query)
        self.assertNotIn('subject', q)
        self.assertEqual(q['include_members'], ['1'])
        self.assertEqual({x['username'] for x in data['taiga_project']['members']}, {'alice','bob'})
        self.assertEqual({x['username'] for x in data['actors']}, {'alice','bob'})

    def test_faro_telemetry_is_filtered_to_taiga_containers(self):
        identity = Identity('alice','',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertEqual(len(data['faro']['containers']), 1)
        self.assertIn('taiga-back', data['faro']['containers'][0]['image'])

    def test_private_taiga_degrades_without_faro_broker_client(self):
        missing = Path(self.temp.name) / 'missing-reconciler.env'
        service._TAIGA_RECONCILER_ENV = str(missing)
        identity = Identity('alice','',frozenset({'CloudIF-Aluno'}))
        data = service.taiga_data(identity, 'alpha')
        self.assertFalse(data['taiga_project']['configured'])
        self.assertEqual(data['taiga_project']['error'], 'taiga_reconciler_credentials_unconfigured')
        markup = views.taiga_body(data)
        self.assertIn('Cliente do broker Faro não configurado', markup)
        self.assertIn('Atividade do projeto', markup)


    def test_admin_grants_only_own_access_to_visible_project(self):
        identity = Identity('silviopro','silviopro@example.invalid',frozenset({'CloudIF-Tenants-Admin'}))
        result = service.grant_taiga_access(identity, 'alpha')
        self.assertTrue(result['ok'])
        self.assertEqual(result['redirect'], 'https://taiga.cloudiff.duckdns.org/project/alpha')
        self.assertEqual(len(self.post_calls), 1)
        url,payload,headers = self.post_calls[0]
        self.assertTrue(url.endswith('/v1/projects/alpha/access/grant'))
        self.assertEqual(payload, {'username':'silviopro','email':'silviopro@example.invalid','full_name':'silviopro'})
        self.assertTrue(headers.get('Authorization','').startswith('Bearer '))
        self.assertNotIn('Authorization', result)

    def test_professor_cannot_grant_project_outside_visibility(self):
        identity = Identity('prof','prof@example.invalid',frozenset({'CloudIF-Professor'}))
        result = service.grant_taiga_access(identity, 'alpha')
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 403)
        self.assertEqual(result['error'], 'project_not_visible')
        self.assertEqual(self.post_calls, [])

    def test_student_cannot_grant_taiga_access(self):
        identity = Identity('alice','alice@example.invalid',frozenset({'CloudIF-Aluno'}))
        result = service.grant_taiga_access(identity, 'alpha')
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 403)
        self.assertEqual(result['error'], 'forbidden')
        self.assertEqual(self.post_calls, [])

    def test_global_view_uses_csrf_post_for_open_project(self):
        identity = Identity('silviopro','silviopro@example.invalid',frozenset({'CloudIF-Tenants-Admin'}))
        data = service.taiga_data(identity, 'alpha')
        data['csrf'] = 'csrf-test'
        markup = views.taiga_body(data)
        self.assertIn('method="post"', markup)
        self.assertIn('/cloudiff/portal/action/taiga-access', markup)
        self.assertIn('name="csrf_token" value="csrf-test"', markup)
        self.assertIn('name="project" value="alpha"', markup)

    def test_navigation_adds_taiga_without_replacing_projects(self):
        shell = SHELL.read_text()
        self.assertIn('(\"projetos\", \"Projetos\")', shell)
        self.assertIn('(\"taiga\", \"Taiga\")', shell)
        self.assertLess(shell.index('(\"projetos\", \"Projetos\")'), shell.index('(\"taiga\", \"Taiga\")'))
        self.assertIn('projects, taiga, overview', WIRING.read_text())
        coexist = COEXIST.read_text()
        self.assertIn('native_taiga', coexist)
        self.assertIn('/cloudiff/portal/pagina/taiga', coexist)

    def test_taiga_post_bridge_does_not_depend_on_get_only_route_query(self):
        source = COEXIST.read_text()
        start = source.index('if parsed.path in {"/cloudif/portal/action/taiga-access"')
        end = source.index('query_action =', start)
        block = source[start:end]
        self.assertIn('urllib.parse.parse_qs(parsed.query)', block)
        self.assertNotIn('route_query.items()', block)

    def test_projects_module_was_not_extended_with_taiga_logic(self):
        self.assertNotIn('taiga', PROJECTS.read_text().lower())


if __name__ == '__main__':
    unittest.main()
