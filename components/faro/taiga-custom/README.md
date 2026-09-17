# CloudIFF Taiga identity hardening

Two small derivative images keep the upstream/custom Taiga images intact while
fixing shared-workstation identity isolation and pre-provisioned user binding.

- `back-oidc`: OIDC resolves stable `sub` and institutional username before
  e-mail, updates a `@cloudiff.invalid` placeholder on first real login, and
  requests `prompt=login` from Authentik.
- `front-session`: only authentication keys (`token`, `refresh`, `userInfo`)
  are redirected from persistent `localStorage` to `sessionStorage`.
  Other Taiga preferences remain persistent.
