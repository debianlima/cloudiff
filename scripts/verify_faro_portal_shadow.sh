#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CONTRACT="$ROOT/config/faro-portal-shadow-contract.json"
PROFILE="$ROOT/config/faro-node-profile.json"

contract_check() {
  PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
contract = json.loads((root / 'config/faro-portal-shadow-contract.json').read_text())
profile = json.loads((root / 'config/faro-node-profile.json').read_text())

assert contract['contract_version'] == 1
assert contract['node'] == 'faro'
assert contract['mode'] == 'portal-shadow'
assert contract['contract_state'] == 'HOMOLOGADO_CI'
assert contract['live_state'] == 'NAO_VERIFICADO'
assert contract['probe'] == {'method': 'GET', 'path': '/', 'read_only': True}
assert contract['endpoint_sources'] == {
    'authoritative': 'CLOUDIFF_PORTAL_AUTHORITATIVE_URL',
    'shadow': 'CLOUDIFF_PORTAL_SHADOW_URL',
}

safety = contract['safety']
assert safety['parallel_only'] is True
assert safety['dedicated_non_authoritative_endpoint'] is True
assert safety['authoritative_untouched'] is True
assert safety['automatic_migration'] is False
assert safety['cutover_authorized'] is False
assert safety['contract_only_may_approve_live'] is False

for rel in contract['evidence'].values():
    assert (root / rel).is_file(), rel

assert profile['hostname'] == 'faro'
assert 'portal-host' in profile['capabilities']
assert profile['portal']['desired_host'] is True
assert profile['portal']['cutover'] == 'after-faro-onboarding-and-portal-shadow-gates'

required_live = {
    'endpoint-separation',
    'authoritative-before-after-unchanged',
    'shadow-readonly-root-probe',
    'frozen-surface-equivalence',
    'backend-navigation-and-actions',
    'telemetry-observed',
    'no-route-dns-lb-takeover',
    'explicit-cutover-authorization',
}
assert required_live.issubset(set(contract['live_gates']))
PY
}

normalize_origin() {
  python3 - "$1" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if u.scheme not in ('http', 'https') or not u.hostname:
    raise SystemExit(2)
port = u.port or (443 if u.scheme == 'https' else 80)
print(f'{u.scheme.lower()}://{u.hostname.lower()}:{port}')
PY
}

probe_get() {
  local url="$1"
  local body="$2"
  local code
  code=$(curl --fail-with-body --silent --show-error --location \
    --connect-timeout 5 --max-time 15 \
    --output "$body" --write-out '%{http_code}' \
    "${url%/}/")
  [[ "$code" =~ ^2[0-9][0-9]$ ]] || {
    echo "PORTAL_SHADOW_PRECHECK=FAIL reason=http-status status=$code" >&2
    return 31
  }
  [[ -s "$body" ]] || {
    echo "PORTAL_SHADOW_PRECHECK=FAIL reason=empty-body" >&2
    return 32
  }
  printf '%s' "$code"
}

contract_check

case "${1:---contract-only}" in
  --contract-only)
    echo 'PORTAL_SHADOW_CONTRACT=PASS LIVE=NAO_VERIFICADO CUTOVER=false'
    exit 0
    ;;
  --live-preflight)
    ;;
  *)
    echo 'usage: verify_faro_portal_shadow.sh [--contract-only|--live-preflight]' >&2
    exit 64
    ;;
esac

AUTHORITATIVE_URL="${CLOUDIFF_PORTAL_AUTHORITATIVE_URL:-}"
SHADOW_URL="${CLOUDIFF_PORTAL_SHADOW_URL:-}"
[[ -n "$AUTHORITATIVE_URL" ]] || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=missing-authoritative-url' >&2
  exit 20
}
[[ -n "$SHADOW_URL" ]] || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=missing-shadow-url' >&2
  exit 21
}

authoritative_origin=$(normalize_origin "$AUTHORITATIVE_URL") || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=invalid-authoritative-url' >&2
  exit 22
}
shadow_origin=$(normalize_origin "$SHADOW_URL") || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=invalid-shadow-url' >&2
  exit 23
}
[[ "$authoritative_origin" != "$shadow_origin" ]] || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=endpoint-not-separated' >&2
  exit 24
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Passive GET only. This script intentionally performs no POST, service
# management, DNS/LB/route mutation, container lifecycle action, or cutover.
status_before=$(probe_get "$AUTHORITATIVE_URL" "$tmp/authoritative-before.html")
status_shadow=$(probe_get "$SHADOW_URL" "$tmp/shadow.html")
status_after=$(probe_get "$AUTHORITATIVE_URL" "$tmp/authoritative-after.html")

# HTTP continuity is a preflight signal, not proof that the authoritative
# process/binding is unchanged; the latter remains a live evidence gate.
[[ "$status_before" == "$status_after" ]] || {
  echo 'PORTAL_SHADOW_PRECHECK=FAIL reason=authoritative-http-continuity' >&2
  exit 25
}

sha256sum "$tmp/authoritative-before.html" "$tmp/shadow.html" "$tmp/authoritative-after.html" \
  | sed "s#$tmp/##" >&2

echo "PORTAL_SHADOW_PRECHECK=PASS authoritative=$authoritative_origin shadow=$shadow_origin probe=GET:/ LIVE=NAO_VERIFICADO CUTOVER=false"
