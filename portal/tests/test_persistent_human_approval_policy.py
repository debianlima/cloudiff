from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APPROVAL_DIR=ROOT/'components/control-plane/current-apps/approvals-current'
API=APPROVAL_DIR/'cloudif-approval-api.py'


def load_api(root:Path):
    os.environ['CLOUDIF_APPROVAL_DB']=str(root/'approvals.db')
    os.environ['CLOUDIF_APPROVAL_TOKEN']='test-token'
    sys.path.insert(0,str(APPROVAL_DIR))
    name='approval_policy_api_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,API);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);return module


class PersistentHumanApprovalPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_api(Path(self.temp.name))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),self.module.H);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.temp.cleanup()

    def call(self,method,path,payload=None):
        data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
        request=urllib.request.Request(self.base+path,data=data,method=method,headers={'Authorization':'Bearer test-token','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)

    def create(self,action='project.environment.change',requested_by='agent-a',slug='demo'):
        return self.call('POST','/v1/approvals',{'project_slug':slug,'action':action,'requested_by':requested_by,'requester_role':'agent','ttl_seconds':900,'reason':'Operação revisada','metadata':{'digest':'a'*64}})

    def test_single_approval_can_create_always_allow_policy_and_future_request_is_autoapproved(self):
        code,created=self.create();self.assertEqual(code,201);self.assertEqual(created['status'],'pending')
        code,approved=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'professor','approver_role':'professor','always_allow':True})
        self.assertEqual(code,200);self.assertEqual(approved['status'],'approved');self.assertTrue(approved['persistent_policy_created']);policy_id=approved['approval_policy_id']
        code,policies=self.call('GET','/v1/approval-policies?status=active');self.assertEqual(code,200);self.assertEqual([x['policy_id'] for x in policies['policies']],[policy_id])
        code,future=self.create();self.assertEqual(code,201);self.assertEqual(future['status'],'approved');self.assertTrue(future['policy_applied']);self.assertEqual(future['authorization_mode'],'persistent_policy');self.assertEqual(future['approval_policy_id'],policy_id)

    def test_policy_scope_is_exact_project_action_and_requester(self):
        _,created=self.create();self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'admin','approver_role':'admin','always_allow':True})
        for action,requester,slug in (
            ('project.environment.promotion','agent-a','demo'),
            ('project.environment.change','agent-b','demo'),
            ('project.environment.change','agent-a','outro'),
        ):
            _,future=self.create(action,requester,slug);self.assertEqual(future['status'],'pending',(action,requester,slug,future))

    def test_policy_can_be_revoked_and_next_request_returns_to_pending(self):
        _,created=self.create();_,approved=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'professor','approver_role':'professor','always_allow':True});policy_id=approved['approval_policy_id']
        code,revoked=self.call('POST',f'/v1/approval-policies/{policy_id}/revoke',{'revoked_by':'professor','reason':'Revisar novamente'});self.assertEqual(code,200);self.assertTrue(revoked['revoked'])
        _,future=self.create();self.assertEqual(future['status'],'pending');self.assertFalse(future['policy_applied'])

    def test_portal_requester_namespace_cannot_bypass_dual_approval_identity_check(self):
        code,created=self.call('POST','/v1/approvals',{'project_slug':'demo','action':'deployment.production.activate','requested_by':'portal:admin-a','requester_role':'owner','ttl_seconds':900,'reason':'Produção','metadata':{}})
        self.assertEqual(code,201);self.assertEqual(created['status'],'pending')
        code,denied=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'admin-a','approver_role':'admin'})
        self.assertEqual(code,409);self.assertEqual(denied['error'],'requester_cannot_approve_activation')
        code,first=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'admin-b','approver_role':'admin'})
        self.assertEqual(code,200);self.assertEqual(first['status'],'pending_second')
        code,same_again=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'portal:admin-b','approver_role':'admin'})
        self.assertEqual(code,409);self.assertEqual(same_again['error'],'distinct_second_approver_required')

    def test_critical_dual_action_activates_policy_only_after_current_dual_flow_finishes(self):
        _,created=self.create('deployment.production.activate');self.assertEqual(created['status'],'pending');self.assertTrue(created['two_approvers_required'])
        _,first=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'prof-a','approver_role':'professor','always_allow':True})
        self.assertEqual(first['status'],'pending_second');self.assertTrue(first['persistent_policy_requested'])
        _,policies=self.call('GET','/v1/approval-policies?status=active');self.assertEqual(policies['policies'],[])
        _,second=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'admin-b','approver_role':'admin'})
        self.assertEqual(second['status'],'approved');self.assertTrue(second['persistent_policy_created']);policy_id=second['approval_policy_id']
        _,future=self.create('deployment.production.activate');self.assertEqual(future['status'],'approved');self.assertTrue(future['policy_applied']);self.assertEqual(future['approval_policy_id'],policy_id);self.assertTrue(future['two_approvers_required'])

    def test_autoapproved_request_still_uses_single_use_reserve_finalize(self):
        _,created=self.create();self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'professor','approver_role':'professor','always_allow':True})
        _,future=self.create();aid=future['approval_id'];reservation='res_'+'1'*32
        code,reserved=self.call('POST',f'/v1/approvals/{aid}/reserve',{'reservation_id':reservation,'reserved_by':'agent-a','ttl_seconds':300});self.assertEqual(code,200);self.assertEqual(reserved['status'],'reserved')
        code,done=self.call('POST',f'/v1/approvals/{aid}/finalize',{'reservation_id':reservation,'result':'success'});self.assertEqual(code,200);self.assertEqual(done['status'],'consumed')

    def test_secret_read_is_critical_dual_approval_action(self):
        source=Path('components/control-plane/current-apps/approvals-current/cloudif-approval-api.py').read_text()
        start=source.index('DUAL_APPROVAL_ACTIONS=');end=source.index('}',start)
        self.assertIn("'project.environment.secret.read'",source[start:end+1])
        self.assertIn('approval_policy',source)


    def test_critical_secret_read_can_be_marked_always_allow_after_two_privileged_decisions(self):
        _,created=self.create('project.environment.secret.read');self.assertEqual(created['status'],'pending');self.assertTrue(created['two_approvers_required'])
        code,first=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'prof-a','approver_role':'professor','always_allow':True})
        self.assertEqual(code,200);self.assertEqual(first['status'],'pending_second');self.assertTrue(first['persistent_policy_requested'])
        code,second=self.call('POST',f"/v1/approvals/{created['approval_id']}/approve",{'approved_by':'admin-b','approver_role':'admin'})
        self.assertEqual(code,200);self.assertEqual(second['status'],'approved');self.assertTrue(second['persistent_policy_created'])
        _,future=self.create('project.environment.secret.read');self.assertEqual(future['status'],'approved');self.assertTrue(future['policy_applied']);self.assertTrue(future['two_approvers_required'])


    def test_legacy_active_index_is_migrated(self):
        import sqlite3
        legacy=tempfile.TemporaryDirectory();root=Path(legacy.name);db=root/'approvals.db'
        connection=sqlite3.connect(db)
        connection.executescript('''
          create table approvals(approval_id text primary key,project_slug text not null,action text not null,requested_by text not null,approved_by text,status text not null,reason text,created_at integer not null,expires_at integer not null,approved_at integer,consumed_at integer,trace_id text,metadata_json text not null default '{}');
          create unique index idx_approval_active on approvals(project_slug,action,requested_by) where status in ('pending','approved');
        ''');connection.commit();connection.close()
        module=load_api(root)
        connection=sqlite3.connect(db)
        sql=connection.execute("select sql from sqlite_master where type='index' and name='idx_approval_active'").fetchone()[0]
        cols={row[1] for row in connection.execute('pragma table_info(approvals)')}
        policies=connection.execute("select name from sqlite_master where type='table' and name='approval_policies'").fetchone()
        connection.close();legacy.cleanup()
        self.assertIn("pending_second",sql);self.assertNotIn("'approved'",sql)
        self.assertIn('approval_policy_id',cols);self.assertIsNotNone(policies)


if __name__=='__main__':unittest.main()
