"""Isolated worker-hook integration tests: no Docker or production access.

The trusted callbacks here are synthetic evidence fixtures, NOT real Docker
attestations and NOT a production provider. SQLite is always disposable.
"""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

SRC_DIR=Path(__file__).resolve().parents[2]/'components/runtime/current-apps/komodo-agent-current'
if str(SRC_DIR) not in sys.path:sys.path.insert(0,str(SRC_DIR))
from cloudif_publication_effect_gate import (make_publication_gate,
    PublicationEffectGateUnavailable, StrictPublicationGate)
from cloudif_publication_recovery_journal import (PublicationRecoveryJournal,
    PublicationJournalConflict)
from portal.tests.test_dev01_whp_prior_stop_failure_contract import PromotionFixture


def strict_fixtures(root):
    saved={}
    def raw_dict(row):
        return {k:row[k] for k in ('operation_id','project','kind','public_number',
                                   'publication_number','target_container')}
    def provider(row):
        proof=json.dumps(row,sort_keys=True,separators=(',',':')).encode()
        digest=hashlib.sha256(proof).hexdigest()
        saved[digest]=proof
        return digest
    def verifier(row,phase,digest):
        proof=saved.get(digest)
        if phase!='committed' or not proof or hashlib.sha256(proof).hexdigest()!=digest:
            return False
        return json.loads(proof)==raw_dict(row)
    def factory(project='demo',kind='production_release',num=1200,publication=1,target='cloudif-p1200-d3-web',
                verified=True,**kwargs):
        return make_publication_gate(
            mode='strict',db_path=root/'journal.sqlite',lock_dir=root,
            project=project,kind=kind,public_number=num,
            publication_number=publication,target=target,
            evidence_provider=provider if verified else None,
            evidence_verifier=verifier if verified else None,
            **kwargs)
    return factory


def crash_after_mutating(directory):
    # os._exit emulates a worker process crash after durable intent, without
    # touching another process, Docker, a real DB or any network resource.
    base=Path(directory)
    make= strict_fixtures(base)
    guard=make()
    guard.__enter__()
    os._exit(13)


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.chmod(0o700)
        self.make=strict_fixtures(self.root)

    def test_disabled_compatibility_mode_does_not_create_journal(self):
        gate=make_publication_gate(mode='disabled',db_path=self.root/'journal.sqlite',
            lock_dir=self.root,project='demo',kind='production_release',
            public_number=1200,publication_number=1,target='cloudif-p1200-d3-web')
        with gate as step:step.finish()
        self.assertFalse((self.root/'journal.sqlite').exists())

    def test_unknown_mode_does_not_downgrade_to_disabled(self):
        with self.assertRaisesRegex(PublicationEffectGateUnavailable,'unknown_publication_journal_mode'):
            make_publication_gate(mode='strcit',db_path=self.root/'journal.sqlite',
              lock_dir=self.root,project='demo',kind='production_release',
              public_number=1200,publication_number=1,target='cloudif-p1200-d3-web')

    def test_strict_missing_trusted_evidence_refuses_before_effects(self):
        with self.assertRaisesRegex(PublicationEffectGateUnavailable,'trusted_evidence_provider_missing'):
            self.make(verified=False)
        self.assertFalse((self.root/'journal.sqlite').exists())

    def test_strict_rejects_missing_or_relative_paths_before_file_io(self):
        for db_path,lock_dir in (('',str(self.root)),('state.sqlite',str(self.root)),
                                 (str(self.root/'journal.sqlite'),''),
                                 (str(self.root/'journal.sqlite'),'./locks')):
            with self.subTest(db_path=db_path,lock_dir=lock_dir):
                with self.assertRaisesRegex(PublicationEffectGateUnavailable,'absolute_private_state_paths_required'):
                    make_publication_gate(mode='strict',db_path=db_path,lock_dir=lock_dir,
                        project='demo',kind='production_release',public_number=1200,
                        publication_number=1,target='cloudif-p1200-d3-web',
                        evidence_provider=lambda _: '0'*64,evidence_verifier=lambda *_:False)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_strict_commit_requires_authenticated_fixture_proof(self):
        with self.make() as guard:
            with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
                row=readback.unresolved()[0]
                self.assertEqual(row['phase'],'mutating')
                self.assertEqual(row['project'],'demo')
            guard.finish()
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertFalse(readback.unresolved())
            row=readback.con.execute('select phase,verification_sha256 from stage_publication_operation_journal').fetchone()
            self.assertEqual(row['phase'],'committed')
            self.assertRegex(row['verification_sha256'],r'^[0-9a-f]{64}$')

    def test_early_return_keeps_durable_reconciliation_fence(self):
        with self.make():
            pass # synthetic early return: no verified finish
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(readback.unresolved()[0]['phase'],'needs_reconciliation')
        with self.assertRaises(PublicationJournalConflict):
            with self.make():pass

    def test_competing_local_alias_lease_fails_without_blocking(self):
        first=self.make()
        with first:
            second=self.make(project='another',num=1200)
            with self.assertRaisesRegex(PublicationEffectGateUnavailable,'publication_alias_busy'):
                with second:pass
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(len(readback.unresolved()),1)

    def test_untrusted_state_directory_is_rejected(self):
        self.root.chmod(0o777)
        try:
            with self.assertRaisesRegex(PublicationEffectGateUnavailable,'untrusted_lock_directory'):
                with self.make():pass
        finally:
            self.root.chmod(0o700)
        self.assertFalse((self.root/'journal.sqlite').exists())

    def test_synthetic_worker_crash_keeps_mutating_record_across_processes(self):
        context=multiprocessing.get_context('fork')
        process=context.Process(target=crash_after_mutating,args=(str(self.root),))
        process.start();process.join(timeout=6)
        if process.is_alive():process.terminate();process.join(timeout=3)
        self.assertEqual(process.exitcode,13)
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(readback.unresolved()[0]['phase'],'mutating')
        with self.assertRaises(PublicationJournalConflict):
            with self.make():pass

    def test_durable_mutating_precedes_environment_file_replacement(self):
        fixture=PromotionFixture()
        observations=[]
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,target=target)
        def observed_write(*args):
            with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
                phases=[row['phase'] for row in readback.unresolved()]
            observations.append(phases)
            self.assertEqual(phases,['mutating'])
            return '/tmp/synthetic-env-file-not-written'
        fixture.release.__globals__['_cloudif_v145_operation_gate']=gated
        fixture.release.__globals__['_cloudif_stage_write_environment']=observed_write
        result=fixture.release(object())
        self.assertEqual(result['http_status'],200)
        self.assertEqual(observations,[['mutating']])

    def test_durable_mutating_precedes_manual_docker_start(self):
        from portal.tests.test_dev01_whp_prior_stop_failure_contract import FakeProcess
        fixture=PromotionFixture()
        events=[]
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,target=target)
        original_docker=fixture.subprocess.run
        def observed_docker(args,**kwargs):
            if args[:3]==['docker','inspect',fixture.source] and '{{.State.Running}}' in args[-1]:
                return FakeProcess(stdout='false')
            if args[:2]==['docker','start']:
                with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
                    phases=[row['phase'] for row in readback.unresolved()]
                events.append(phases)
                self.assertEqual(phases,['mutating'])
            return original_docker(args,**kwargs)
        fixture.activate.__globals__['_cloudif_v145_operation_gate']=gated
        fixture.subprocess.run=observed_docker
        result=fixture.activate(object())
        self.assertEqual(result['http_status'],200)
        self.assertEqual(events,[['mutating']])

    def test_fake_release_success_journal_committed_without_real_docker(self):
        fixture=PromotionFixture()
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,target=target)
        fixture.release.__globals__['_cloudif_v145_operation_gate']=gated
        result=fixture.release(object())
        self.assertEqual(result['http_status'],200)
        self.assertEqual(result['containerId'],'same-id-123')
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertFalse(readback.unresolved())

    def test_fake_release_missing_trust_rejected_before_docker_mutation(self):
        fixture=PromotionFixture()
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,
                             target=target,verified=False)
        fixture.release.__globals__['_cloudif_v145_operation_gate']=gated
        result=fixture.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'publication_journal_or_runtime_blocked')
        self.assertFalse(fixture.db_calls)
        self.assertFalse(any(call[:2] in (('docker','restart'),('docker','stop'),('docker','start'))
                             for call in fixture.calls))
        self.assertFalse(fixture.reconnections)

    def test_fake_release_previous_stop_failure_blocks_future_retry(self):
        fixture=PromotionFixture(previous_stop_status=1)
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,target=target)
        fixture.release.__globals__['_cloudif_v145_operation_gate']=gated
        response=fixture.release(object())
        self.assertEqual(response['error'],'previous_production_stop_failed')
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(readback.unresolved()[0]['phase'],'needs_reconciliation')
        # Original fixture remains a simulated handler; the second request may
        # read-only inspect Docker but may not restart/reconfigure it.
        next_fake=PromotionFixture()
        next_fake.release.__globals__['_cloudif_v145_operation_gate']=gated
        response2=next_fake.release(object())
        self.assertEqual(response2['http_status'],503)
        self.assertEqual(response2['error'],'publication_journal_or_runtime_blocked')
        self.assertFalse(next_fake.reconnections)
        self.assertFalse(next_fake.db_calls)

    def test_reconciliation_write_failure_preserves_initial_mutating_fence(self):
        guard=self.make()
        guard.__enter__()
        original=guard.journal.transition
        def synthetic_unavailable(operation_id,**kwargs):
            if kwargs.get('next_phase')=='needs_reconciliation':
                raise OSError('simulated_disk_unavailable')
            return original(operation_id,**kwargs)
        guard.journal.transition=synthetic_unavailable
        # Early HTTP response must not be replaced by a journal write exception.
        self.assertFalse(guard.__exit__(None,None,None))
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(readback.unresolved()[0]['phase'],'mutating')
        with self.assertRaises(PublicationJournalConflict):
            with self.make():pass

    def test_strict_proof_failure_does_not_claim_200_or_committed(self):
        fixture=PromotionFixture()
        def gated(project,kind,num,publication,target):
            return make_publication_gate(mode='strict',db_path=self.root/'journal.sqlite',
                lock_dir=self.root,project=project,kind=kind,public_number=num,
                publication_number=publication,target=target,
                evidence_provider=lambda _:'1'*64,
                evidence_verifier=lambda *args:False)
        fixture.release.__globals__['_cloudif_v145_operation_gate']=gated
        result=fixture.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'publication_journal_or_runtime_blocked')
        self.assertTrue(fixture.db_calls, 'failure is after synthetic DB commit')
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            self.assertEqual(readback.unresolved()[0]['phase'],'needs_reconciliation')

    def test_fake_manual_activation_missing_verifier_blocks_before_start(self):
        fixture=PromotionFixture()
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,
                             target=target,verified=False)
        fixture.activate.__globals__['_cloudif_v145_operation_gate']=gated
        result=fixture.activate(object())
        self.assertEqual(result['http_status'],503)
        self.assertFalse(fixture.reconnections)
        self.assertFalse(fixture.db_calls)

    def test_fake_manual_activation_obeys_same_journal_contract(self):
        fixture=PromotionFixture()
        def gated(project,kind,num,publication,target):
            return self.make(project=project,kind=kind,num=num,publication=publication,target=target)
        fixture.activate.__globals__['_cloudif_v145_operation_gate']=gated
        response=fixture.activate(object())
        self.assertEqual(response['http_status'],200)
        with PublicationRecoveryJournal(self.root/'journal.sqlite') as readback:
            row=readback.con.execute('select kind,phase from stage_publication_operation_journal').fetchone()
            self.assertEqual((row['kind'],row['phase']),('manual_activation','committed'))

if __name__=='__main__':unittest.main()
