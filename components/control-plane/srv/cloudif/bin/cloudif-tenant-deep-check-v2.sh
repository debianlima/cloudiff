#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"
LOG="$BASE/logs/deep-check-v2-${TENANT}.log"

mkdir -p "$BASE/logs"
exec >> "$LOG" 2>&1

echo
echo "============================================================"
echo "CloudIF Deep Check v2 tenant=$TENANT date=$(date -Is)"
echo "============================================================"

[ -d "$TDIR" ] || { echo "ERRO: tenant dir não existe"; exit 1; }
[ -f "$ENV" ] || { echo "ERRO: .env não existe"; exit 1; }

cd "$TDIR"

bad=0

echo
echo "==> docker compose ps"
docker compose --env-file .env ps || true

echo
echo "==> serviços"
for svc in db kong studio meta auth rest storage realtime supavisor; do
  cid="$(docker compose --env-file .env ps -q "$svc" 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo "WARN: serviço ausente: $svc"
    bad=1
    continue
  fi
  status="$(docker inspect "$cid" --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)"
  echo "$svc: $status"
  if echo "$status" | grep -Eiq 'exited|dead|restarting|unhealthy'; then
    bad=1
  fi
done

if [ "$bad" = "1" ]; then
  echo
  echo "==> Problema detectado. Sincronizando roles e recriando serviços críticos."
  if [ -x /srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh ]; then
    /srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh "$TENANT" || true
  elif [ -x /srv/cloudif/bin/cloudif-sync-db-passwords.sh ]; then
    /srv/cloudif/bin/cloudif-sync-db-passwords.sh "$TENANT" || true
  fi

  docker compose --env-file .env up -d auth rest storage realtime supavisor meta kong studio || true
else
  echo "OK: nenhum serviço crítico em estado ruim."
fi

echo
echo "==> teste Kong local"
PORT="$(awk -F= '$1=="KONG_HTTP_PORT"{print substr($0,length($1)+2); exit}' "$ENV" | tr -d '"' || true)"
if [ -n "$PORT" ]; then
  curl -sS -I --max-time 10 -H "Host: ${TENANT}.cloudiff.duckdns.org" "http://127.0.0.1:${PORT}/" | sed -n '1,12p' || true
fi

echo "FIM deep check v2 $(date -Is)"
