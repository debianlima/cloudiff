from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORJA = ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'


def load_forja():
    spec = importlib.util.spec_from_file_location('forja_taiga_activity_test', FORJA)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ForjaTaigaActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_forja()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_state = self.m.STATE_DIR
        self.m.STATE_DIR = Path(self.temp.name)/'projects'
        self.m.STATE_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.m.STATE_DIR = self.old_state
        self.temp.cleanup()

    def test_actor_uses_login_not_email(self):
        body = {'sender': {'login': 'Aluno123', 'email': 'private@example.invalid'}}
        self.assertEqual(self.m._cloudif_forgejo_actor(body), 'aluno123')
        activity = self.m._cloudif_forgejo_activity('push', {
            **body, 'ref':'refs/heads/main', 'after':'a'*40,
            'head_commit': {'message':'TG-32 corrige autenticação\ntexto privado'}
        }, 'delivery-1')
        raw = json.dumps(activity)
        self.assertNotIn('private@example.invalid', raw)
        self.assertNotIn('texto privado', raw)
        self.assertEqual(activity['summary'], 'TG-32 corrige autenticação')
        self.assertEqual(activity['actor'], 'aluno123')

    def test_activity_state_is_sanitized_and_bounded(self):
        slug='demo'
        self.m.save_project({'project_slug':slug})
        for i in range(120):
            self.m._cloudif_record_activity(slug, {'ts':f'2026-09-17T12:{i%60:02d}:00','source':'forgejo','event':'push','actor':'alice','commit':str(i)})
        project=self.m.load_project(slug)
        self.assertEqual(len(project['activity']),100)
        self.assertEqual(project['activity'][-1]['actor'],'alice')

    def test_pull_request_and_release_only_keep_safe_fields(self):
        pr=self.m._cloudif_forgejo_activity('pull_request', {'sender':{'username':'alice','email':'x@y'},'action':'opened','pull_request':{'number':7,'title':'Revisar TG-7','body':'sensitive body'}}, 'd1')
        rel=self.m._cloudif_forgejo_activity('release', {'sender':{'login':'alice'},'action':'published','release':{'tag_name':'v1.2.3','body':'notes'}}, 'd2')
        self.assertEqual(pr['number'],7); self.assertNotIn('body',pr)
        self.assertEqual(rel['version'],'v1.2.3'); self.assertNotIn('body',rel)


if __name__=='__main__':
    unittest.main()
