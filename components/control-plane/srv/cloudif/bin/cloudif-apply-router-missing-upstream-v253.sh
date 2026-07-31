#!/usr/bin/env bash
set -Eeuo pipefail

CONF="${1:-/srv/cloudif/router/conf.d/default.conf}"
ROUTER="${CLOUDIF_ROUTER_CONTAINER:-cloudif-tenant-router}"
STAMP="$(date +%F-%H%M%S)"

echo "------------------------------------------------------------"
echo " CloudIF Apply Missing Upstream Guard v253"
echo "------------------------------------------------------------"
echo "CONF=$CONF"

test -f "$CONF" || { echo "ERRO: não existe $CONF"; exit 1; }

cp -a "$CONF" "$CONF.bkp-missing-upstream-v253-$STAMP"

python3 - "$CONF" <<'PY'
from pathlib import Path
import re
import sys

conf = Path(sys.argv[1])
txt = conf.read_text(errors="ignore")

# Remove blocos antigos v253.
txt = re.sub(
    r'\n\s*# CloudIF v253 missing-upstream guard BEGIN.*?# CloudIF v253 missing-upstream guard END\n',
    '\n',
    txt,
    flags=re.S,
)

guard = r'''
        # CloudIF v253 missing-upstream guard BEGIN
        default_type text/html;

        if ($cloudif_kong_port = "") {
            return 202 '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>CloudIF preparando ambiente</title></head><body style="font-family:Arial,sans-serif;max-width:760px;margin:40px auto"><h2>CloudIF esta preparando seu ambiente</h2><p>Tenant: <b>$cloudif_effective_tenant</b></p><p>O ambiente ainda esta iniciando ou sendo renderizado.</p><p>Esta pagina atualiza automaticamente a cada 5 segundos. Se preferir, pressione F5.</p></body></html>';
        }
        # CloudIF v253 missing-upstream guard END
'''

# Insere logo após o bloco de autenticação v244/v233 dentro das locations protegidas.
patterns = [
    "# CloudIF v244 tenant-auth END",
    "# CloudIF v233 tenant-auth END",
]

inserted = 0
lines = txt.splitlines()
out = []

for line in lines:
    out.append(line)
    if any(p in line for p in patterns):
        out.append(guard.rstrip("\n"))
        inserted += 1

if inserted < 2:
    raise SystemExit(f"ERRO: esperava inserir em /project/ e /api/, inseri {inserted}")

conf.write_text("\n".join(out) + "\n")
print(f"OK: guard v253 inserido em {inserted} pontos.")
PY

docker exec "$ROUTER" nginx -t
docker exec "$ROUTER" nginx -s reload

echo "OK: Missing upstream guard v253 aplicado."
