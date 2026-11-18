#!/usr/bin/env python3
"""Synthetic contract checks; no SSH, secrets, Docker, runtime services or accounts."""
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import time
import unittest
import sys

# Research fixtures only: never import these modules from a production worker.
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "tools" / "acl_r3_research"))

from acl_revision_gate import GateError, apply_revision, authoritative_request


def sample(revision=1, project='demo', members=None):
    return {'project':project,'owner':'fictional-owner','acl':members if members is not None else [{'type':'user','subject':'fictional-member'}],
            'acl_revision':revision,'stack_ids':['fake-stack'],'repo_id':'fake-repo','server_id':''}


def fake_apply(request,previous):
    return {'ok':True,'targets':['synthetic-'+str(request['acl_revision'])]}


def worker(root,request,signal,results,sleep):
    def callback(req,prev):
        signal.set()
        time.sleep(sleep)
        return fake_apply(req,prev)
    try:results.put(('ok',apply_revision(Path(root),request,'portal',callback)))
    except GateError as e:results.put(('err',e.code))


class RevisionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cloudiff-r3-')
        self.root=Path(self.temp.name)/'state'
        self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def applied(self,request,prior):
        self.calls.append((request['acl_revision'],prior))
        return fake_apply(request,prior)
    def run_apply(self,request,source='portal'):
        return apply_revision(self.root,request,source,self.applied)
    def reject(self,code,request,source='portal'):
        before=len(self.calls)
        with self.assertRaises(GateError) as cm:self.run_apply(request,source)
        self.assertEqual(cm.exception.code,code)
        self.assertEqual(len(self.calls),before,'rejected request must not reach simulated Mongo callback')

    def test_new_revision_then_higher_and_stale_deny(self):
        self.assertEqual(self.run_apply(sample(1))['revision'],1)
        self.assertEqual(self.run_apply(sample(2))['revision'],2)
        self.reject('stale_acl_revision',sample(1))
        self.assertEqual([r for r,_ in self.calls],[1,2])

    def test_replay_equal_revision_and_digest(self):
        self.run_apply(sample(3))
        self.assertTrue(self.run_apply(sample(3),'replay')['replayed'])
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[1][1],['synthetic-3'])

    def test_revision_digest_conflict(self):
        self.run_apply(sample(3))
        self.reject('revision_digest_conflict',sample(3,members=[{'type':'user','subject':'different'}]))

    def test_replay_cannot_advance_revision(self):
        self.run_apply(sample(4))
        self.reject('unauthorized_replay',sample(5),'replay')
        self.reject('stale_acl_revision',sample(3),'replay')

    def test_replay_cannot_initialize_missing_snapshot(self):
        self.reject('unauthorized_replay',sample(7),'replay')
        self.assertFalse((self.root/'demo.json').exists())

    def test_legacy_requires_migration(self):
        self.root.mkdir(mode=0o700)
        (self.root/'demo.json').write_text(json.dumps({'project':'demo','request':sample(7),'targets':['old']}))
        # This test targets the *legacy schema*, not permissive file mode.
        (self.root/'demo.json').chmod(0o600)
        self.reject('legacy_migration_required',sample(8))
        self.assertEqual(json.loads((self.root/'demo.json').read_text())['targets'],['old'])

    def test_untrusted_source_rejected(self):
        self.reject('untrusted_source',sample(1),'forja')

    def test_equal_revision_normalized_membership(self):
        one=sample(1,members=[{'type':'group','subject':'Fictional Group'},{'type':'user','subject':'Fictional User'}])
        two=sample(1,members=list(reversed(one['acl'])))
        self.assertEqual(authoritative_request(one)[-1],authoritative_request(two)[-1])
        self.run_apply(one)
        self.assertTrue(self.run_apply(two,'replay')['ok'])

    def test_owner_or_resources_changed_without_revision_rejected(self):
        self.run_apply(sample(2))
        changed=sample(2); changed['owner']='another-owner'
        self.reject('revision_digest_conflict',changed)
        changed=sample(2);changed['repo_id']='other-repo'
        self.reject('revision_digest_conflict',changed)

    def test_unknown_request_fields_are_never_persisted(self):
        req=sample(1)
        req['authorization']='bearer fictional-secret-marker'
        self.reject('unexpected_fields',req)
        self.assertFalse((self.root/'demo.json').exists())

    def test_world_readable_state_fails_closed(self):
        self.root.mkdir(mode=0o700)
        p=self.root/'demo.json'
        p.write_text(json.dumps({'schema':2,'status':'ready','revision':1,'digest':'synthetic'}))
        p.chmod(0o644)
        self.reject('unsafe_state_file',sample(2))
        self.assertEqual(p.stat().st_mode & 0o777,0o644)

    def test_hardlinked_state_fail_closed(self):
        self.root.mkdir(mode=0o700)
        outside=Path(self.temp.name)/'foreign.json'
        outside.write_text(json.dumps({'schema':2,'status':'ready','revision':1,'digest':'fake'}))
        outside.chmod(0o600)
        (self.root/'demo.json').hardlink_to(outside)
        self.reject('unsafe_state_file',sample(2))
        self.assertEqual(outside.stat().st_nlink,2)

    def test_hardlinked_lock_fail_closed(self):
        self.root.mkdir(mode=0o700)
        outside=Path(self.temp.name)/'foreign.lock'
        outside.write_text('fixture')
        outside.chmod(0o600)
        (self.root/'demo.lock').hardlink_to(outside)
        self.reject('unsafe_lock_file',sample(1))
        self.assertEqual(outside.stat().st_nlink,2)

    def test_rejects_duplicate_or_invalid_acl(self):
        for acl in ([None],['invalid'],[{'type':'user','subject':''}],
                    [{'type':'user','subject':'Example'},{'type':'user','subject':'example'}]):
            with self.assertRaises(GateError): self.run_apply(sample(members=acl))
        self.assertEqual(len(self.calls),0)

    def test_revision_types(self):
        for revision in (0,-1,True,1.0,'1',None):
            with self.assertRaises(GateError):self.run_apply(sample(revision))
        self.assertEqual(len(self.calls),0)

    def test_interrupted_apply_blocks_automatic_replay(self):
        def crash(request,targets):raise RuntimeError('simulated network crash after potential writes')
        with self.assertRaisesRegex(GateError,'apply_interrupted_manual_recovery'):
            apply_revision(self.root,sample(1),'portal',crash)
        self.assertEqual(json.loads((self.root/'demo.json').read_text())['status'],'applying')
        self.reject('manual_recovery_required',sample(1))
        self.reject('manual_recovery_required',sample(2))

    def test_false_success_also_blocks_replay(self):
        with self.assertRaisesRegex(GateError,'apply_failed_manual_recovery'):
            apply_revision(self.root,sample(1),'portal',lambda req,prev:{'ok':False})
        self.reject('manual_recovery_required',sample(1),'replay')

    def test_state_atomic_and_private(self):
        self.run_apply(sample(1))
        p=self.root/'demo.json'
        self.assertEqual(p.stat().st_mode & 0o777,0o600)
        self.assertEqual((self.root/'demo.lock').stat().st_mode & 0o777,0o600)
        self.assertEqual(self.root.stat().st_mode & 0o777,0o700)
        self.assertEqual(json.loads(p.read_text())['status'],'ready')
        self.assertFalse(list(self.root.glob('.acl-pending-*')))

    def test_invalid_symlink_and_path_traversal_rejected(self):
        with self.assertRaises(GateError):self.run_apply(sample(1,project='../escape'))
        self.root.mkdir(mode=0o700)
        (self.root/'demo.json').symlink_to('/dev/null')
        self.reject('unsafe_state_link',sample(1))

    def test_concurrency_lock_serializes_and_denies_stale(self):
        self.root.mkdir(mode=0o700)
        ctx=mp.get_context('fork')
        start=ctx.Event();results=ctx.Queue()
        first=ctx.Process(target=worker,args=(str(self.root),sample(2),start,results,0.45))
        first.start();self.assertTrue(start.wait(3),'first project revision did not hold lock')
        second=ctx.Process(target=worker,args=(str(self.root),sample(1),ctx.Event(),results,0))
        second.start()
        first.join(5);second.join(5)
        self.assertEqual(first.exitcode,0);self.assertEqual(second.exitcode,0)
        outcomes=[results.get(timeout=1) for _ in range(2)]
        self.assertEqual(len([x for x in outcomes if x[0]=='ok']),1)
        self.assertIn(('err','stale_acl_revision'),outcomes)
        self.assertEqual(json.loads((self.root/'demo.json').read_text())['revision'],2)

if __name__=='__main__':unittest.main()
