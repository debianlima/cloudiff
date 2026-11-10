# CloudIFF Taiga identity hardening

Two small derivative images keep the upstream/custom Taiga images intact while
fixing shared-workstation identity isolation and pre-provisioned user binding.

- `back-oidc`: OIDC resolves stable `sub` and institutional username before
  e-mail, updates a `@pending.cloudif.invalid` placeholder on first real login, and
  requests `prompt=login` from Authentik.
- `front-session`: only authentication keys (`token`, `refresh`, `userInfo`)
  are redirected from persistent `localStorage` to `sessionStorage`.
  Other Taiga preferences remain persistent.

- `current-apps/taiga-current`: canonical compose/gateway baseline; `/cloudif-enter/<slug>` clears Taiga browser auth before fresh OIDC.

## Shared-workstation hardening release

The next immutable derivative images are:

- `cloudif-local/taiga-back-oidc:6.10.2-c623b753-r6-identity`: keeps `prompt=login` and rejects an OIDC `sub`/username already bound to a different Taiga user instead of silently accepting drift.
- `cloudif-local/taiga-front-oidc:6.10.3-c623b753-r4-session`: keeps Taiga auth in `sessionStorage` and uses a non-secret browser session generation signal so a new authenticated tab invalidates older authenticated tabs on the same workstation.

The gateway canonicalizes both `/entrar-cloudiff` and `/cloudif-enter/<slug>` through a local Taiga-session reset before OIDC and marks OIDC/private-media responses as non-cacheable. Production must build these tags as new images; previous immutable tags must not be overwritten.
