"""Offline-only contract tests: no real Docker, network, identities, or secrets."""
import contextlib
import hashlib
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'components/runtime/current-apps/komodo-agent-current'))
import cloudif_publication_operation_guard as guard
import cloudif_publication_recovery_journal as journal


class FakeIdentity:
    def __init__(self,fail_on=None):
        self.calls=0
        self.fail_on=fail_on

    def assert_current(self,project,kind):
        self.calls+=1
        if self.calls==self.fail_on:
            raise PermissionError('revoked_identity')
        assert project=='example' and kind=='production_release'


class FakeLease:
    def __init__(self,fail_on=None):
        self.calls=0
        self.fail_on=fail_on

    def assert_current(self):
        self.calls+=1
        if self.calls==self.fail_on:
            raise PermissionError('lease_lost')


class FakeLeaseAuthority:
    def __init__(self,fail_on=None):
        self.lease_obj=FakeLease(fail_on)

    @contextlib.contextmanager
    def lease(self,project,public_number):
        assert project=='example' and public_number==10
        yield self.lease_obj


class FakeProof:
    def __init__(self,can_verify=True):
        self.store={}
        self.can_verify=can_verify

    def attest(self,record,result):
        assert record['phase']=='mutating'
        assert result['ok'] is True
        proof={
            'project':record['project'],
            'operation_id':record['operation_id'],
            'target_container':record['target_container'],
            'public_number':record['public_number'],
            'container_id':result['container_id'],
            'decision':'committed',
        }
        data=json.dumps(proof,sort_keys=True).encode()
        digest=hashlib.sha256(data).hexdigest()
        self.store[digest]=proof
        return digest

    def verify(self,record,phase,digest):
        p=self.store.get(digest)
        return bool(self.can_verify
                    and p is not None and phase=='committed'
                    and p['decision']==phase
                    and p['operation_id']==record['operation_id']
                    and p['project']==record['project']
                    and p['public_number']==record['public_number']
                    and p['target_container']==record['target_container'])


class ReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'recovery.sqlite'
        self.identity=FakeIdentity()
        self.lease=FakeLeaseAuthority()
        self.proof=FakeProof()
        self.effects=[]

    def make_call(self,mutation=None,**overrides):
        def default_mutation(operation_id, lease):
            lease.assert_current()
            with journal.PublicationRecoveryJournal(self.path) as j:
                active=j.unresolved('example')
                self.assertEqual(len(active),1)
                self.assertEqual(active[0]['phase'],'mutating')
                self.assertEqual(active[0]['operation_id'],operation_id)
            self.effects.append(operation_id)
            return {'ok':True,'container_id':'sha256:synthetic'}
        values=dict(
            database_path=self.path,
            project='example',
            kind='production_release',
            public_number=10,
            publication_number=1,
            target='cloudif-p10-d3-web',
            identity_authority=self.identity,
            lease_authority=self.lease,
            proof_authority=self.proof,
            perform_mutation=mutation or default_mutation,
        )
        values.update(overrides)
        return guard.execute_fenced_publication(**values)

    def test_missing_verifier_denies_before_journal_or_side_effect(self):
        with self.assertRaisesRegex(guard.PublicationGuardUnavailable,'missing_verify'):
            self.make_call(proof_authority=type('Fake',(),{'attest':lambda *x:None})())
        self.assertFalse(self.path.exists())
        self.assertEqual(self.effects,[])

    def test_missing_lease_denies_before_journal_or_side_effect(self):
        with self.assertRaisesRegex(guard.PublicationGuardUnavailable,'missing_lease'):
            self.make_call(lease_authority=object())
        self.assertFalse(self.path.exists())
        self.assertEqual(self.effects,[])

    def test_lost_lease_before_prepare_does_not_create_journal(self):
        self.lease=FakeLeaseAuthority(fail_on=1)
        with self.assertRaisesRegex(PermissionError,'lease_lost'):
            self.make_call()
        self.assertFalse(self.path.exists())

    def test_success_requires_real_lease_identity_and_independent_proof(self):
        self.assertTrue(self.make_call()['ok'])
        self.assertEqual(len(self.effects),1)
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved(),[])
            state=j.con.execute('select phase,verification_sha256 from stage_publication_operation_journal').fetchone()
            self.assertEqual(state['phase'],'committed')
            self.assertEqual(len(state['verification_sha256']),64)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)

    def test_failure_after_mutation_leaves_unresolved_fence(self):
        def fails(key, lease):
            self.effects.append(key)
            raise RuntimeError('external_effect_uncertain')
        with self.assertRaisesRegex(RuntimeError,'external_effect_uncertain'):
            self.make_call(fails)
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')
        with self.assertRaisesRegex(journal.PublicationJournalConflict,'unresolved_project_operation'):
            self.make_call()
        self.assertEqual(len(self.effects),1)

    def test_negative_response_requires_reconciliation(self):
        with self.assertRaisesRegex(guard.PublicationGuardUnavailable,'unverified_mutation_result'):
            self.make_call(lambda _, lease: {'ok':False})
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')

    def test_rejected_proof_does_not_commit(self):
        self.proof=FakeProof(can_verify=False)
        with self.assertRaisesRegex(journal.PublicationJournalConflict,'evidence_verification_failed'):
            self.make_call()
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')

    def test_lease_lost_after_side_effect_does_not_commit(self):
        # assert calls: pre-journal, after prepare, after mutating, after mutate.
        self.lease=FakeLeaseAuthority(fail_on=5)
        with self.assertRaisesRegex(PermissionError,'lease_lost'):
            self.make_call()
        self.assertEqual(len(self.effects),1)
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')

    def test_current_identity_revoked_after_effect_stays_unresolved(self):
        # identity calls before prepare, after prepare, after mutating, after mutate
        self.identity=FakeIdentity(fail_on=4)
        with self.assertRaisesRegex(PermissionError,'revoked_identity'):
            self.make_call()
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')

    def test_revocation_before_external_intent_aborts_cleanly(self):
        self.identity=FakeIdentity(fail_on=2)
        with self.assertRaisesRegex(PermissionError,'revoked_identity'):
            self.make_call()
        with journal.PublicationRecoveryJournal(self.path) as j:
            self.assertEqual(j.unresolved(),[])
            self.assertEqual(j.con.execute('select phase from stage_publication_operation_journal').fetchone()['phase'],'aborted')
        self.assertEqual(self.effects,[])

    def test_no_explicit_auto_replay_after_ambiguous_result(self):
        with self.assertRaises(guard.PublicationGuardUnavailable):
            self.make_call(lambda _, lease: None)
        for _ in range(2):
            with self.assertRaises(journal.PublicationJournalConflict):
                self.make_call()
        self.assertEqual(self.effects,[])

if __name__=='__main__':
    unittest.main()
