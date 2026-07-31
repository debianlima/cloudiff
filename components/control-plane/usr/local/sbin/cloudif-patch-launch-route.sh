#!/usr/bin/env bash
set -euo pipefail

CONF="/srv/cloudif/router/conf.d/default.conf"
ROUTER_CONT="cloudif-tenant-router"

if [ ! -f "$CONF" ]; then
  echo "ERRO: não encontrei $CONF"
  exit 1
fi

cp -a "$CONF" "$CONF.bkp-launch-route-$(date +%Y%m%d-%H%M%S)"

python3 - "$CONF" <<'PY'
from pathlib import Path
import re

path = Path(__import__("sys").argv[1])
text = path.read_text()

text = re.sub(
    r"\n?\s*# BEGIN CloudIF Supabase Launch API.*?# END CloudIF Supabase Launch API\n?",
    "\n",
    text,
    flags=re.S,
)

block = r'''
    # BEGIN CloudIF Supabase Launch API
    # Endpoint chamado pelo Authentik para garantir/criar o tenant antes de abrir o Studio.
    location ^~ /cloudif/supabase/launch/ {
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass http://127.0.0.1:18090/cloudif/supabase/launch/;
    }
    # END CloudIF Supabase Launch API

'''

server_end = text.rfind("}")
if server_end < 0:
    raise SystemExit("ERRO: não encontrei fechamento do server.")

text = text[:server_end] + block + text[server_end:]
path.write_text(text)
PY

docker exec "$ROUTER_CONT" nginx -t
docker restart "$ROUTER_CONT"

echo "OK: rota /cloudif/supabase/launch/ aplicada."
