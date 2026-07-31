#!/usr/bin/env bash
set -euo pipefail

CONF="/srv/cloudif/router/conf.d/default.conf"
ROUTER_CONT="cloudif-tenant-router"
LAUNCH_UPSTREAM="http://10.62.92.7:18090"

if [ ! -f "$CONF" ]; then
  echo "ERRO: não encontrei $CONF"
  exit 1
fi

cp -a "$CONF" "$CONF.bkp-async-launch-$(date +%Y%m%d-%H%M%S)"

python3 - "$CONF" "$LAUNCH_UPSTREAM" <<'PY'
from pathlib import Path
import sys
import re

path = Path(sys.argv[1])
upstream = sys.argv[2]

text = path.read_text()

text = re.sub(
    r"\n?\s*# BEGIN CloudIF Async Supabase Launch.*?# END CloudIF Async Supabase Launch\n?",
    "\n",
    text,
    flags=re.S,
)

block = f'''
    # BEGIN CloudIF Async Supabase Launch
    # Broker assíncrono: mostra status, impede concorrência e permite recriação confirmada.
    location ^~ /cloudif/supabase/ {{
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_pass {upstream}/cloudif/supabase/;
    }}
    # END CloudIF Async Supabase Launch

'''

server_end = text.rfind("}")
if server_end < 0:
    raise SystemExit("ERRO: não encontrei fechamento do server.")

text = text[:server_end] + block + text[server_end:]
path.write_text(text)
PY

docker exec "$ROUTER_CONT" nginx -t
docker restart "$ROUTER_CONT"

echo "OK: rota assíncrona aplicada."
