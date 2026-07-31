#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
COMPOSE="$TDIR/docker-compose.yml"

test -f "$COMPOSE" || { echo "ERRO: não existe $COMPOSE"; exit 1; }

# O akadmin atual já está funcionando com containers fixos supabase-*.
# Não vamos mexer nele para evitar duplicar containers em produção.
if [ "$TENANT" = "akadmin" ] && docker ps -a --format '{{.Names}}' | grep -qx 'supabase-kong'; then
  echo "akadmin existente detectado: mantendo container_name para não recriar containers."
  exit 0
fi

cp -a "$COMPOSE" "$COMPOSE.bkp-sanitize-$(date +%F-%H%M%S)"

python3 - "$COMPOSE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
lines = p.read_text().splitlines()
out = []

for line in lines:
    if line.lstrip().startswith("container_name:"):
        continue
    out.append(line)

p.write_text("\n".join(out).rstrip() + "\n")
PY

echo "container_name removido de $COMPOSE"

cd "$TDIR"
docker compose --env-file .env config -q
echo "docker-compose.yml validado para $TENANT"
