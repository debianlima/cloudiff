#!/usr/bin/env bash
set -euo pipefail

CONF="/srv/cloudif/router/conf.d/default.conf"
ROUTER="cloudif-tenant-router"
UPSTREAM="http://10.62.92.7:18090"

cp -a "$CONF" "$CONF.bkp-launch-v2-$(date +%Y%m%d-%H%M%S)"

python3 - "$CONF" "$UPSTREAM" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
upstream = sys.argv[2]
text = path.read_text()

def remove_location(src, marker):
    idx = src.find(marker)
    if idx < 0:
        return src
    brace = src.find("{", idx)
    if brace < 0:
        return src
    depth = 0
    end = None
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return src
    while end < len(src) and src[end] in " \t\r\n":
        end += 1
    return src[:idx] + src[end:]

# Remove rotas antigas conflitantes.
for marker in [
    "location ^~ /cloudif/supabase/ {",
    "location ^~ /cloudif/supabase/launch/ {",
    "location ^~ /cloudif/supabase/status/ {",
    "location ^~ /cloudif/supabase/force/ {",
]:
    text = remove_location(text, marker)

text = re.sub(
    r"\n?\s*# BEGIN CloudIF .*?Supabase Launch.*?# END CloudIF .*?Supabase Launch\n?",
    "\n",
    text,
    flags=re.S,
)

block = f'''
    # BEGIN CloudIF Supabase Launch V2
    location ^~ /cloudif/supabase/ {{
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_pass {upstream}/cloudif/supabase/;
    }}
    # END CloudIF Supabase Launch V2

'''

server_pos = text.find("server {")
if server_pos < 0:
    raise SystemExit("server não encontrado")

insert = text.find("\n", server_pos) + 1
text = text[:insert] + block + text[insert:]
path.write_text(text)
PY

docker exec "$ROUTER" nginx -t
docker restart "$ROUTER"
