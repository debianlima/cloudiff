"""Opt-in, fail-closed publication journal bridge for the Komodo runtime.

NOT a production-ready verifier or multi-host lease. Under strict mode this
class must be supplied trusted evidence callbacks by the hosting controller;
no user request can provide the callbacks. Nothing here performs Docker I/O.
"""
import fcntl
import os
import re
import stat
from pathlib import Path

from cloudif_publication_recovery_journal import PublicationRecoveryJournal


class PublicationEffectGateUnavailable(RuntimeError):
    """An operation cannot safely enter the external-effects phase."""


class DisabledPublicationGate:
    """Compatibility mode only. It does not claim crash-safe publication."""
    def __enter__(self):
        return self

    def finish(self):
        return None

    def __exit__(self, *_):
        return False


def _trusted_directory(path):
    parent = Path(path)
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        raise PublicationEffectGateUnavailable('untrusted_lock_directory')
    if st.st_uid not in (os.geteuid(), 0) or st.st_mode & 0o022:
        raise PublicationEffectGateUnavailable('untrusted_lock_directory')
    return parent


class StrictPublicationGate:
    """Local-host file lease plus a durable SQLite alias/project fence.

    The production actor must separately guarantee all Docker/Komodo agents
    use this same guard; local flock alone does not fence remote hosts.
    """

    def __init__(self, *, db_path, lock_dir, project, kind, public_number,
                 publication_number, target, evidence_provider, evidence_verifier):
        if not callable(evidence_provider) or not callable(evidence_verifier):
            raise PublicationEffectGateUnavailable('trusted_evidence_provider_missing')
        if (not db_path or not lock_dir or
                not os.path.isabs(os.fspath(db_path)) or
                not os.path.isabs(os.fspath(lock_dir))):
            raise PublicationEffectGateUnavailable('absolute_private_state_paths_required')
        self.db_path = os.fspath(db_path)
        self.lock_dir = os.fspath(lock_dir)
        self.project = project
        self.kind = kind
        self.public_number = public_number
        self.publication_number = publication_number
        self.target = target
        self.evidence_provider = evidence_provider
        self.evidence_verifier = evidence_verifier
        self.lock_fd = None
        self.journal = None
        self.operation_id = None
        self.done = False

    def __enter__(self):
        try:
            base = _trusted_directory(self.lock_dir)
            if type(self.public_number) is not int or not 0 < self.public_number < 10**10:
                raise PublicationEffectGateUnavailable('invalid_public_alias')
            lock_path = base / f'publication-{self.public_number}.lock'
            flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
            self.lock_fd = os.open(lock_path, flags, 0o600)
            lock_stat = os.fstat(self.lock_fd)
            if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.geteuid():
                raise PublicationEffectGateUnavailable('untrusted_lock_file')
            os.fchmod(self.lock_fd, 0o600)
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PublicationEffectGateUnavailable('publication_alias_busy') from None
            self.journal = PublicationRecoveryJournal(self.db_path,
                                                       evidence_verifier=self.evidence_verifier)
            self.operation_id = self.journal.prepare(
                project=self.project, kind=self.kind,
                public_number=self.public_number,
                publication_number=self.publication_number, target=self.target)
            # This durable commit precedes every external Docker/network effect.
            self.journal.transition(self.operation_id,
                                    expected_phase='prepared', next_phase='mutating')
            return self
        except Exception:
            self._close()
            raise

    def finish(self):
        if self.done or self.journal is None or self.operation_id is None:
            raise PublicationEffectGateUnavailable('publication_gate_not_running')
        # The caller controls no evidence: the hosting controller's authenticated
        # evidence provider must independently inspect SQLite and Docker state.
        try:
            digest = self.evidence_provider({
                'operation_id': self.operation_id,
                'project': self.project,
                'kind': self.kind,
                'public_number': self.public_number,
                'publication_number': self.publication_number,
                'target_container': self.target,
            })
        except Exception:
            raise PublicationEffectGateUnavailable('trusted_evidence_unavailable') from None
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise PublicationEffectGateUnavailable('trusted_evidence_invalid')
        self.journal.transition(self.operation_id, expected_phase='mutating',
                                next_phase='committed', verification_sha256=digest)
        self.done = True

    def __exit__(self, *_):
        try:
            if not self.done and self.journal is not None and self.operation_id:
                # A failed/cancelled request may have changed Docker and DB.
                # Never reopen the alias without an independent reconciliation.
                try:
                    self.journal.transition(self.operation_id, expected_phase='mutating',
                                            next_phase='needs_reconciliation',
                                            reason_code='incomplete_effect')
                except Exception:
                    # The committed `mutating` phase itself is a durable fence.
                    # Do not try to send a second HTTP response when the handler
                    # already returned an error; retry/reconciliation stays blocked.
                    pass
        finally:
            self._close()
        return False

    def _close(self):
        if self.journal is not None:
            try:
                self.journal.close()
            finally:
                self.journal = None
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self.lock_fd)
                self.lock_fd = None


def make_publication_gate(*, mode, db_path, lock_dir, project, kind, public_number,
                          publication_number, target, evidence_provider=None,
                          evidence_verifier=None):
    """Reject unknown settings, never silently downgrade strict to disabled."""
    if mode == 'disabled':
        return DisabledPublicationGate()
    if mode != 'strict':
        raise PublicationEffectGateUnavailable('unknown_publication_journal_mode')
    return StrictPublicationGate(
        db_path=db_path, lock_dir=lock_dir, project=project, kind=kind,
        public_number=public_number, publication_number=publication_number,
        target=target, evidence_provider=evidence_provider,
        evidence_verifier=evidence_verifier)
