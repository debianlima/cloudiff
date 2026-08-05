#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
[[ "$TENANT" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || {
  echo "Tenant inválido: $TENANT" >&2
  exit 2
}

ENV_FILE="${CLOUDIF_NPM_PUBLISHER_ENV:-/etc/cloudif/npm-publisher-client.env}"
REGISTRY="${CLOUDIF_TENANT_REGISTRY:-/srv/cloudif/registry/tenants.csv}"
TENANT_DIR="${CLOUDIF_TENANT_ROOT:-/srv/cloudif/tenants}/${TENANT}"
DOMAIN="${CLOUDIF_DOMAIN:-cloudiff.duckdns.org}"
HOST="${TENANT}.${DOMAIN}"
READY_URL="https://${HOST}/cloudiff/tenant-readiness"
API_URL="https://${HOST}/auth/v1/health"
PUBLISHER_URL="${CLOUDIF_TENANT_PUBLISHER_URL:-http://10.62.91.3/tenant}"
PUBLISHER_HOST="${CLOUDIF_TENANT_PUBLISHER_HOST:-cloudif-publisher.internal}"
WAIT_SECONDS="${CLOUDIF_TENANT_CERTIFICATE_WAIT_SECONDS:-900}"
[[ "$WAIT_SECONDS" =~ ^[0-9]+$ ]] || WAIT_SECONDS=900

# Não publique um host para tenant ausente. Um certificado válido, sozinho,
# não comprova que a rota pertence a um tenant ativo.
KONG_PORT="$(python3 - "$REGISTRY" "$TENANT" <<'PY'
import csv
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
tenant = sys.argv[2]
if path.exists():
    with path.open(newline="", errors="ignore") as stream:
        for row in csv.DictReader(stream):
            if (row.get("tenant") or "").strip() == tenant:
                print((row.get("kong_http_port") or "").strip())
                break
PY
)"
[ -n "$KONG_PORT" ] || {
  echo "Tenant não registrado em $REGISTRY: $TENANT" >&2
  exit 1
}
[ -d "$TENANT_DIR" ] || {
  echo "Diretório do tenant não existe: $TENANT_DIR" >&2
  exit 1
}

TOKEN="$(grep -E '^NPM_PUBLISHER_TOKEN=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
[ -n "$TOKEN" ] || {
  echo "NPM publisher token ausente em $ENV_FILE" >&2
  exit 1
}

REQUEST_JSON="$(python3 -c 'import json,sys; print(json.dumps({"tenant":sys.argv[1]}))' "$TENANT")"
RESPONSE_FILE="$(mktemp)"
READY_BODY="$(mktemp)"
READY_HEADERS="$(mktemp)"
API_BODY="$(mktemp)"
ERROR_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE" "$READY_BODY" "$READY_HEADERS" "$API_BODY" "$ERROR_FILE"' EXIT

curl -fsS \
  --retry 5 --retry-delay 3 --retry-all-errors \
  --connect-timeout 8 --max-time 240 \
  -H 'Content-Type: application/json' \
  -H "Host: $PUBLISHER_HOST" \
  -H "X-CloudIF-Token: $TOKEN" \
  --data "$REQUEST_JSON" \
  --output "$RESPONSE_FILE" \
  "$PUBLISHER_URL"

python3 - "$RESPONSE_FILE" "$TENANT" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
tenant = sys.argv[2]
raw = path.read_text(errors="replace").strip()
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"publisher_invalid_json:{exc}")
if not isinstance(data, dict) or data.get("ok") is not True or data.get("tenant") != tenant:
    raise SystemExit("publisher_rejected_tenant:" + raw[:500])
PY

DEADLINE=$((SECONDS + WAIT_SECONDS))
LAST_READY_CODE="000"
LAST_API_CODE="000"
LAST_ERROR=""
while (( SECONDS < DEADLINE )); do
  : >"$ERROR_FILE"
  : >"$READY_BODY"
  : >"$READY_HEADERS"
  : >"$API_BODY"

  LAST_READY_CODE="$(curl --silent --show-error --output "$READY_BODY" \
      --dump-header "$READY_HEADERS" --write-out '%{http_code}' \
      --connect-timeout 8 --max-time 30 "$READY_URL" 2>"$ERROR_FILE" || true)"
  READY_TENANT="$(tr -d '\r\n' <"$READY_BODY")"
  READY_HEADER="$(grep -i '^X-CloudIF-Tenant:' "$READY_HEADERS" | tail -1 | cut -d: -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true)"

  LAST_API_CODE="$(curl --silent --show-error --output "$API_BODY" \
      --write-out '%{http_code}' --connect-timeout 8 --max-time 30 \
      "$API_URL" 2>>"$ERROR_FILE" || true)"

  if [ "$LAST_READY_CODE" = "200" ] \
      && [ "$READY_TENANT" = "$TENANT" ] \
      && [ "$READY_HEADER" = "$TENANT" ]; then
    case "$LAST_API_CODE" in
      200|401|403)
        python3 - "$TENANT" "$HOST" "$READY_URL" "$API_URL" "$LAST_READY_CODE" "$LAST_API_CODE" "$KONG_PORT" "$RESPONSE_FILE" <<'PY'
import json
import pathlib
import sys

tenant, host, ready_url, api_url, ready_status, api_status, kong_port, response_file = sys.argv[1:]
publisher = json.loads(pathlib.Path(response_file).read_text(errors="replace"))
print(json.dumps({
    "ok": True,
    "tenant": tenant,
    "host": host,
    "url": "https://" + host + "/",
    "readiness_url": ready_url,
    "api_url": api_url,
    "readiness_status": int(ready_status),
    "api_status": int(api_status),
    "kong_http_port": int(kong_port),
    "registry_verified": True,
    "tls_verified": True,
    "route_verified": True,
    "api_verified": True,
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

echo "Tenant não ficou pronto em ${READY_URL}. readiness=${LAST_READY_CODE} api=${LAST_API_CODE} body=$(head -c 200 "$READY_BODY"). ${LAST_ERROR}" >&2
exit 1
