#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/srv/cloudif"
REGISTRY="$BASE/registry/tenants.csv"
CONF="$BASE/router/conf.d/default.conf"
HOST="${CLOUDIF_PUBLIC_HOST:-cloudiff.duckdns.org}"
ROUTER_IP="${CLOUDIF_ROUTER_IP:-10.62.92.7}"
ROUTER_PORT="${CLOUDIF_ROUTER_PORT:-8099}"
BROKER_PORT="${CLOUDIF_BROKER_PORT:-18091}"
STAMP="$(date +%F-%H%M%S)"

test -f "$REGISTRY" || { echo "ERRO: não existe $REGISTRY"; exit 1; }

mkdir -p "$BASE/router/conf.d" "$BASE/router/logs" "$BASE/backups"

if [ -f "$CONF" ]; then
  cp -a "$CONF" "$BASE/backups/default.conf.bkp-render-subdomain-$STAMP"
fi

python3 - <<'PY'
from pathlib import Path
import csv
import base64
import os

BASE = Path("/srv/cloudif")
REGISTRY = BASE / "registry/tenants.csv"
CONF = BASE / "router/conf.d/default.conf"

HOST = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")
ROUTER_IP = os.environ.get("CLOUDIF_ROUTER_IP", "10.62.92.7")
ROUTER_PORT = os.environ.get("CLOUDIF_ROUTER_PORT", "8099")
BROKER_PORT = os.environ.get("CLOUDIF_BROKER_PORT", "18091")

def read_env(path: Path):
    d = {}
    if not path.exists():
        return d
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip().strip('"')
    return d

def q(s: str):
    return s.replace("\\", "\\\\").replace('"', '\\"')

tenants = []

with REGISTRY.open(newline="", errors="ignore") as f:
    for row in csv.DictReader(f):
        tenant = (row.get("tenant") or "").strip()
        if not tenant:
            continue

        env = read_env(BASE / "tenants" / tenant / ".env")
        port = (env.get("KONG_HTTP_PORT") or row.get("kong_http_port") or "").strip()

        if not port:
            continue

        user = env.get("DASHBOARD_USERNAME") or "admin"
        pw = env.get("DASHBOARD_PASSWORD") or ""
        basic = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode() if pw else ""

        tenants.append((tenant, port, basic))

if not tenants:
    raise SystemExit("ERRO: nenhum tenant válido.")

L = []

L.append("# CloudIF router v170 - subdomain tenants + legacy /supabase/<tenant>")
L.append("")

L.append("map $http_upgrade $connection_upgrade {")
L.append("    default upgrade;")
L.append("    '' close;")
L.append("}")
L.append("")

# Tenant pelo host: iff1742962.cloudiff.duckdns.org
L.append("map $host $cloudif_host_tenant {")
L.append('    default "";')
L.append(rf"    ~^([A-Za-z0-9_.-]+)\.{HOST.replace('.', r'\.')}$ $1;")
L.append("}")
L.append("")

L.append("map $http_referer $cloudif_referer_tenant {")
L.append('    default "";')
L.append(r"    ~*/supabase/([^/]+)/ $1;")
L.append(rf"    ~^https?://([A-Za-z0-9_.-]+)\.{HOST.replace('.', r'\.')}/ $1;")
L.append("}")
L.append("")

# Ordem de confiança:
# 1) subdomínio do host
# 2) cookie
# 3) referer
L.append('map "$cloudif_host_tenant:$cookie_cloudif_tenant:$cloudif_referer_tenant" $cloudif_effective_tenant {')
L.append('    default "";')
L.append(r"    ~^([^:]+):.*:.*$ $1;")
L.append(r"    ~^:([^:]+):.*$ $1;")
L.append(r"    ~^::([^:]+)$ $1;")
L.append("}")
L.append("")

L.append("map $cloudif_host_tenant $cloudif_is_subdomain_tenant {")
L.append("    default 1;")
L.append('    "" 0;')
L.append("}")
L.append("")

L.append("map $cloudif_effective_tenant $cloudif_kong_port {")
L.append('    default "";')
for tenant, port, basic in tenants:
    L.append(f"    {tenant} {port};")
L.append("}")
L.append("")

L.append("map $cloudif_effective_tenant $cloudif_basic_auth_header {")
L.append('    default "";')
for tenant, port, basic in tenants:
    if basic:
        L.append(f'    {tenant} "{q(basic)}";')
L.append("}")
L.append("")

L.append("server {")
L.append(f"    listen {ROUTER_IP}:{ROUTER_PORT};")
L.append(f"    server_name {HOST} *.{HOST};")
L.append("")
L.append("    absolute_redirect off;")
L.append("    port_in_redirect off;")
L.append("    server_name_in_redirect off;")
L.append("    proxy_headers_hash_max_size 4096;")
L.append("    proxy_headers_hash_bucket_size 256;")
L.append("")
L.append("    proxy_intercept_errors on;")
L.append("    error_page 401 = @cloudif_reauth;")
L.append("")
L.append("    location @cloudif_reauth {")
L.append("        add_header Cache-Control no-store always;")
L.append("        add_header X-CloudIF-Reason basic-auth-intercept always;")
L.append(f"        return 302 https://{HOST}/cloudiff/supabase/session/start;")
L.append("    }")
L.append("")
L.append("    location = /health {")
L.append("        add_header Content-Type text/plain;")
L.append('        return 200 "cloudif-router-ok\\n";')
L.append("    }")
L.append("")
L.append("    location ^~ /cloudiff/supabase/session/ {")
L.append("        proxy_intercept_errors off;")
L.append("        proxy_http_version 1.1;")
L.append("        proxy_set_header Host $host;")
L.append("        proxy_set_header X-Real-IP $remote_addr;")
L.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
L.append("        proxy_set_header X-Forwarded-Proto https;")
L.append(f"        proxy_pass http://{ROUTER_IP}:{BROKER_PORT};")
L.append("    }")
L.append("")

# Legacy path /supabase/<tenant> continua funcionando.
for tenant, port, basic in tenants:
    L.append(f"    location = /supabase/{tenant} {{ return 301 https://{HOST}/supabase/{tenant}/; }}")
    L.append("")
    L.append(f"    location ^~ /supabase/{tenant}/ {{")
    L.append("        proxy_hide_header WWW-Authenticate;")
    L.append(f'        add_header Set-Cookie "cloudif_tenant={tenant}; Path=/; Secure; HttpOnly; SameSite=Lax" always;')
    L.append("        proxy_http_version 1.1;")
    L.append("        proxy_set_header Host $host;")
    L.append("        proxy_set_header Upgrade $http_upgrade;")
    L.append("        proxy_set_header Connection $connection_upgrade;")
    L.append("        proxy_set_header X-Real-IP $remote_addr;")
    L.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
    L.append("        proxy_set_header X-Forwarded-Proto https;")
    L.append("        proxy_set_header X-Forwarded-Host $host;")
    L.append(f"        proxy_set_header X-Forwarded-Prefix /supabase/{tenant};")
    L.append('        proxy_set_header Accept-Encoding "";')
    if basic:
        L.append(f'        proxy_set_header Authorization "{q(basic)}";')
    L.append(f"        rewrite ^/supabase/{tenant}/?(.*)$ /$1 break;")
    L.append(f"        proxy_cookie_path / /supabase/{tenant}/;")
    L.append(f"        proxy_redirect ~^/(.*)$ /supabase/{tenant}/$1;")
    L.append(f"        proxy_redirect / /supabase/{tenant}/;")
    L.append(f"        proxy_pass http://{ROUTER_IP}:{port};")
    L.append("    }")
    L.append("")

# Em subdomínio, /project/default é permitido.
# No domínio base, /project/default volta ao broker.
L.append("    location ^~ /project/ {")
L.append(f"        if ($cloudif_is_subdomain_tenant = 0) {{ return 302 https://{HOST}/cloudiff/supabase/session/start; }}")
L.append(f"        if ($cloudif_kong_port = \"\") {{ return 302 https://{HOST}/cloudiff/supabase/session/start; }}")
L.append("        proxy_intercept_errors off;")
L.append("        proxy_hide_header WWW-Authenticate;")
L.append("        proxy_http_version 1.1;")
L.append("        proxy_set_header Host $host;")
L.append("        proxy_set_header Upgrade $http_upgrade;")
L.append("        proxy_set_header Connection $connection_upgrade;")
L.append("        proxy_set_header X-Real-IP $remote_addr;")
L.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
L.append("        proxy_set_header X-Forwarded-Proto https;")
L.append("        proxy_set_header Authorization $cloudif_basic_auth_header;")
L.append(f"        proxy_pass http://{ROUTER_IP}:$cloudif_kong_port;")
L.append("    }")
L.append("")

# APIs/Assets absolutos, agora funcionam nativamente por subdomínio.
for loc in [
    "/api/",
    "/_next/",
    "/assets/",
    "/img/",
    "/monaco-editor/",
    "/favicon/",
    "/auth/v1/",
    "/rest/v1/",
    "/storage/v1/",
    "/realtime/v1/",
    "/functions/v1/",
]:
    L.append(f"    location ^~ {loc} {{")
    L.append("        proxy_intercept_errors off;")
    L.append("        proxy_hide_header WWW-Authenticate;")
    L.append(f"        if ($cloudif_kong_port = \"\") {{ return 302 https://{HOST}/cloudiff/supabase/session/start; }}")
    L.append("        proxy_http_version 1.1;")
    L.append("        proxy_set_header Host $host;")
    L.append("        proxy_set_header Referer $http_referer;")
    L.append("        proxy_set_header Cookie $http_cookie;")
    L.append("        proxy_set_header Upgrade $http_upgrade;")
    L.append("        proxy_set_header Connection $connection_upgrade;")
    L.append("        proxy_set_header X-Real-IP $remote_addr;")
    L.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
    L.append("        proxy_set_header X-Forwarded-Proto https;")
    L.append("        proxy_set_header Authorization $cloudif_basic_auth_header;")
    L.append(f"        proxy_pass http://{ROUTER_IP}:$cloudif_kong_port;")
    L.append("    }")
    L.append("")

# Raiz do subdomínio tenant.
L.append("    location / {")
L.append(f"        if ($cloudif_is_subdomain_tenant = 0) {{ return 404; }}")
L.append(f"        if ($cloudif_kong_port = \"\") {{ return 404; }}")
L.append("        proxy_hide_header WWW-Authenticate;")
L.append('        add_header Set-Cookie "cloudif_tenant=$cloudif_effective_tenant; Path=/; Secure; HttpOnly; SameSite=Lax" always;')
L.append("        proxy_http_version 1.1;")
L.append("        proxy_set_header Host $host;")
L.append("        proxy_set_header Upgrade $http_upgrade;")
L.append("        proxy_set_header Connection $connection_upgrade;")
L.append("        proxy_set_header X-Real-IP $remote_addr;")
L.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
L.append("        proxy_set_header X-Forwarded-Proto https;")
L.append("        proxy_set_header Authorization $cloudif_basic_auth_header;")
L.append(f"        proxy_pass http://{ROUTER_IP}:$cloudif_kong_port;")
L.append("    }")
L.append("")
L.append("}")

# CloudIF persistent machine-admin mTLS block
MTLS_BLOCK = r'''
server {
    listen 10.62.92.7:18111 ssl;
    server_name cloudif-machine-controller;

    ssl_certificate /etc/nginx/mtls/controller-server-chain.pem;
    ssl_certificate_key /etc/nginx/mtls/controller-server.key;
    ssl_client_certificate /etc/nginx/mtls/ca-chain.pem;
    ssl_trusted_certificate /etc/nginx/mtls/ca-chain.pem;
    ssl_crl /etc/nginx/mtls/ca-chain.crl.pem;
    ssl_verify_client on;
    ssl_verify_depth 2;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:CLOUDIF_AGENT_MTLS:10m;
    ssl_session_timeout 10m;
    client_max_body_size 10m;

    proxy_http_version 1.1;
    proxy_set_header Host cloudif-machine-controller;
    proxy_set_header X-CloudIF-Agent-Remote 1;
    proxy_set_header X-SSL-Client-Verify $ssl_client_verify;
    proxy_set_header X-SSL-Client-DN $ssl_client_s_dn;
    proxy_set_header X-SSL-Client-Serial $ssl_client_serial;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;

    location = /health { proxy_pass http://127.0.0.1:18110/health; }
    location = /api/inventory { proxy_pass http://127.0.0.1:18110/api/inventory; }
    location = /api/policy { proxy_pass http://127.0.0.1:18110/api/policy$is_args$args; }
    location = /api/policy/applied { proxy_pass http://127.0.0.1:18110/api/policy/applied; }
    location = /api/guardian/event { proxy_pass http://127.0.0.1:18110/api/guardian/event; }
    location = /api/certificate/renew { proxy_pass http://127.0.0.1:18110/api/certificate/renew; }
    location = /api/certificate/renew/ack { proxy_pass http://127.0.0.1:18110/api/certificate/renew/ack; }
    location / { return 404; }
}
'''
L.append("")
L.extend(MTLS_BLOCK.strip().splitlines())

CONF.write_text("\n".join(L) + "\n")
print("OK: router subdomain renderizado com tenants:", ", ".join(t[0] for t in tenants))
PY

docker rm -f cloudif-tenant-router 2>/dev/null || true
docker run -d \
  --name cloudif-tenant-router \
  --restart unless-stopped \
  --network host \
  -v /srv/cloudif/router/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro \
  -v /srv/cloudif/router/mtls:/etc/nginx/mtls:ro \
  -v /srv/cloudif/router/logs:/var/log/nginx \
  nginx:stable-alpine >/dev/null

sleep 2
docker exec cloudif-tenant-router nginx -t
echo "OK: cloudif-tenant-router atualizado."

# CloudIF v234 persistent AuthZ post-render BEGIN
if [ -x /srv/cloudif/bin/cloudif-apply-router-authz-v233.sh ]; then
  /srv/cloudif/bin/cloudif-apply-router-authz-v233.sh || {
    echo "ERRO: CloudIF AuthZ v233 post-render falhou" >&2
    exit 1
  }
fi
# CloudIF v234 persistent AuthZ post-render END


# CloudIF portal v1 post-render BEGIN
if [ -x /srv/cloudif/bin/cloudif-apply-router-portal-v1.sh ]; then
  /srv/cloudif/bin/cloudif-apply-router-portal-v1.sh /srv/cloudif/router/conf.d/default.conf || {
    echo "ERRO: CloudIF portal post-render falhou" >&2
    exit 1
  }
fi
# CloudIF portal v1 post-render END


# CloudIF tenant control v134 post-render normalization BEGIN
python3 - <<'PY'
from pathlib import Path
p=Path('/srv/cloudif/router/conf.d/default.conf')
if p.exists():
 s=p.read_text()
 s=s.replace('error_page 403 = @cloudif_forbidden_v244;\n\n        auth_request_set $auth_cookie', 'error_page 403 = @cloudif_portal_forbidden_v134;\n        proxy_intercept_errors off;\n\n        auth_request_set $auth_cookie',1)
 if '@cloudif_portal_forbidden_v134 {' not in s:
  anchor='    # CloudIF portal v1 BEGIN\n'
  h='''    location @cloudif_portal_forbidden_v134 {\n        internal;\n        default_type text/html;\n        add_header Cache-Control no-store always;\n        return 403 'CloudIF Portal: operação não autorizada pela política do Portal.';\n    }\n\n'''
  if anchor in s:s=s.replace(anchor,h+anchor,1)
 p.write_text(s)
PY
# CloudIF tenant control v134 post-render normalization END
