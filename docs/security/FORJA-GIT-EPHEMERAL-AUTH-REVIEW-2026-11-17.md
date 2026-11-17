# Forja Git transport — preventive credential safety patch

**Status:** source-only review, not deployed; **The review branch is stacked on draft PR #43**, whose source-test scope fix and regenerated technical catalogs are independently CI-green. Main is the eventual target only after PR #43 is reviewed/merged. No production credentials or Git `.git/config` files were accessed, changed or copied during development. This change does **not** contain or revoke historical exposed credentials.

## Code and threat model

CloudIFF Forja has CLI fallbacks for Git-based file commits and repository bundle import. Previously, selected fallbacks constructed URLs containing `username:token@host` and could leave credential-bearing remotes inside cloned `.git/config`; Git errors could also expose URL userinfo, query secrets, SCP-like userinfo, or HTTP Authorization values. A scoped HTTP header alone is insufficient: Git/curl may follow an HTTP 302 to a *different repository on the same origin* and send the scoped header there.

In both mirrored runtime sources (`components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py` and `components/runtime/usr/local/sbin/cloudif-forja-agent.py`), the Git network operations now use:

- A clean remote URL with **no embedded userinfo**, plus process-only environment `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` scoping `http.<exact repo URL>.extraHeader` to the intended Forgejo repository, and `GIT_TERMINAL_PROMPT=0`.
- Process-only `http.followRedirects=false` to **reject even same-origin redirects** where Git/curl would otherwise forward a Basic authorization header to another repository. This requires the owner to configure a *final, canonical Forgejo URL*; changing a Git URL in an uncontrolled way or bypassing TLS is not an acceptable workaround.
- All intended Git clone/fetch/ls-remote/push operations in the bundle-import fallback pass the ephemeral auth environment. The obsolete credential-bearing URL constructor is removed from both runtime mirrors.
- Returned subprocess errors are sanitized to mask configured token values and encoded variants, HTTP URL authority/query/fragment credentials, Authorization Basic/Bearer values, and credential-like malformed SCP remotes. No raw secrets should be written to PGH notes, logs or error payloads.

## Validation and review limitations

Nine independent test modules in `portal/tests/test_pgh_forja_*.py` use **synthetic tokens only** and exercise static source contracts, mirror byte-parity, scoped Git config behavior and a localhost fake HTTP redirect receiving no credential on the second URL when redirects are blocked. The tests run under the official `scripts/test.sh` discovery rather than a separate unverified folder. They do not contact Forgejo, production Docker or institutional networks.

Residual threats requiring independent review include: same-UID environment inspection while Git subprocesses run; legitimate Forgejo URL rewrites and redirects breaking operations (fail closed); unvalidated operation ownership or broad Git permissions upstream; any other existing Git callers not routed through the new wrapper; and browser/API error paths outside Git subprocesses. Only a legitimate owner can verify the final canonical Forgejo URL, authorize the service identity with minimum privilege, package/deploy the correct mirrored runtime and perform a rollback-enabled canary.

## Release gates and incident containment

This PR is **preventive source hardening**. The existing **22 Git origin configurations with embedded credentials (21 Forja, 1 Hospedagem)** are an active P0 and require **owner-controlled containment, real credential rotation/revocation, and independent zero-exposure audit**; no code-level test can replace that. G0 authenticated owner and change lock, G1 verified institutional backups/volume restore, G2 productive OpenBao secret broker/ACL/TTL, G3 isolated source+Docker end-to-end, G4 credential rotation and G5 independent audit all remain mandatory for production rollout. Do not merge/deploy automatically or change Git remotes from an unprivileged session.

## PR sequencing and catalog parity

The standalone security change contains two mirrored Forja runtime files, nine test modules, and this documentation. It was stacked on PR #43 rather than duplicating the baseline async publication test fix and its generated catalogs. After PR #43 merges, rebase/retarget this PR and revalidate regenerated catalogs on the exact resulting main HEAD; no authorization to merge either draft is implied.

### TLS-only credential delivery

The ephemeral Basic authorization helper now **rejects HTTP**, userinfo, query and fragment in the configured `FORGEJO_URL`. Only an HTTPS canonical URL may carry the process-scoped Git Basic header. This deliberately fails closed for internal plaintext HTTP endpoints; an authorized owner must supply a valid HTTPS Forgejo ingress with matching certificate and no redirects before rollout. The direct loopback Git HTTP redirect fixture remains synthetic and never uses production credentials.
