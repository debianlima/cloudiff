from __future__ import annotations

import importlib.util
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
FORJA=ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
WORKER=ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'


class MembershipIdentityPendingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        root=Path(cls.tmp.name)
        env={
            'FORJA_ENVFILE':str(root/'missing.env'),
            'FORJA_STATE_DIR':str(root/'projects'),
            'FORJA_EVENT_DIR':str(root/'events'),
            'FORJA_ARTIFACT_STAGE_DIR':str(root/'artifacts'),
        }
        cls.env_patch=mock.patch.dict(os.environ,env,clear=False);cls.env_patch.start()
        spec=importlib.util.spec_from_file_location('forja_identity_pending_test',FORJA)
        cls.agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.agent)
        cls.env_patch.stop()
        cls.agent.CFG['FORGEJO_TOKEN']='test-token'
        cls.agent.CFG['FORGEJO_URL']='http://forgejo.invalid'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_redirected_username_is_pending_not_existing(self):
        def fake_http(method,url,**kwargs):
            self.assertIn('/users/iff200',url)
            return {'ok':True,'status':200,'data':{'login':'iff100','id':20}}
        with mock.patch.object(self.agent,'http_json',side_effect=fake_http), mock.patch.object(self.agent.subprocess,'run') as run:
            result=self.agent.ensure_forgejo_user_from_authentik('iff200')
        self.assertTrue(result['ok'])
        self.assertTrue(result['pending'])
        self.assertEqual(result['reason'],'username_redirect_conflict')
        run.assert_not_called()

    def test_duplicate_directory_email_uses_unique_placeholder(self):
        created={'value':False};commands=[]
        def fake_http(method,url,**kwargs):
            if '/users/iff300' in url:
                if created['value']:
                    return {'ok':True,'status':200,'data':{'login':'iff300','id':30}}
                return {'ok':False,'status':404,'data':{}}
            raise AssertionError(url)
        def fake_identity(payload):
            if payload['q']=='iff300':
                return {'ok':True,'items':[{'principal':'iff300','username':'iff300','email':'shared@iff.edu.br','full_name':'Student'}]}
            if payload['q']=='shared@iff.edu.br':
                return {'ok':True,'items':[
                    {'principal':'iff300','username':'iff300','email':'shared@iff.edu.br'},
                    {'principal':'iff301','username':'iff301','email':'shared@iff.edu.br'},
                ]}
            raise AssertionError(payload)
        def fake_run(cmd,**kwargs):
            commands.append(cmd);created['value']=True
            return types.SimpleNamespace(returncode=0)
        with mock.patch.object(self.agent,'http_json',side_effect=fake_http), mock.patch.object(self.agent,'authentik_identity_lookup',side_effect=fake_identity), mock.patch.object(self.agent.subprocess,'run',side_effect=fake_run):
            result=self.agent.ensure_forgejo_user_from_authentik('iff300')
        self.assertTrue(result['ok'])
        self.assertTrue(result['created'])
        self.assertEqual(result['email_mode'],'placeholder_duplicate_directory_email')
        cmd=commands[0]
        self.assertEqual(cmd[cmd.index('--email')+1],'iff300@pending.cloudif.invalid')

    def test_pending_member_is_not_added_or_marked_managed(self):
        saved=[]
        with mock.patch.object(self.agent,'load_project',return_value={'forgejo':{'owner':'owner','repo':'cloudif-demo'},'managed_collaborators':[]}), \
             mock.patch.object(self.agent,'save_project',side_effect=lambda x:saved.append(dict(x)) or x), \
             mock.patch.object(self.agent,'ensure_forgejo_user_from_authentik',return_value={'ok':True,'pending':True,'reason':'username_redirect_conflict'}), \
             mock.patch.object(self.agent,'forgejo_api_base',return_value='http://forgejo.invalid/api/v1'), \
             mock.patch.object(self.agent,'http_json') as http:
            result=self.agent.reconcile_project_membership({'project':'demo','owner_user':'owner','access':{'owner':'owner','acl':[{'type':'user','subject':'iff200'}]}})
        self.assertTrue(result['ok'])
        self.assertTrue(result['pending'])
        self.assertEqual(result['pending_users'],[{'username':'iff200','reason':'username_redirect_conflict'}])
        self.assertEqual(saved[-1]['managed_collaborators'],[])
        http.assert_not_called()

    def test_worker_treats_identity_and_terminal_creation_as_soft_while_pending(self):
        source=WORKER.read_text()
        for marker in (
            "forgejo_pending=bool(fdata.get('pending'))",
            "forgejo_effective_ok=bool(forgejo.get('ok') or forgejo_pending)",
            "elif komodo_pending and stage=='create_terminal'",
            "pending_terminal_errors",
            "'pending':bool(forgejo_pending or komodo_pending)",
        ):
            self.assertIn(marker,source)


if __name__=='__main__':unittest.main()
