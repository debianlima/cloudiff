# CloudIFF T-002 — R3 ACL Revision/Concurrency Sandbox Prototype

Date: 2026-11-14 (UTC); PGH agent `desenvolvimento/cloudiff/dev-01`.

**CANDIDATE FOR INDEPENDENT REVIEW ONLY. NOT wired into production, not a deployable patch. No migration or Komodo integration.**

## Files

- `acl_revision_gate.py`: per-project `fcntl.flock` serialization, monotonic ACL revision, deterministic request digest, stale replay/conflict rejection, atomic state files with `fsync`/`os.replace`, fail closed on applying/ambiguous external result.
- `portal_acl_revision.py`: isolated SQLite schema example with revision table, triggers for owner/ACL changes and transactionally coherent read-only snapshot. The `install_disposable_schema` function is *not* authorized for the live database.
- `test_acl_revision_gate.py`: 16 synthetic checks including two-process contention; stale revisions never invoke fake Mongo callback.
- `test_portal_acl_revision.py`: 9 synthetic SQLite checks for revision increments, idempotency, rollback, legacy seed and snapshot integration.
- `test_synthetic_acl_flow.py`: 6 synthetic simulated Portal -> v4 service-auth -> revision gate -> fake Komodo integration checks; includes negative authorization and Forgejo preserve.

## Test commands (run on LabIFF; no remote calls)

```sh
cd /srv/mcp-workspace/cloudiff-admin/agent-worktrees/dev-01/t002-r3-sandbox
PYTHONDONTWRITEBYTECODE=1 python3 -B test_acl_revision_gate.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -B test_portal_acl_revision.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -B test_synthetic_acl_flow.py -q
```

Result 2026-11-14: **16 + 9 + 6 = 31/31 PASS.** Python syntax compilation PASS. No credentials, user identities, production database writes, API, SSH to external hosts, Docker or Mongo involved in these tests.

## Confirmed live-schema compatibility (read-only)

- Hospedagem `portal.db`: SQLite WAL, `PRAGMA quick_check=ok`; tables `projects.slug, owner` and `project_acl.slug, subject_type, subject` exist.
- No live `project_acl_revisions` table or prototype triggers exist. This migration has **not** been applied.
- Remote production source remains v4 baseline, not R3 prototype.

## Proposed integration contract (MUST be reviewed, not yet implemented)

1. Canonical Portal source: protected migration adds revision table/triggers and seeds existing projects with baseline revision. Rollout requires real backup/restore smoke and transactional migration validation. Legacy ACL snapshots must be preserved and manually reconciled before first authoritative replay.
2. Every ACL snapshot carries `project`, verified `owner`, explicit `acl`, `acl_revision` and target/resource metadata. Revision is assigned by canonical Portal DB, never arbitrarily by the HTTP request sender. Project target changes must increment a revision as well, or use a separate monotonic target generation.
3. Service caller authentication from v4 is an independent gate. `verified_source='portal'|'replay'` in prototype is an **out-of-band trusted parameter**, not a credential or a claim made by request payload. Implementation must prove issuer identity and revision integrity on every entry point.
4. Helper obtains exclusive project lock *before* checking state and applying Mongo permissions; a lower revision is rejected before any side effects. Equal revision is replayable only if digest matches. `replay` cannot advance revision. `applying` states require a designated manual recovery procedure.
5. State updates are atomic and private, but cross-system atomicity with Mongo and terminal creation cannot be guaranteed by file locking alone. Membership reconciliation creates terminals AFTER the existing helper returns; that flow also needs a revision fence or a shared project-level lock covering all permissions/terminal side effects.
6. Existing timer and Portal publisher, project ensure producer, direct authz-sync and membership endpoints require coordinated release; existing 26 snapshots without ACL/revision are not silently migrated/replayed. Any attempt to use old JSON must stop safely.
7. Race/crash recovery: `applying` journal deliberately blocks automatic recovery. Define restore/compensation workflow for uncertain partial writes; do not automatically delete permissions or drop users. Cross-host clocks must not be used as revision counters.
8. Production rollout requires authenticated clients, TLS or trusted transport, RBAC, validated backup and restore, rollback, branch reviews/CI, E2E tests with Komodo Mongo/terminals/negative access in isolated environment and audit approval. No rollout in this iteration.

## Known limitations of the prototype

- `portal_acl_revision.py` uses minimal schema fixtures; production migrations and owner/ACL update call sites have not been rehearsed with a full copy of the actual database (and must not be performed on live data without change control).
- Revision numbers are database-local; in a multi-master or restore scenario, epochs/generations must be managed. Merely incrementing an integer is not a complete distributed authorization protocol.
- `acl_revision_gate.py` serializes local helper operations only; it does not cover Mongo transactions, other Komodo mutation routes, the post-helper terminal lifecycle, or multiple nodes writing the same project without shared coordination.
- State contains usernames/groups in a trusted on-disk ACL snapshot, hence production path must be protected with least privilege and never exported to Atlas/MD or GitHub. Tests only use fictitious principals.
- This prototype is not an installable CloudIFF package and should remain in LabIFF until reviewed by `aud-01` and `dev-02`.

## PGH handoff

Evidence: `/srv/mcp-workspace/cloudiff-admin/evidencias/PGH-DEV01-T002-R3-SANDBOX-20261114.md`. R3 still `in_progress`, not production-complete.

## Updated source-only review, 18/11/2026

This versioned research candidate lives under `portal/tools/acl_r3_research/`, with
`portal/tests/test_dev01_acl_r3_guard_research.py` and
`portal/tests/test_dev01_acl_r3_portal_research.py`. It is **not imported by the
Portal or Komodo runtime**. Run synthetic tests from repository root with:

```sh
python3 -m unittest discover -s portal/tests -p 'test_dev01_acl_r3_*research.py'
```

The older six end-to-end simulated auth-v4 tests were **intentionally not copied**
from the LabIFF sandbox because they import an absolute private path
`t002-auth-v4/cloudif-komodo-agent.py` that is not present in the canonical
CloudIFF source. Reintroduce this coverage only once the real authenticated
endpoint/service principal is source-versioned and reviewed. Do **not** paste
mock bearer tokens into a live worker or claim these tests cover authentication.

Additional fail-closed research guards (including world-readable files): unknown request keys are rejected
(before persisting arbitrary credentials in request snapshots), and private
state/lock files reject hardlinks, unsafe mode and foreign UID. These protections
are **not** a substitute for secure `openat`/dirfd traversal, inode recheck and
trusted ancestor validation. The prototype's `verified_source` string must be
derived by a separate authenticated transport; it is not an authorization token.

**Do not merge/integrate into production yet.** Missing requirements: canonical
Portal schema migration with tested rollback (26 historical snapshots), epoch
after restore and cross-host shared locking, trustworthy publisher identity,
Komodo/Mongo effective ACL and terminal lifecycle fenced in the same revision,
provenance/revocation/negative tests, OpenBao secret_ref/TTL, G0–G5 and
independent AUD01 review. The generated technical catalog includes the
`project_acl_revisions` SQL declaration from this research file, which is
*not a claim that this table exists in production*.
