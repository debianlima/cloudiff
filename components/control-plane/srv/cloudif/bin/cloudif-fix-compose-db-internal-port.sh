#!/usr/bin/env bash
set -Eeuo pipefail
TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
COMPOSE="$TDIR/docker-compose.yml"
ENV="$TDIR/.env"

test -f "$COMPOSE" || { echo "ERRO: não existe $COMPOSE"; exit 1; }
test -f "$ENV" || { echo "ERRO: não existe $ENV"; exit 1; }

POSTGRES_PORT="$(grep -E '^POSTGRES_PORT=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
[ -n "$POSTGRES_PORT" ] || POSTGRES_PORT="5432"

# Nesta imagem Supabase, o Postgres usa POSTGRES_PORT também dentro da rede Docker.
python3 - "$COMPOSE" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
txt = p.read_text()
txt = txt.replace("${POSTGRES_INTERNAL_PORT}", "${POSTGRES_PORT}")
txt = txt.replace(":${POSTGRES_INTERNAL_PORT}", ":${POSTGRES_PORT}")
p.write_text(txt)
PY

if grep -qE '^POSTGRES_INTERNAL_PORT=' "$ENV"; then
  sed -i "s|^POSTGRES_INTERNAL_PORT=.*|POSTGRES_INTERNAL_PORT=${POSTGRES_PORT}|" "$ENV"
else
  echo "POSTGRES_INTERNAL_PORT=${POSTGRES_PORT}" >> "$ENV"
fi

docker compose --env-file "$ENV" -f "$COMPOSE" config -q
echo "OK: compose mantido com POSTGRES_PORT interno para tenant=$TENANT"
