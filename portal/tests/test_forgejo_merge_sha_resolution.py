from __future__ import annotations

import ast
import hmac
import json
import re
import types
import unittest
import urllib.parse
from pathlib import Path

FORJA_PATH=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
FORJA_SOURCE=FORJA_PATH.read_text()
GATEWAY_PATH=Path('components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py')
GATEWAY_SOURCE=GATEWAY_PATH.read_text()

WANTED_FUNCS={
    '_proposal_number','_controlled_pr','_proposal_merge_status','_proposal_public','_proposal_detail',
    'cloudif_proposal_list','cloudif_proposal_get','cloudif_proposal_ready_for_review','cloudif_proposal_action',
}
WANTED_ASSIGNS={'_PROPOSAL_COMMIT_RE','_PROPOSAL_APPROVAL_RE'}
tree=ast.parse(FORJA_SOURCE);nodes=[]
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name in WANTED_FUNCS:nodes.append(node)
    elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in WANTED_ASSIGNS for t in node.targets):nodes.append(node)
module=ast.Module(body=nodes,type_ignores=[]);ast.fix_missing_locations(module)

class FakeForgejo:
    def __init__(self):
        self.pr={
            'number':7,'title':'WIP: Sanitized documents','state':'open','draft':True,'merged':False,'mergeable':False,
            'head':{'ref':'cloudif-proposal-abc123','sha':'a'*40},'base':{'ref':'main','sha':'b'*40},
            'user':{'login':'agent'},'html_url':'https://forgejo.example/pr/7','created_at':'2026-08-08T10:00:00Z','updated_at':'2026-08-08T10:00:00Z',
        }
        self.merge_posts=0;self.patch_posts=0
    def api(self,method,path,payload=None,timeout=45):
        if method=='GET' and '/pulls?' in path:return {'ok':True,'status':200,'data':[dict(self.pr)]}
        if method=='GET' and path.endswith('/pulls/7'):return {'ok':True,'status':200,'data':dict(self.pr)}
        if method=='PATCH' and path.endswith('/pulls/7'):
            self.patch_posts+=1
            if payload and 'title' in payload:
                self.pr['title']=payload['title'];self.pr['draft']=self.pr['title'].startswith('WIP: ');self.pr['mergeable']=not self.pr['draft']
            return {'ok':True,'status':200,'data':dict(self.pr)}
        if method=='POST' and path.endswith('/pulls/7/merge'):
            self.merge_posts+=1
            if self.pr['draft']:return {'ok':False,'status':405,'data':{}}
            if (payload or {}).get('head_commit_id')!=self.pr['head']['sha']:return {'ok':False,'status':409,'data':{}}
            self.pr['merged']=True;self.pr['state']='closed';self.pr['mergeable']=False;self.pr['merge_commit_sha']='c'*40;self.pr['merged_at']='2026-08-08T11:00:00Z'
            return {'ok':True,'status':200,'data':{'merged':True}}
        if method=='GET' and path.endswith('/pulls/7/merge'):
            return {'ok':self.pr['merged'],'status':204 if self.pr['merged'] else 404,'data':{}}
        return {'ok':False,'status':500,'data':{}}

def forja_namespace(fake):
    events=[]
    ns={
        're':re,'hmac':hmac,'urllib':types.SimpleNamespace(parse=urllib.parse),
        'SLUG_RE':re.compile(r'^[a-z0-9][a-z0-9._-]{1,62}$'),
        'load_project':lambda slug:{'project_slug':slug},'_proposal_repo':lambda project,slug:('owner','repo'),
        '_proposal_api':fake.api,'json_response':lambda handler,code,data:(code,data),'save_event':lambda *args:events.append(args),'now':lambda:'2026-08-08T11:00:00Z',
    }
    exec(compile(module,'<forja-proposal>','exec'),ns)
    return ns,events

class ForgejoMergeShaResolutionTests(unittest.TestCase):
    def test_list_and_get_expose_sha_and_actionable_merge_state(self):
        fake=FakeForgejo();ns,_=forja_namespace(fake)
        code,data=ns['cloudif_proposal_list'](None,{'slug':['project-a'],'state':['open'],'limit':['20']})
        self.assertEqual(code,200);pr=data['proposals'][0]
        self.assertEqual(pr['head_sha'],'a'*40);self.assertEqual(pr['base_sha'],'b'*40)
        self.assertEqual(pr['head_branch'],'cloudif-proposal-abc123');self.assertEqual(pr['base_branch'],'main')
        self.assertEqual(pr['mergeable_state'],'draft');self.assertEqual(pr['merge_block_reason'],'proposal_is_draft')
        code,data=ns['cloudif_proposal_get'](None,{'slug':['project-a'],'number':['7']})
        self.assertEqual(code,200);self.assertEqual(data['proposal']['head_sha'],'a'*40);self.assertTrue(data['read_only'])

    def test_ready_for_review_is_separate_and_does_not_modify_main(self):
        fake=FakeForgejo();ns,events=forja_namespace(fake)
        code,data=ns['cloudif_proposal_ready_for_review'](None,{'project_slug':'project-a','number':7,'requested_by':'client','trace_id':'trace-1'})
        self.assertEqual(code,200);self.assertTrue(data['ok']);self.assertFalse(data['proposal']['draft']);self.assertFalse(data['main_modified'])
        self.assertEqual(data['proposal']['mergeable_state'],'ready');self.assertEqual(fake.patch_posts,1);self.assertEqual(fake.merge_posts,0);self.assertTrue(events)

    def test_merge_refuses_draft_and_stale_sha_then_accepts_pinned_sha(self):
        fake=FakeForgejo();ns,_=forja_namespace(fake)
        base={'project_slug':'project-a','proposal_number':7,'action':'merge','approval_id':'apr_'+'1'*20,'requested_by':'client','trace_id':'trace-2'}
        code,data=ns['cloudif_proposal_action'](None,{**base,'expected_head_sha':'a'*40})
        self.assertEqual(code,409);self.assertEqual(data['error'],'proposal_is_draft');self.assertEqual(fake.merge_posts,0)
        code,_=ns['cloudif_proposal_ready_for_review'](None,{'project_slug':'project-a','number':7,'requested_by':'client','trace_id':'trace-ready'})
        self.assertEqual(code,200)
        code,data=ns['cloudif_proposal_action'](None,{**base,'expected_head_sha':'d'*40})
        self.assertEqual(code,409);self.assertEqual(data['error'],'head_sha_mismatch');self.assertEqual(data['actual_head_sha'],'a'*40);self.assertEqual(fake.merge_posts,0)
        code,data=ns['cloudif_proposal_action'](None,{**base,'expected_head_sha':'a'*40})
        self.assertEqual(code,200);self.assertTrue(data['merged']);self.assertTrue(data['main_modified']);self.assertEqual(data['head_sha'],'a'*40);self.assertEqual(fake.merge_posts,1)

    def test_gateway_contract_resolves_and_freezes_sha_server_side(self):
        self.assertIn("'name':'forgejo.proposal.get'",GATEWAY_SOURCE)
        self.assertIn("'name':'forgejo.proposal.ready-for-review'",GATEWAY_SOURCE)
        self.assertIn("'required':['slug','number','reason']",GATEWAY_SOURCE)
        self.assertIn("'required':['slug','number','approval_id']",GATEWAY_SOURCE)
        self.assertIn("proposal,sha=resolve_proposal_head(slug,number,args.get('expected_head_sha') or '')",GATEWAY_SOURCE)
        self.assertIn("sha=str(meta.get('expected_head_sha') or '').strip().lower()",GATEWAY_SOURCE)
        self.assertIn("content={'ok':True,'approval_id':created['approval_id'],'proposal_number':number,'expected_head_sha':sha",GATEWAY_SOURCE)
        self.assertIn("'forgejo.proposal.get':'forgejo:proposal-read'",GATEWAY_SOURCE)
        self.assertIn("'forgejo.proposal.ready-for-review':'forgejo:proposal-merge'",GATEWAY_SOURCE)

    def test_forja_mirror_remains_identical(self):
        mirror=Path('components/runtime/usr/local/sbin/cloudif-forja-agent.py').read_text()
        self.assertEqual(FORJA_SOURCE,mirror)

if __name__=='__main__':unittest.main()
