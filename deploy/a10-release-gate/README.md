# A10 release-gate preparation

This directory intentionally contains **no promotion/apply script**. The A10 UX candidate was homologated only when `portal-current`, the `/srv/cloudif/lib` overlay, and `/srv/cloudif/lib/portal` came from the same source set. A partial application can therefore create a false candidate.

`build-candidate.sh` creates an immutable, hashed local bundle from the current Git commit. `preflight-target.sh` is the first allowed target-side step: it captures current/previous pointers, service metadata, hashes and restorable pre-state without changing pointers or restarting the service. `rollback.sh` refuses to run unless that complete pre-state and its hashes exist.

`cutover-readiness.sh <release-id> <archive-sha256> <source-commit>` is a read-only gate to run immediately before any human-authorized cutover. It refuses readiness when the staged archive hash/manifest diverges, when `PRESTATE.SHA256` is invalid, when `portal-current`, `portal-previous`, `/srv/cloudif/lib/portal`, the active app files or root lib overlay have drifted since preflight, or when the Portal service is not `active/running`. It does not create pointers, extract into live paths, restart services, or authorize promotion.

Promotion remains a separate, explicitly gated operation. Before any future cutover, the live Hospedagem inventory must be revalidated and the required network/authentication gates must be accepted. The deployment must then atomically coordinate the app pointer with the shared lib/portal payload or introduce a separately reviewed pointer architecture; this preparation does not guess that mechanism and still intentionally contains no promotion/apply script.
