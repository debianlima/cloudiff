---
name: cloudiff-safe-release
versao: 1.0.0
tipo: dominio
description: Apply any CloudIFF production change through a reversible release, isolated candidate, explicit validation, promotion,
  smoke tests, and evidence. Use for systemd, portal, proxy, MCP, database, container, or configuration changes on CloudIFF
  hosts.
origem:
  tipo: aprendizado-preexistente-cloudiff
  release_operacional: cloudiff-project-0.1.1-20260824
  sha256_original: d53483b97e8251700dcc15afa783421f3cac1167b7303acc21d1f30a0a53ff4a
escopo: release, promoção, cutover, rollback e evidência operacional CloudIFF
portao: dry-run; candidate isolada; smoke pós-deploy; rollback integral funcional
---
# CloudIFF Safe Release
1. Inventory the active service, port, unit, environment file, data path, symlink, dependencies, and current health.
2. Create `/srv/cloudif/releases/<release-id>/pre-state` and a syntactically valid `rollback.sh` before changing production.
3. Never put passwords, bearer tokens, private keys, cookies, or full environment files in reports or command output.
4. Build a new immutable application directory. Do not overwrite the active release.
5. Compile, lint, and validate configuration before promotion.
6. Run a candidate on an unused loopback port or copied database. Verify the candidate PID owns the test port.
7. Promote atomically with a symlink or replace-one-file operation. Restart only the affected service.
8. Validate health, authorization failures, authorized success, database integrity, dependent services, public edge behavior, and the coordinated smoke suite.
9. On any critical failure, run rollback immediately, validate the restored service, and record the failed release honestly.
10. Homologate only after repeated successful checks. Preserve active and previous pointers; never delete the rollback of the current release.
