"""Durable publication-recovery journal prototype tests: temporary SQLite only.

Proves a persistent *fence*, not automatic real-Docker crash recovery.
"""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[2]
MODULE=HERE/'components/runtime/current-apps/komodo-agent-current/cloudif_publication_recovery_journal.py'
SPEC=importlib.util.spec_from_file_location('isolated_publication_recovery_journal',MODULE)
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def payload(project='example',public_number=10,publication_number=1):
    return dict(project=project,kind='production_release',public_number=public_number,
                publication_number=publication_number,target=f'cloudif-p{public_number}-d3-web')

class JournalContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'ephemeral-state.sqlite'

    def journal(self):
        return mod.PublicationRecoveryJournal(self.db)

    def test_prepare_is_durable_after_connection_restart(self):
        with self.journal() as first:
            key=first.prepare(**payload())
            self.assertEqual(first.unresolved()[0]['phase'],'prepared')
        with self.journal() as second:
            self.assertEqual(second.unresolved('example')[0]['operation_id'],key)
            with self.assertRaisesRegex(mod.PublicationJournalConflict,'unresolved_project_operation'):
                second.prepare(**payload(publication_number=2))

    def test_safe_retry_only_before_external_effects(self):
        with self.journal() as j:
            key='a'*32
            self.assertEqual(j.prepare(**payload(),operation_id=key),key)
            self.assertEqual(j.prepare(**payload(),operation_id=key),key)
            j.transition(key,expected_phase='prepared',next_phase='mutating')
            with self.assertRaisesRegex(mod.PublicationJournalConflict,'operation_id_already_advanced'):
                j.prepare(**payload(),operation_id=key)

    def test_crash_after_external_intent_blocks_new_promotion(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            j.transition(key,expected_phase='prepared',next_phase='mutating')
        with self.journal() as restarted:
            self.assertEqual(restarted.unresolved()[0]['phase'],'mutating')
            with self.assertRaises(mod.PublicationJournalConflict):
                restarted.prepare(**payload(publication_number=2))
            restarted.transition(key,expected_phase='mutating',next_phase='needs_reconciliation',
                                 reason_code='worker_crash')
        with self.journal() as restarted_again:
            self.assertEqual(restarted_again.unresolved()[0]['reason_code'],'worker_crash')
            with self.assertRaises(mod.PublicationJournalConflict):
                restarted_again.prepare(**payload(publication_number=3))

    def test_two_connections_cannot_prepare_same_project(self):
        with self.journal() as first, self.journal() as second:
            first.prepare(**payload())
            with self.assertRaises(mod.PublicationJournalConflict):
                second.prepare(**payload(publication_number=2))
            self.assertEqual(len(first.unresolved('example')),1)

    def test_distinct_projects_are_independent(self):
        with self.journal() as j:
            one=j.prepare(**payload('alpha',10))
            two=j.prepare(**payload('beta',11))
            self.assertNotEqual(one,two)
            self.assertEqual(len(j.unresolved()),2)

    def test_clean_terminal_commit_allows_next_operation(self):
        with self.journal() as j:
            one=j.prepare(**payload())
            j.transition(one,expected_phase='prepared',next_phase='mutating')
            j.transition(one,expected_phase='mutating',next_phase='committed',verification_sha256='a'*64)
            self.assertEqual(j.unresolved('example'),[])
            two=j.prepare(**payload(publication_number=2))
            self.assertNotEqual(one,two)

    def test_preparation_without_effects_may_be_aborted(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            j.transition(key,expected_phase='prepared',next_phase='aborted')
            self.assertFalse(j.unresolved('example'))
            j.prepare(**payload(publication_number=2))

    def test_reconciliation_is_explicit_not_automatic(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            j.transition(key,expected_phase='prepared',next_phase='mutating')
            j.transition(key,expected_phase='mutating',next_phase='needs_reconciliation',
                         reason_code='db_commit_unknown')
            with self.assertRaises(mod.PublicationJournalConflict):
                j.prepare(**payload(publication_number=2))
            # This library does not inspect Docker. `reconciled` is allowed only
            # after a trusted separate verifier supplies that conclusion.
            j.transition(key,expected_phase='needs_reconciliation',next_phase='reconciled',verification_sha256='b'*64)
            j.prepare(**payload(publication_number=2))

    def test_ambiguous_operation_cannot_be_closed_without_evidence_reference(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            j.transition(key,expected_phase='prepared',next_phase='mutating')
            with self.assertRaisesRegex(ValueError,'finalization_requires_verification_digest'):
                j.transition(key,expected_phase='mutating',next_phase='committed')
            j.transition(key,expected_phase='mutating',next_phase='needs_reconciliation',
                         reason_code='db_commit_unknown')
            with self.assertRaisesRegex(ValueError,'finalization_requires_verification_digest'):
                j.transition(key,expected_phase='needs_reconciliation',next_phase='reconciled')
            self.assertEqual(j.unresolved()[0]['phase'],'needs_reconciliation')
            j.transition(key,expected_phase='needs_reconciliation',next_phase='reconciled',
                         verification_sha256='c'*64)
            row=j.con.execute('SELECT verification_sha256 FROM stage_publication_operation_journal WHERE operation_id=?',
                              (key,)).fetchone()
            self.assertEqual(row[0],'c'*64)

    def test_stale_expected_transition_cannot_change_record(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            j.transition(key,expected_phase='prepared',next_phase='mutating')
            with self.assertRaisesRegex(mod.PublicationJournalConflict,'journal_phase_changed_or_missing'):
                j.transition(key,expected_phase='prepared',next_phase='aborted')
            self.assertEqual(j.unresolved('example')[0]['phase'],'mutating')

    def test_invalid_transitions_cannot_release_fence(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            with self.assertRaises(mod.PublicationJournalConflict):
                j.transition(key,expected_phase='prepared',next_phase='committed')
            with self.assertRaises(ValueError):
                j.transition(key,expected_phase='prepared',next_phase='needs_reconciliation')
            self.assertEqual(j.unresolved()[0]['phase'],'prepared')

    def test_bad_identity_inputs_are_rejected_before_storage(self):
        bad=[dict(project='https://example.invalid/not-a-project'),
             dict(project='OTHER/PROJECT'),dict(target='bad/name'),
             dict(target='cloudif-p10-p1-other'),dict(public_number=True),
             dict(publication_number=0),dict(kind='destroy'),
             dict(operation_id='secret-token')]
        with self.journal() as j:
            for patch in bad:
                with self.subTest(patch=list(patch)):
                    supplied=payload();supplied.update(patch)
                    with self.assertRaises(ValueError):j.prepare(**supplied)
            self.assertFalse(j.unresolved())

    def test_no_secret_payload_columns_or_noncanonical_sources(self):
        with self.journal() as j:
            cols={x[1] for x in j.con.execute('pragma table_info(stage_publication_operation_journal)')}
            for forbidden in ('env','token','secret','password','authorization','origin','url','request','response'):
                self.assertFalse(any(forbidden in name for name in cols),forbidden)
            j.prepare(**payload())
            self.assertNotIn('example.invalid',str(j.unresolved()))
            self.assertEqual(j.con.execute('PRAGMA synchronous').fetchone()[0],2) # FULL

    def test_no_partial_row_after_insert_conflict(self):
        with self.journal() as j:
            key=j.prepare(**payload())
            with self.assertRaises(mod.PublicationJournalConflict):
                j.prepare(**payload(publication_number=2))
            self.assertEqual(j.unresolved()[0]['operation_id'],key)
            self.assertEqual(j.con.execute('SELECT count(*) FROM stage_publication_operation_journal').fetchone()[0],1)

if __name__=='__main__':unittest.main()
