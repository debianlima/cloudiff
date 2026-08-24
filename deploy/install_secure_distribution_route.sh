#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
CONF=${CLOUDIFF_NPM_SERVER_PROXY_CONF:-/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf}
BACKUP_DIR=${CLOUDIFF_DISTRIBUTION_ROUTE_BACKUP_DIR:-/var/lib/cloudiff-v2/secure-distribution-route}
BEGIN='# CloudIFF SecureDistribution HTTPS BEGIN'
END='# CloudIFF SecureDistribution HTTPS END'
block(){ cat <<'NGINX'
# CloudIFF SecureDistribution HTTPS BEGIN
location ^~ /__cloudif_distribution/ {
    if ($host != cloudiff.duckdns.org) { return 404; }
    if ($request_method != GET) { return 405; }
    allow 10.62.92.7;
    deny all;
    client_max_body_size 8k;
    proxy_http_version 1.1;
    proxy_set_header Host 10.62.91.3;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-CloudIFF-Audience $http_x_cloudiff_audience;
    proxy_set_header X-CloudIFF-Expected-Generation $http_x_cloudiff_expected_generation;
    proxy_pass http://10.62.91.3:18240/;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
}
# CloudIFF SecureDistribution HTTPS END
NGINX
}
validate_reload(){ docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null; docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null; }
mkdir -p "$BACKUP_DIR"; chmod 0700 "$BACKUP_DIR"; touch "$CONF"
case "$ACTION" in
 status) if grep -Fq "$BEGIN" "$CONF"; then echo INSTALLED=yes; else echo INSTALLED=no; fi;;
 apply)
   ts=$(date -u +%Y%m%dT%H%M%SZ);cp -p "$CONF" "$BACKUP_DIR/server_proxy.$ts.conf";printf '%s\n' "$BACKUP_DIR/server_proxy.$ts.conf" > "$BACKUP_DIR/previous"
   python3 - "$CONF" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();a,b=sys.argv[2:]
while a in s:
 i=s.index(a);j=s.find(b,i)
 if j<0:raise SystemExit('unterminated distribution block')
 j+=len(b);s=s[:i]+s[j:].lstrip('\n')
p.write_text(s.rstrip()+('\n' if s.strip() else ''))
PY
   block >> "$CONF"
   if ! validate_reload; then cp -p "$(cat "$BACKUP_DIR/previous")" "$CONF";validate_reload || true;echo ROUTE_ROLLBACK >&2;exit 4;fi
   echo ROUTE_APPLY=PASS;;
 rollback)
   [ -s "$BACKUP_DIR/previous" ];cp -p "$(cat "$BACKUP_DIR/previous")" "$CONF";validate_reload;echo ROUTE_ROLLBACK=PASS;;
 *) echo 'usage: install_secure_distribution_route.sh apply|rollback|status' >&2;exit 2;;
esac
