#!/usr/bin/env bash
set -Eeuo pipefail
TENANT="${1:?tenant}"
ENV=/etc/cloudif/npm-publisher-client.env
TOKEN="$(grep -E '^NPM_PUBLISHER_TOKEN=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
[ -n "$TOKEN" ] || { echo "NPM publisher token ausente" >&2; exit 1; }
JSON="$(python3 -c 'import json,sys; print(json.dumps({"tenant":sys.argv[1]}))' "$TENANT")"
curl -fsS --connect-timeout 5 --max-time 360 \
  -H 'Content-Type: application/json' \
  -H 'Host: cloudif-publisher.internal' \
  -H "X-CloudIF-Token: $TOKEN" \
  --data "$JSON" \
  http://10.62.91.3/tenant
