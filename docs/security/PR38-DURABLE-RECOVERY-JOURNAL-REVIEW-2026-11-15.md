# PR38 — Durable publication recovery journal (review-only prototype)

## Scope and provenance

This is a **standalone, offline-only candidate** supporting T-003, based on PR38 commit `42774c37aac7ff5df6522ce9406fc8fdebe9a739`. It has **not been imported by the Komodo production agent**, and does not run Docker, query the live environment, or modify production databases. It is not an authorization to publish, merge or deploy.

## Failure model

The current PR38 compensates for ordinary exceptions after Docker network changes and a failed SQLite transaction, including cases with no previous production container. It cannot reconstruct an interrupted external workflow if the worker is killed after an alias switch or an ambiguous database commit. There is no distributed transaction between Docker and SQLite.

The candidate `cloudif_publication_recovery_journal.py` provides a **durable fail-closed fence**, not unattended recovery:

1. `prepare`: validate canonical project/target/kind, insert an operation with phase `prepared` and commit the intent **before any Docker/network mutation**. A SQLite partial unique index permits at most one unresolved operation per project, including across connections.
2. `mutating`: commit the phase change **before starting external effects**. If the worker crashes at any subsequent point, the phase remains open. Another promotion is blocked, rather than treating the prior job as complete.
3. `committed`: requires the caller to have completed the SQLite release transition, verified the network/containers and supplied a SHA-256 evidence reference. **The module does not perform that verification**, so production integration must supply an authenticated, separately reviewed reconciler.
4. `needs_reconciliation`: commit a reason code such as `db_commit_unknown` or `worker_crash`. A re-opened connection can report these records without printing request bodies, user secrets or environment values. A subsequent promotion remains blocked.
5. `reconciled`: additionally requires a SHA-256 verification reference, but the reference is **not proof by itself**. A trusted external inspector must validate the evidence contents and the actor before invoking the transition. `aborted` is possible only from `prepared`; it also requires external proof of no side effects before integration. This prototype does **not** implement or authorize automatic state clearing on startup.

The proposed index and SQLite `BEGIN IMMEDIATE` make *journal writes* atomic, while `PRAGMA synchronous=FULL` improves their durability. They do not guarantee atomic Docker or network operations. Races with another controller, Docker daemon restart, loss of network connectivity or power failure still require actual operating-system and Docker validation.

## Required reconciliation evidence

A future trusted read-only inspector should obtain: target and previous container IDs, image IDs, Docker health, network memberships and exact active public alias, publication number, candidate/deploy identities, SQLite current active release and `environment_digest` metadata (not values), and journal phase. It must distinguish:

| Journal/DB/runtime observation | Default decision |
| --- | --- |
| `prepared`, with independently proven no external side effects | Operator may approve cancellation |
| `mutating`, same target ID active and DB state committed | Require reconciliation and operator-reviewed finalize |
| `mutating`, DB still old and alias switched | Block, then choose compensating recovery after verification |
| `mutating`, first Pn has no previous and alias remains | Block, verify alias-only retraction and preserve Hn |
| `needs_reconciliation`, partial/inconsistent or unavailable evidence | Keep blocked; no automatic retry |
| Previous Pn absent/unhealthy or unknown network options | Keep blocked; owner-led incident response |

## Open engineering gates

- Link `prepare`/phase transitions to the actual release and manual activation handlers in code review, **before** Docker effects. The project-specific key must protect both handlers and any other route changing the same active alias. Decide how to prevent another process bypassing the fence.
- Add verified reconciliation and a signed or otherwise trusted approval record before allowing `needs_reconciliation → reconciled`. The transition API enforces a syntactically valid `verification_sha256` for `committed`/`reconciled`, but does not authenticate it; trusted review of the referenced evidence is mandatory. The API is **not by itself an authorization control**.
- Test power loss, ambiguous COMMIT, Docker daemon failure, multi-process interleavings, foreign aliases, static IP/network options and scheduler restarts on an isolated disposable Docker environment owned by the infrastructure team.
- Preserve same Hn/Pn container ID, new runtime environment effectiveness, previous Pn stop, first-Pn alias rollback and manual activation. Never use an uncontrolled production network as a test fixture.
- P0 Git origins with credentials, approved backup/restore, OpenBao, owner G0–G5 and independent aud-01/dev-02/surface-01 acceptance are blocking release gates.

## Prototype evidence

The 13 deterministic offline tests use temporary SQLite databases: persistence across connection restart, replay/idempotency, competing connection fence, crash phase retention, separate projects, accepted and forbidden transitions, metadata validation, and no secret-bearing columns. They are not a Docker E2E or an implementation of automatic crash recovery.
