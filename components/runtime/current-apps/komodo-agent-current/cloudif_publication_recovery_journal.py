"""Offline-only candidate for durable CloudIFF publication operation fencing.

This module is not integrated into a live publication path. It records *only*
non-secret operation metadata and rejects concurrent/ambiguous retries.
No Docker, network, credential or service actions occur here.
"""
import re
import sqlite3
import uuid
from datetime import datetime, timezone

_ACTIVE = ('prepared', 'mutating', 'needs_reconciliation')
_FINAL = ('committed', 'aborted', 'reconciled')
_ALLOWED = {
    'prepared': {'mutating', 'aborted', 'needs_reconciliation'},
    'mutating': {'committed', 'needs_reconciliation'},
    'needs_reconciliation': {'reconciled'},
}


class PublicationJournalConflict(RuntimeError):
    """The project has an unresolved operation or an invalid state transition."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _validate_identity(project, kind, public_number, publication_number, target):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', str(project)):
        raise ValueError('invalid_project')
    if kind not in ('production_release', 'manual_activation'):
        raise ValueError('invalid_operation_kind')
    if type(public_number) is not int or public_number < 1:
        raise ValueError('invalid_public_number')
    if type(publication_number) is not int or publication_number < 1:
        raise ValueError('invalid_publication_number')
    # Only a canonical local container name, never an arbitrary origin/URL.
    if not re.fullmatch(rf'cloudif-p{public_number}-(?:d\d+-web|p\d+-publication-web)', str(target)):
        raise ValueError('invalid_target_container')


class PublicationRecoveryJournal:
    """Durable SQLite phase fence; caller must reconcile externally, never guess.

    SQLite WAL + FULL applies only to this connection. All mutations use BEGIN
    IMMEDIATE and commit before the caller starts the next external phase.
    """
    def __init__(self, db_path, *, evidence_verifier=None):
        # Only the trusted hosting controller may inject an independently
        # authenticated local verifier. Without it, terminal successes are
        # forbidden regardless of SHA-256 formatting.
        if evidence_verifier is not None and not callable(evidence_verifier):
            raise TypeError('invalid_evidence_verifier')
        self._evidence_verifier = evidence_verifier
        self.con = sqlite3.connect(str(db_path), timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA busy_timeout=30000')
        self.con.execute('PRAGMA journal_mode=WAL')
        self.con.execute('PRAGMA synchronous=FULL')
        self.con.execute('''CREATE TABLE IF NOT EXISTS stage_publication_operation_journal (
            operation_id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            kind TEXT NOT NULL,
            public_number INTEGER NOT NULL,
            publication_number INTEGER NOT NULL,
            target_container TEXT NOT NULL,
            phase TEXT NOT NULL CHECK(phase IN (
                'prepared','mutating','needs_reconciliation','committed','aborted','reconciled')),
            reason_code TEXT NOT NULL DEFAULT '',
            verification_sha256 TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        self.con.execute('''CREATE UNIQUE INDEX IF NOT EXISTS
            idx_pubjournal_one_open_per_project
            ON stage_publication_operation_journal(project)
            WHERE phase IN ('prepared','mutating','needs_reconciliation')''')
        # The public number identifies the network alias globally. Another
        # project must not change it while an operation is unresolved.
        self.con.execute('''CREATE UNIQUE INDEX IF NOT EXISTS
            idx_pubjournal_one_open_per_public_number
            ON stage_publication_operation_journal(public_number)
            WHERE phase IN ('prepared','mutating','needs_reconciliation')''')
        self.con.commit()

    def close(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _begin(self):
        self.con.execute('BEGIN IMMEDIATE')

    def prepare(self, *, project, kind, public_number, publication_number, target, operation_id=None):
        _validate_identity(project, kind, public_number, publication_number, target)
        operation_id = str(operation_id or uuid.uuid4().hex)
        if not re.fullmatch(r'[0-9a-f]{32}', operation_id):
            raise ValueError('invalid_operation_id')
        values=(project,kind,public_number,publication_number,target)
        try:
            self._begin()
            prior=self.con.execute('SELECT * FROM stage_publication_operation_journal WHERE operation_id=?',
                                   (operation_id,)).fetchone()
            if prior is not None:
                old=tuple(prior[k] for k in ('project','kind','public_number','publication_number','target_container'))
                if prior['phase']=='prepared' and old==values:
                    self.con.commit()
                    return operation_id  # Safe idempotent retry before external effects.
                raise PublicationJournalConflict('operation_id_already_advanced_or_reused')
            busy=self.con.execute('''SELECT project,public_number FROM stage_publication_operation_journal
                                     WHERE (project=? OR public_number=?)
                                       AND phase IN ('prepared','mutating','needs_reconciliation')''',
                                  (project,public_number)).fetchone()
            if busy is not None:
                raise PublicationJournalConflict('unresolved_project_operation' if busy['project']==project
                                                 else 'unresolved_public_alias')
            stamp=_now()
            self.con.execute('''INSERT INTO stage_publication_operation_journal(
                operation_id,project,kind,public_number,publication_number,target_container,
                phase,reason_code,created_at,updated_at) VALUES (?,?,?,?,?,?,'prepared','',?,?)''',
                (operation_id,*values,stamp,stamp))
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise
        return operation_id

    def transition(self, operation_id, *, expected_phase, next_phase, reason_code='', verification_sha256=''):
        if next_phase not in _ALLOWED.get(expected_phase, set()):
            raise PublicationJournalConflict('invalid_journal_transition')
        if not re.fullmatch(r'[0-9a-f]{32}', str(operation_id)):
            raise ValueError('invalid_operation_id')
        if reason_code and not re.fullmatch(r'[a-z0-9_]{1,48}', reason_code):
            raise ValueError('invalid_reason_code')
        if next_phase=='needs_reconciliation' and not reason_code:
            raise ValueError('reconciliation_requires_reason_code')
        if next_phase in ('committed','reconciled'):
            if not re.fullmatch(r'[0-9a-f]{64}', verification_sha256):
                raise ValueError('finalization_requires_verification_digest')
        elif verification_sha256:
            raise ValueError('verification_digest_for_nonterminal_phase')
        # Never run an external or potentially slow evidence verifier under a
        # SQLite write lock: it blocks unrelated projects and can deadlock on
        # a re-entrant verifier. Read a stable journal snapshot in autocommit,
        # verify that snapshot, and then compare it again under BEGIN IMMEDIATE.
        # The controller must ALSO own a cross-service alias/operation lease
        # while observing Docker/runtime; SQLite alone cannot fence Docker.
        select_sql=('SELECT operation_id,project,kind,public_number,publication_number, '
                    'target_container,phase,reason_code,verification_sha256,updated_at '
                    'FROM stage_publication_operation_journal '
                    'WHERE operation_id=? AND phase=?')
        prior=None
        if next_phase in ('committed','reconciled'):
            if self._evidence_verifier is None:
                raise PublicationJournalConflict('evidence_verifier_unavailable')
            prior=self.con.execute(select_sql,(operation_id,expected_phase)).fetchone()
            if prior is None:
                raise PublicationJournalConflict('journal_phase_changed_or_missing')
            try:
                verified=self._evidence_verifier(dict(prior),next_phase,verification_sha256)
            except Exception:
                raise PublicationJournalConflict('evidence_verification_failed') from None
            if verified is not True:
                raise PublicationJournalConflict('evidence_verification_failed')
        try:
            self._begin()
            current=self.con.execute(select_sql,(operation_id,expected_phase)).fetchone()
            if current is None:
                raise PublicationJournalConflict('journal_phase_changed_or_missing')
            if prior is not None and dict(current)!=dict(prior):
                raise PublicationJournalConflict('journal_changed_during_verification')
            result=self.con.execute('''UPDATE stage_publication_operation_journal
                SET phase=?,reason_code=?,verification_sha256=?,updated_at=?
                WHERE operation_id=? AND phase=?''',
                (next_phase,reason_code,verification_sha256,_now(),operation_id,expected_phase))
            if result.rowcount!=1:
                raise PublicationJournalConflict('journal_phase_changed_or_missing')
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def unresolved(self, project=None):
        if project is not None and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', str(project)):
            raise ValueError('invalid_project')
        sql='''SELECT operation_id,project,kind,public_number,publication_number,
                     target_container,phase,reason_code,verification_sha256,created_at,updated_at
               FROM stage_publication_operation_journal
               WHERE phase IN ('prepared','mutating','needs_reconciliation')'''
        params=()
        if project is not None:
            sql+=' AND project=?';params=(project,)
        sql+=' ORDER BY created_at,operation_id'
        return [dict(r) for r in self.con.execute(sql,params)]
