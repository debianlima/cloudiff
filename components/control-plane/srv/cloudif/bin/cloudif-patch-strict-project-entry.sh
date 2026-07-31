#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/srv/cloudif"
CONF="$BASE/router/conf.d/default.conf"
HOST="${CLOUDIF_PUBLIC_HOST:-cloudiff.duckdns.org}"
STAMP="$(date +%F-%H%M%S)"

test -f "$CONF" || { echo "ERRO: não existe $CONF"; exit 1; }

cp -a "$CONF" "$BASE/backups/default.conf.bkp-strict-project-$STAMP"

python3 - <<'PY'
from pathlib import Path
import re
import os

conf = Path("/srv/cloudif/router/conf.d/default.conf")
host = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")

txt = conf.read_text(errors="ignore")

# Remove qualquer bloco antigo de /project/
txt = re.sub(
    r'\n\s*location\s+\^~\s+/project/\s*\{.*?\n\s*\}\s*\n',
    '\n',
    txt,
    flags=re.S,
)

strict = f'''
    # CloudIF v168: entrada direta em /project/ não deve confiar só em cookie.
    # Sempre volta ao broker para validar sessão no Authentik.
    location ^~ /project/ {{
        add_header Cache-Control no-store always;
        add_header X-CloudIF-Reason strict-project-entry always;
        return 302 https://{host}/cloudiff/supabase/session/start;
    }}

'''

marker = "    location ^~ /api/ {"
if marker in txt:
    txt = txt.replace(marker, strict + "\n" + marker, 1)
else:
    # fallback: insere antes do fim do server
    txt = txt.replace("\n}", "\n" + strict + "\n}", 1)

conf.write_text(txt)
print("OK: /project/ agora força validação pelo broker.")
PY

docker exec cloudif-tenant-router nginx -t
docker exec cloudif-tenant-router nginx -s reload || docker restart cloudif-tenant-router
