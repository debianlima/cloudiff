# Komodo PGH service-user manifest — fail-closed structural type validation

**Date:** 2026-11-17. **Scope:** source and synthetic tests only. No Komodo API call, service account, real key, secret broker operation, access-control mutation, Docker process or production deployment occurred.

## Why this change is necessary

An independent `surface-01` review of draft PR48 (aud-01 field allowlist) found the manifest validator raised Python exceptions on 10 of 17 malformed nested JSON values, and silently accepted `key_ttl_hours_max: true` and a duplicated agent identifier. The validator must return deterministic errors on malformed data without accepting ambiguous types or authorizing operations.

This patch comes from `evidencias/surface-01/pr48-schema-20261117/SURFACE-01-PR48-TYPE-FAIL-CLOSED.patch`, SHA-256 `089170d3486a6097c0d2c7ad4130b3d175b5b22c2446db639031342331378287`, independently tested and applied to exact PR48 head `689957c926b237b2a11ef235e6f1831792c8e934`. It preserves the original allowlist, pending-only account policy, and negative authorization claims.

## Behavior

- Return `invalid_manifest_structure` before dereferencing malformed `target_scope`, `agent_credential_model`, `elevated_operations` or `activation_checks` values.
- Accept denied privileges only as a list of strings containing the required denyset, never converting malformed structures to a set.
- Accept agent identifiers only as a list of strings with exact authorized set and count; duplicate codes fail closed.
- TTL must have **exact Python type `int`**, range 1–24; boolean `true` is not an integer TTL for this policy.

The manifest stays `PENDING_ADMIN_CREATION`. The CLI must report `authenticated_to_komodo:false`, `service_user_created:false`, and `credentials_processed:false` for the pending plan; schema validation is not proof of account creation.

## Evidence

- Original 20 offline PR48 policy tests: **20/20 PASS**.
- `portal/tests/test_pgh_pr48_komodo_schema_types.py`: 17 separately discoverable malformed-value cases, valid-pending check and original 20-case regression: **19/19 PASS**.
- `scripts/validate-repository.py`: `ok:true`, `errors:[]`.
- Full four-shard Portal suite: **329 + 306 + 315 + 399 = 1,349/1,349 PASS**. Four generated catalogs byte-identical after regeneration. No Docker or Komodo API access.

## Operational release gates

**G0** legitimate Komodo admin identity and change lock; **G1** institutional PostgreSQL dump, roles and volumes isolated recovery evidence; **G2** production OpenBao/approved broker with `secret_ref`, TTL, ACL and revocation; **G3** negative ACL/config secret-sanitization and real runtime E2E; **G4** containment, rotation and revocation of 22 credential-bearing Git origin files; **G5** independent audit. The service user remains uncreated and no API keys may be issued by this patch. User approval alone does not establish runtime permissions or restoration proof.
