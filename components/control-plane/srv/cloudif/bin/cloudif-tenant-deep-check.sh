#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/srv/cloudif"
TENANT="${1:?tenant}"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"
LOG="$BASE/logs/deep-check-${TENANT}.log"

exec >> "$LOG" 2>&1

echo
echo "============================================================"
echo "Deep check tenant=$TENANT date=$(date -Is)"
echo "============================================================"

if [ ! -f "$ENV" ]; then
  echo "ERRO: sem .env"
  exit 1
fi

cd "$TDIR"

echo
echo "==> compose ps"
docker compose --env-file .env ps || true

echo
echo "==> health serviços principais"
bad=0

for svc in db kong studio meta auth rest storage realtime supavisor; do
  cid="$(docker compose --env-file .env ps -q "$svc" 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo "WARN: serviço $svc sem container"
    bad=1
    continue
  fi

  status="$(docker inspect "$cid" --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)"
  echo "$svc: $status"

  if echo "$status" | grep -Eq 'exited|dead|restarting|unhealthy'; then
    bad=1
  fi
done

if [ "$bad" = "1" ]; then
  echo
  echo "==> Há serviço problemático. Tentando sync de roles se script existir."
  if [ -x /root/cloudif-sync-db-roles-one-tenant-v158.sh ]; then
    /root/cloudif-sync-db-roles-one-tenant-v158.sh "$TENANT" || true
  elif [ -x /srv/cloudif/bin/cloudif-sync-db-passwords.sh ]; then
    /srv/cloudif/bin/cloudif-sync-db-passwords.sh "$TENANT" || true
    docker compose --env-file .env up -d auth rest storage realtime supavisor meta kong studio || true
  else
    echo "Nenhum script de sync de roles encontrado."
  fi
else
  echo "OK: tenant saudável. Não reiniciei nada."
fi

if [ -x /srv/cloudif/bin/cloudif-render-router-sso.sh ]; then
  /srv/cloudif/bin/cloudif-render-router-sso.sh || true
fi

echo "FIM deep check $(date -Is)"
