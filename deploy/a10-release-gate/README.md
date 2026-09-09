# A10 release-gate preparation

This directory intentionally contains **no promotion/apply script**. The A10 UX candidate was homologated only when `portal-current`, the `/srv/cloudif/lib` overlay, and `/srv/cloudif/lib/portal` came from the same source set. A partial application can therefore create a false candidate.

`build-candidate.sh` creates an immutable, hashed local bundle from the current Git commit. `preflight-target.sh` is the first allowed target-side step: it captures current/previous pointers, service metadata, hashes and restorable pre-state without changing pointers or restarting the service. `rollback.sh` refuses to run unless that complete pre-state and its hashes exist.

Promotion remains a separate, explicitly gated operation. Before any future cutover, the live Hospedagem inventory must be revalidated and the `R-REDES -> pfSense -> SSH` authentication gate must be accepted. The deployment must then atomically coordinate the app pointer with the shared lib/portal payload or introduce a separately reviewed pointer architecture; this preparation does not guess that mechanism.
