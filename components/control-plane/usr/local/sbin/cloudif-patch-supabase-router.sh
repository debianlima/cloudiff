#!/usr/bin/env bash
set -euo pipefail

TENANT="${1:-iff1742962}"
MODE="${2:-normal}"

PUBLIC_HOST="cloudiff.duckdns.org"
PUBLIC_BASE="https://${PUBLIC_HOST}/supabase/${TENANT}"

ROUTER_CONT="cloudif-tenant-router"
CONF="/srv/cloudif/router/conf.d/default.conf"
ENV_FILE="/srv/cloudif/tenants/${TENANT}/.env"
RENDER="/srv/cloudif/bin/cloudif-render-router.sh"

ROUTER_BIND="10.62.92.7:8099"

echo "============================================================"
echo " CLOUDIF - PATCH ROUTER SUPABASE STUDIO COM BASIC INTERNO"
echo " Tenant: $TENANT"
echo " URL:    $PUBLIC_BASE"
echo " Conf:   $CONF"
echo "============================================================"

if [ ! -f "$CONF" ]; then
  echo "ERRO: não encontrei $CONF"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERRO: não encontrei $ENV_FILE"
  exit 1
fi

DASHBOARD_USERNAME="$(grep -E '^DASHBOARD_USERNAME=' "$ENV_FILE" | cut -d= -f2- || true)"
DASHBOARD_PASSWORD="$(grep -E '^DASHBOARD_PASSWORD=' "$ENV_FILE" | cut -d= -f2- || true)"

if [ -z "$DASHBOARD_USERNAME" ] || [ -z "$DASHBOARD_PASSWORD" ]; then
  echo "ERRO: DASHBOARD_USERNAME ou DASHBOARD_PASSWORD ausente no .env"
  exit 1
fi

BASIC_B64="$(printf '%s:%s' "$DASHBOARD_USERNAME" "$DASHBOARD_PASSWORD" | base64 -w0)"

KONG_BIND="$(docker port "cloudif-${TENANT}-kong-1" 8000/tcp 2>/dev/null | head -1 | tr -d '\r\n' || true)"
KONG_HOST="$(echo "$KONG_BIND" | awk -F: '{print $1}')"
KONG_PORT="$(echo "$KONG_BIND" | awk -F: '{print $NF}')"

if [ -z "$KONG_HOST" ] || [ -z "$KONG_PORT" ]; then
  KONG_HOST="10.62.92.7"
  KONG_PORT="8101"
fi

echo "Kong: http://${KONG_HOST}:${KONG_PORT}"

TS="$(date +%Y%m%d-%H%M%S)"
cp -a "$CONF" "$CONF.bkp-supabase-basic-$TS"

python3 - "$CONF" "$TENANT" "$PUBLIC_HOST" "$KONG_HOST" "$KONG_PORT" "$BASIC_B64" "$ROUTER_BIND" <<'PY'
from pathlib import Path
import sys
import re

path = Path(sys.argv[1])
tenant = sys.argv[2]
public_host = sys.argv[3]
kong_host = sys.argv[4]
kong_port = sys.argv[5]
basic_b64 = sys.argv[6]
router_bind = sys.argv[7]

text = path.read_text()

# Garante bind correto do router.
text = re.sub(
    r'listen\s+(?:0\.0\.0\.0:|127\.0\.0\.1:|10\.\d+\.\d+\.\d+:)?8099\s*;',
    f'listen {router_bind};',
    text
)
text = text.replace("listen 8099;", f"listen {router_bind};")

# Remove guards antigos e recria.
text = re.sub(
    r"\n?\s*# BEGIN CloudIF Port Guard.*?# END CloudIF Port Guard\n?",
    "\n",
    text,
    flags=re.S,
)

server_idx = text.find("server {")
if server_idx < 0:
    raise SystemExit("ERRO: não encontrei server {")

insert_after = text.find("\n", server_idx)

guard = f'''
    # BEGIN CloudIF Port Guard
    absolute_redirect off;
    port_in_redirect off;
    server_name_in_redirect off;

    if ($http_host ~* ":[0-9]+$") {{
        return 301 https://{public_host}$request_uri;
    }}

    proxy_headers_hash_max_size 2048;
    proxy_headers_hash_bucket_size 128;
    # END CloudIF Port Guard
'''

text = text[:insert_after+1] + guard + text[insert_after+1:]

def remove_location(src: str, marker: str):
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

# Remove blocos antigos específicos do tenant.
markers = [
    f"location = /supabase/{tenant} {{",
    f"location = /supabase/{tenant}/ {{",
    f"location ^~ /supabase/{tenant}/auth/v1/ {{",
    f"location ^~ /supabase/{tenant}/rest/v1/ {{",
    f"location ^~ /supabase/{tenant}/storage/v1/ {{",
    f"location ^~ /supabase/{tenant}/realtime/v1/ {{",
    f"location ^~ /supabase/{tenant}/functions/v1/ {{",
    f"location ^~ /supabase/{tenant}/ {{",
]

for marker in markers:
    text = remove_location(text, marker)

common_headers = f'''
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
'''

api_block = f'''
    # ============================================================
    # CloudIF Supabase APIs - tenant {tenant}
    # Sem Basic Auth interno para não quebrar apikey/Bearer.
    # ============================================================

    location = /supabase/{tenant} {{
        return 302 /supabase/{tenant}/;
    }}

    location = /supabase/{tenant}/ {{
        return 302 https://{public_host}/supabase/{tenant}/project/default;
    }}

    location ^~ /supabase/{tenant}/auth/v1/ {{
{common_headers}
        proxy_pass http://{kong_host}:{kong_port}/auth/v1/;
    }}

    location ^~ /supabase/{tenant}/rest/v1/ {{
{common_headers}
        proxy_pass http://{kong_host}:{kong_port}/rest/v1/;
    }}

    location ^~ /supabase/{tenant}/storage/v1/ {{
{common_headers}
        proxy_pass http://{kong_host}:{kong_port}/storage/v1/;
    }}

    location ^~ /supabase/{tenant}/realtime/v1/ {{
{common_headers}
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass http://{kong_host}:{kong_port}/realtime/v1/;
    }}

    location ^~ /supabase/{tenant}/functions/v1/ {{
{common_headers}
        proxy_pass http://{kong_host}:{kong_port}/functions/v1/;
    }}

    # ============================================================
    # CloudIF Supabase Studio - tenant {tenant}
    # Aqui o router injeta Basic Auth internamente.
    # O navegador do usuário NÃO deve pedir usuário/senha.
    # ============================================================

    location ^~ /supabase/{tenant}/ {{
        rewrite ^/supabase/{tenant}/(.*)$ /$1 break;

        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Forwarded-Prefix /supabase/{tenant};
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Accept-Encoding "";

        proxy_cookie_path / /supabase/{tenant}/;

        proxy_redirect ~^https?://[^/]+(:[0-9]+)?/supabase/{tenant}/(.*)$ https://{public_host}/supabase/{tenant}/$2;
        proxy_redirect ~^https?://[^/]+(:[0-9]+)?/(project/.*)$ https://{public_host}/supabase/{tenant}/$2;
        proxy_redirect ~^/(project/.*)$ /supabase/{tenant}/$1;
        proxy_redirect ~^/(.*)$ /supabase/{tenant}/$1;

        sub_filter_once off;
        sub_filter_types *;
        sub_filter 'href="/' 'href="/supabase/{tenant}/';
        sub_filter 'src="/' 'src="/supabase/{tenant}/';
        sub_filter 'action="/' 'action="/supabase/{tenant}/';
        sub_filter 'url(/' 'url(/supabase/{tenant}/';
        sub_filter '"/_next/' '"/supabase/{tenant}/_next/';
        sub_filter "'/_next/" "'/supabase/{tenant}/_next/";
        sub_filter '"/api/' '"/supabase/{tenant}/api/';
        sub_filter "'/api/" "'/supabase/{tenant}/api/";
        sub_filter '"/auth/' '"/supabase/{tenant}/auth/';
        sub_filter "'/auth/" "'/supabase/{tenant}/auth/";
        sub_filter '"/project/' '"/supabase/{tenant}/project/';
        sub_filter "'/project/" "'/supabase/{tenant}/project/";

        proxy_pass http://{kong_host}:{kong_port}/;
    }}

'''

# Insere antes do fechamento do server.
server_end = text.rfind("}")
if server_end < 0:
    raise SystemExit("ERRO: não encontrei fechamento do server.")

text = text[:server_end] + api_block + text[server_end:]

path.write_text(text)
PY

echo
echo "===== 1. Conferindo trecho do tenant ====="
grep -nA130 -B5 "CloudIF Supabase APIs - tenant ${TENANT}" "$CONF" \
  | sed -E 's/(Authorization "Basic )[A-Za-z0-9+\/=]+/\1<oculto>/'

echo
echo "===== 2. Testando Nginx ====="
docker exec "$ROUTER_CONT" nginx -t

echo
echo "===== 3. Reiniciando Tenant Router ====="
docker restart "$ROUTER_CONT"

sleep 8

echo
echo "===== 4. Testes sem seguir redirect ====="

echo
echo "--- Raiz do tenant: deve ser 302, NÃO 401 ---"
curl -k -I --max-time 15 "$PUBLIC_BASE/" 2>/dev/null | sed -n '1,40p' || true

echo
echo "--- Studio project/default: deve ser 200, NÃO 401 ---"
curl -k -I --max-time 15 "$PUBLIC_BASE/project/default" 2>/dev/null | sed -n '1,60p' || true

echo
echo "--- Auth settings com anon key: deve responder JSON ---"
ANON_KEY="$(grep -E '^ANON_KEY=' "$ENV_FILE" | cut -d= -f2- || true)"

if [ -n "$ANON_KEY" ]; then
  curl -k -sS --max-time 15 \
    -H "apikey: $ANON_KEY" \
    -H "Authorization: Bearer $ANON_KEY" \
    "$PUBLIC_BASE/auth/v1/settings" | jq '.external.keycloak, .disable_signup' || true
else
  echo "ANON_KEY não encontrada."
fi

echo
echo "===== 5. Validação final ====="

BAD="$(
  {
    curl -k -I --max-time 15 "$PUBLIC_BASE/" 2>/dev/null
    curl -k -I --max-time 15 "$PUBLIC_BASE/project/default" 2>/dev/null
  } | grep -i 'www-authenticate: Basic' || true
)"

if [ -n "$BAD" ]; then
  echo "ERRO: ainda está pedindo Basic Auth:"
  echo "$BAD"
  exit 1
fi

echo "OK: navegador não deve mais pedir usuário/senha Basic."
