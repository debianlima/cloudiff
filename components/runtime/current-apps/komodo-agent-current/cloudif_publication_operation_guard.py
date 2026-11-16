"""Fail-closed offline candidate for durable in-place CloudIFF publication.

Not wired into the production agent. The controller must supply independently
trusted current identity, cross-service lease and runtime evidence providers.
Caller-controlled HTTP payloads must never be used as those authorities.
"""
from collections.abc import Mapping

from cloudif_publication_recovery_journal import (
    PublicationRecoveryJournal, PublicationJournalConflict,
)


class PublicationGuardUnavailable(RuntimeError):
    """A trusted prerequisite or a provable result is missing."""


def _required(obj, name):
    fn = getattr(obj, name, None)
    if not callable(fn):
        raise PublicationGuardUnavailable('missing_' + name)
    return fn


def execute_fenced_publication(
    *, database_path, project, kind, public_number, publication_number,
    target, identity_authority, lease_authority, proof_authority,
    perform_mutation, operation_id=None,
):
    """Perform a release only with durable intent, lease, ACL and external proof.

    Identity: identity_authority.assert_current(project, kind)
    Lease: lease_authority.lease(project, public_number) -> context manager
      whose value supplies assert_current() and fences other services.
    Proof: proof_authority.attest(record, result) returns the SHA-256 digest
      of *independently observed* Docker+alias+database evidence.
      proof_authority.verify(record, phase, digest) checks that digest from
      an immutable protected store and returns literal True.
    Effects: perform_mutation(operation_id, lease) runs only after 'mutating'
      is durable. The integration MUST propagate the authority's fencing
      context to every external Docker/publisher effect and reject stale
      tokens. Result ok=True alone is NOT proof.

    A crash after mutating leaves a durable unresolved fence. Retries cannot
    repeat external effects without separate authenticated reconciliation.
    """
    check_identity = _required(identity_authority, 'assert_current')
    acquire_lease = _required(lease_authority, 'lease')
    attest = _required(proof_authority, 'attest')
    verify = _required(proof_authority, 'verify')
    if not callable(perform_mutation):
        raise PublicationGuardUnavailable('missing_perform_mutation')

    # No journal or side effect is created before the authority's lease.
    with acquire_lease(project, public_number) as lease:
        check_lease = _required(lease, 'assert_current')
        check_lease()
        check_identity(project, kind)
        with PublicationRecoveryJournal(
            database_path, evidence_verifier=verify
        ) as journal:
            key = journal.prepare(
                project=project, kind=kind, public_number=public_number,
                publication_number=publication_number, target=target,
                operation_id=operation_id,
            )
            try:
                check_lease()
                check_identity(project, kind)
            except BaseException:
                journal.transition(
                    key, expected_phase='prepared', next_phase='aborted',
                )
                raise
            # Persist the mutation intent before reaching Docker or Nginx.
            journal.transition(
                key, expected_phase='prepared', next_phase='mutating',
            )
            try:
                check_lease()
                check_identity(project, kind)
                result = perform_mutation(key, lease)
                if not isinstance(result, Mapping) or result.get('ok') is not True:
                    raise PublicationGuardUnavailable('unverified_mutation_result')
                check_lease()
                check_identity(project, kind)
                record = next(
                    (r for r in journal.unresolved(project)
                     if r['operation_id'] == key), None,
                )
                if record is None or record['phase'] != 'mutating':
                    raise PublicationGuardUnavailable('mutating_record_unavailable')
                digest = attest(record, result)
                journal.transition(
                    key, expected_phase='mutating', next_phase='committed',
                    verification_sha256=digest,
                )
                return result
            except BaseException:
                # Effects may already have run. Never report clean rollback.
                try:
                    journal.transition(
                        key, expected_phase='mutating',
                        next_phase='needs_reconciliation',
                        reason_code='effect_state_uncertain',
                    )
                except PublicationJournalConflict:
                    pass  # Original exception remains authoritative.
                raise
