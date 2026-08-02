#!/usr/bin/env bash
set -Eeuo pipefail

CONF="${1:-/srv/cloudif/router/conf.d/default.conf}"
ROUTER="${CLOUDIF_ROUTER_CONTAINER:-cloudif-tenant-router}"
NOW="$(date +%Y%m%d-%H%M%S)"
BKDIR="/srv/cloudif/backups/apply-router-portal-direct-auth-$NOW"

mkdir -p "$BKDIR"

[ -f "$CONF" ] || {
  echo "ERRO: não existe $CONF"
  exit 1
}

cp -a "$CONF" "$BKDIR/default.conf.bkp-$NOW"

python3 - "$CONF" <<'PY'
from pathlib import Path
import re
import sys

p = Path(sys.argv[1])
txt = p.read_text(errors="ignore")

# Remove portal anterior.
txt = re.sub(
    r'\n\s*# CloudIF portal v1 BEGIN.*?# CloudIF portal v1 END\n',
    '\n',
    txt,
    flags=re.S,
)

# Remove portal-auth anterior.
txt = re.sub(
    r'\n\s*# CloudIF portal-auth v1 BEGIN.*?# CloudIF portal-auth v1 END\n',
    '\n',
    txt,
    flags=re.S,
)

portal_auth = r'''
    # CloudIF portal-auth v1 BEGIN
    location = /cloudiff/portal-auth {
        internal;
        proxy_pass http://10.62.91.2:9000/outpost.goauthentik.io/auth/nginx;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";

        proxy_set_header Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_set_header X-Original-URL https://$http_host$request_uri;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-Uri $request_uri;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_intercept_errors off;
    }
    # CloudIF portal-auth v1 END

'''

portal = r'''
    # CloudIF portal v1 BEGIN
    location ^~ /cloudiff/portal/ {
        auth_request /cloudiff/portal-auth;
        error_page 401 = @cloudif_authentik_signin_v244;
        error_page 403 = @cloudif_forbidden_v244;

        auth_request_set $auth_cookie $upstream_http_set_cookie;
        add_header Set-Cookie $auth_cookie always;

        auth_request_set $authentik_username $upstream_http_x_authentik_username;
        auth_request_set $authentik_email $upstream_http_x_authentik_email;
        auth_request_set $authentik_groups $upstream_http_x_authentik_groups;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-authentik-username $authentik_username;
        proxy_set_header X-authentik-email $authentik_email;
        proxy_set_header X-authentik-groups $authentik_groups;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # Preserve o prefixo público. O Portal usa /cloudiff/portal/ para selecionar o shell atual.
        proxy_pass http://10.62.92.7:18094;
    }
    # CloudIF portal v1 END

'''

marker = "    location = /health"
if marker not in txt:
    raise SystemExit("ERRO: não encontrei location = /health.")

txt = txt.replace(marker, portal_auth + portal + marker, 1)

p.write_text(txt)
print("OK: portal-auth direto inserido.")
PY

docker exec "$ROUTER" nginx -t
docker exec "$ROUTER" nginx -s reload || docker restart "$ROUTER"

echo "OK: portal com Authentik direto aplicado ao router."
