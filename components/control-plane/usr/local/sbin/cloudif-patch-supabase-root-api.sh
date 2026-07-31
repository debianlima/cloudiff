#!/usr/bin/env bash
set -euo pipefail

TENANT="${1:-iff1742962}"

PUBLIC_HOST="cloudiff.duckdns.org"
PUBLIC_BASE="https://${PUBLIC_HOST}/supabase/${TENANT}"

CONF="/srv/cloudif/router/conf.d/default.conf"
ENV_FILE="/srv/cloudif/tenants/${TENANT}/.env"
ROUTER_CONT="cloudif-tenant-router"

ROUTER_BIND="10.62.92.7:8099"

echo "============================================================"
echo " CLOUDIF - PATCH SUPABASE STUDIO ROOT API/ASSETS"
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
  echo "ERRO: DASHBOARD_USERNAME/DASHBOARD_PASSWORD ausentes no .env"
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
cp -a "$CONF" "$CONF.bkp-root-api-$TS"

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

# Garante bind correto.
text = re.sub(
    r'listen\s+(?:0\.0\.0\.0:|127\.0\.0\.1:|10\.\d+\.\d+\.\d+:)?8099\s*;',
    f'listen {router_bind};',
    text
)
text = text.replace("listen 8099;", f"listen {router_bind};")

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

# Remove rotas raiz que hoje conflitam com o Supabase Studio.
# No domínio cloudiff.duckdns.org, /api precisa ser do Supabase Studio, não do Komodo.
markers = [
    "location ^~ /api/ {",
    "location ^~ /assets/ {",
    "location ^~ /ws/ {",
    "location = /favicon.ico {",
    "location = /favicon.svg {",
    "location = /favicon-96x96.png {",
    "location = /apple-touch-icon.png {",
    "location = /manifest.json {",
    "location ^~ /_next/ {",
    "location ^~ /monaco-editor/ {",
    "location ^~ /img/ {",
    "location = /supabase-logo.svg {",
    "location ^~ /project/ {",
]

for marker in markers:
    text = remove_location(text, marker)

# Remove bloco anterior deste patch, se existir.
text = re.sub(
    r"\n?\s*# BEGIN CloudIF Supabase Root API/Assets.*?# END CloudIF Supabase Root API/Assets\n?",
    "\n",
    text,
    flags=re.S,
)

root_block = f'''
    # BEGIN CloudIF Supabase Root API/Assets
    # O Supabase Studio gera chamadas absolutas em /api, /_next, /monaco-editor etc.
    # Como cloudiff.duckdns.org é o domínio do Supabase, essas rotas raiz precisam ir para o tenant.
    # Se não fizer isso, o frontend chama /api/platform/projects/default e recebe 404.

    location ^~ /api/ {{
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
        proxy_set_header Accept-Encoding "";
        proxy_cookie_path / /supabase/{tenant}/;
        proxy_pass http://{kong_host}:{kong_port}/api/;
    }}

    location ^~ /_next/ {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://{kong_host}:{kong_port}/_next/;
    }}

    location ^~ /monaco-editor/ {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://{kong_host}:{kong_port}/monaco-editor/;
    }}

    location ^~ /img/ {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://{kong_host}:{kong_port}/img/;
    }}

    location ^~ /assets/ {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_set_header X-Forwarded-Host {public_host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-Forwarded-Scheme https;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header Forwarded "proto=https;host={public_host}";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://{kong_host}:{kong_port}/assets/;
    }}

    location ^~ /project/ {{
        return 302 https://{public_host}/supabase/{tenant}$request_uri;
    }}

    location = /supabase-logo.svg {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/supabase-logo.svg;
    }}

    location = /manifest.json {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/manifest.json;
    }}

    location = /favicon.ico {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/favicon.ico;
    }}

    location = /favicon.svg {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/favicon.svg;
    }}

    location = /favicon-96x96.png {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/favicon-96x96.png;
    }}

    location = /apple-touch-icon.png {{
        proxy_http_version 1.1;
        proxy_set_header Host {public_host};
        proxy_set_header Authorization "Basic {basic_b64}";
        proxy_pass http://{kong_host}:{kong_port}/apple-touch-icon.png;
    }}

    # END CloudIF Supabase Root API/Assets

'''

# Insere antes do bloco Supabase do tenant, se existir.
anchor = f"# CloudIF Supabase APIs - tenant {tenant}"
idx = text.find(anchor)

if idx >= 0:
    insert_at = text.rfind("\n", 0, idx)
    text = text[:insert_at+1] + root_block + text[insert_at+1:]
else:
    # fallback: antes do último }
    server_end = text.rfind("}")
    if server_end < 0:
        raise SystemExit("ERRO: não encontrei fechamento do server.")
    text = text[:server_end] + root_block + text[server_end:]

path.write_text(text)
PY

echo
echo "===== 1. Conferindo rotas raiz Supabase ====="
grep -nA170 -B5 "BEGIN CloudIF Supabase Root API/Assets" "$CONF" \
  | sed -E 's/(Authorization "Basic )[A-Za-z0-9+\/=]+/\1<oculto>/'

echo
echo "===== 2. Conferindo se /api ainda aponta para Komodo ====="
grep -nA12 -B3 'location \^~ /api/' "$CONF" \
  | sed -E 's/(Authorization "Basic )[A-Za-z0-9+\/=]+/\1<oculto>/'

echo
echo "===== 3. Testando Nginx ====="
docker exec "$ROUTER_CONT" nginx -t

echo
echo "===== 4. Reiniciando Tenant Router ====="
docker restart "$ROUTER_CONT"

sleep 8

echo
echo "===== 5. Testes das chamadas que estavam dando 404 ====="

for path in \
  "/api/get-deployment-commit" \
  "/api/cli-release-version" \
  "/api/platform/profile" \
  "/api/enabled-features-overrides" \
  "/api/platform/projects/default" \
  "/api/platform/projects/default/databases" \
  "/api/v1/projects/default/api-keys?reveal=false" \
  "/monaco-editor/loader.js" \
  "/supabase-logo.svg" \
  "/manifest.json"
do
  echo
  echo "--- $path ---"
  curl -k -I --max-time 15 "https://${PUBLIC_HOST}${path}" 2>/dev/null | sed -n '1,20p' || true
done

echo
echo "===== 6. Teste da tela principal ====="
curl -k -I --max-time 15 "$PUBLIC_BASE/project/default" 2>/dev/null | sed -n '1,60p'

echo
echo "============================================================"
echo " OK: patch aplicado."
echo " Agora recarregue com Ctrl+F5 ou nova janela anônima:"
echo " $PUBLIC_BASE/project/default"
echo "============================================================"
