#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
[[ "$TENANT" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || {
  echo "Tenant inválido: $TENANT" >&2
  exit 2
}

ENV_FILE="${CLOUDIF_NPM_PUBLISHER_ENV:-/etc/cloudif/npm-publisher-client.env}"
DOMAIN="${CLOUDIF_DOMAIN:-cloudiff.duckdns.org}"
HOST="${TENANT}.${DOMAIN}"
PUBLIC_URL="https://${HOST}/project/default"
PUBLISHER_URL="${CLOUDIF_TENANT_PUBLISHER_URL:-http://10.62.91.3/tenant}"
PUBLISHER_HOST="${CLOUDIF_TENANT_PUBLISHER_HOST:-cloudif-publisher.internal}"
WAIT_SECONDS="${CLOUDIF_TENANT_CERTIFICATE_WAIT_SECONDS:-900}"
[[ "$WAIT_SECONDS" =~ ^[0-9]+$ ]] || WAIT_SECONDS=900

TOKEN="$(grep -E '^NPM_PUBLISHER_TOKEN=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
[ -n "$TOKEN" ] || {
  echo "NPM publisher token ausente em $ENV_FILE" >&2
  exit 1
}

REQUEST_JSON="$(python3 -c 'import json,sys; print(json.dumps({"tenant":sys.argv[1]}))' "$TENANT")"
RESPONSE_FILE="$(mktemp)"
ERROR_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE" "$ERROR_FILE"' EXIT

curl -fsS \
  --retry 5 --retry-delay 3 --retry-all-errors \
  --connect-timeout 8 --max-time 240 \
  -H 'Content-Type: application/json' \
  -H "Host: $PUBLISHER_HOST" \
  -H "X-CloudIF-Token: $TOKEN" \
  --data "$REQUEST_JSON" \
  --output "$RESPONSE_FILE" \
  "$PUBLISHER_URL"

python3 - "$RESPONSE_FILE" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
raw = path.read_text(errors="replace").strip()
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"publisher_invalid_json:{exc}")
if not isinstance(data, dict) or data.get("ok") is not True:
    raise SystemExit("publisher_rejected_tenant:" + raw[:500])
PY

# A chamada interna apenas solicita/reconcilia o proxy. O sucesso real exige
# TLS público válido e uma rota que não esteja ausente nem quebrada.
DEADLINE=$((SECONDS + WAIT_SECONDS))
LAST_CODE="000"
LAST_ERROR=""
while (( SECONDS < DEADLINE )); do
  : >"$ERROR_FILE"
  if LAST_CODE="$(curl --silent --show-error --output /dev/null \
      --write-out '%{http_code}' --connect-timeout 8 --max-time 30 \
      "$PUBLIC_URL" 2>"$ERROR_FILE")"; then
    case "$LAST_CODE" in
      2??|3??|401|403)
        python3 - "$TENANT" "$HOST" "$PUBLIC_URL" "$LAST_CODE" "$RESPONSE_FILE" <<'PY'
import json
import pathlib
import sys

tenant, host, url, status, response_file = sys.argv[1:]
publisher = json.loads(pathlib.Path(response_file).read_text(errors="replace"))
print(json.dumps({
    "ok": True,
    "tenant": tenant,
    "host": host,
    "url": url,
    "http_status": int(status),
    "tls_verified": True,
    "route_verified": True,
    "publisher": {
        "ok": publisher.get("ok") is True,
        "certificate": publisher.get("certificate") or publisher.get("cert_name") or "",
    },
}, ensure_ascii=False))
PY
        exit 0
        ;;
    esac
  fi
  LAST_ERROR="$(tail -c 1000 "$ERROR_FILE" 2>/dev/null || true)"
  sleep 5
done

echo "Certificado/rota HTTPS do tenant não ficou válido em ${PUBLIC_URL}. HTTP=${LAST_CODE}. ${LAST_ERROR}" >&2
exit 1
