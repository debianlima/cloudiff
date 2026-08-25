#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
NPM_CONF=${CLOUDIFF_NPM_SERVER_PROXY_CONF:-/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf}
STATE=${CLOUDIFF_WEBDEV_ROUTE_STATE:-/var/lib/cloudiff-webdev/route-v44}
BEGIN='# CloudIFF WebDev HTTPS VPN BEGIN'
END='# CloudIFF WebDev HTTPS VPN END'
block(){ cat <<'NGINX'
# CloudIFF WebDev HTTPS VPN BEGIN
location ^~ /__cloudiff_webdev/ {
    if ($host != cloudiff.duckdns.org) { return 404; }
    allow 10.0.0.0/16;
    allow 10.62.91.2;
    allow 10.62.91.3;
    allow 10.62.92.7;
    deny all;
    limit_except GET HEAD { deny all; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    proxy_pass http://10.62.91.2:17900/;
}
# CloudIFF WebDev HTTPS VPN END
NGINX
}
apply(){
  [ -f "$NPM_CONF" ];install -d -m 0700 "$STATE";ts=$(date -u +%Y%m%dT%H%M%SZ)
  cp -p "$NPM_CONF" "$STATE/config.$ts";printf '%s\n' "$STATE/config.$ts" >"$STATE/previous";chmod 0600 "$STATE/previous"
  [ -s "$STATE/baseline" ] || { cp -p "$NPM_CONF" "$STATE/baseline";chmod 0600 "$STATE/baseline"; }
  bf=$(mktemp);block >"$bf"
  python3 - "$NPM_CONF" "$BEGIN" "$END" "$bf" <<'PY'
from pathlib import Path
import sys
conf,begin,end,bf=sys.argv[1:];p=Path(conf);s=p.read_text();block=Path(bf).read_text().rstrip()+"\n"
while begin in s:
 i=s.index(begin);j=s.find(end,i)
 if j<0:raise SystemExit('unterminated managed block')
 j+=len(end);s=s[:i]+s[j:].lstrip('\n')
anchor='# CloudIFF SecureDistribution HTTPS BEGIN'
if anchor not in s:raise SystemExit('anchor missing')
p.write_text(s.replace(anchor,block+'\n'+anchor,1))
PY
  rm -f "$bf"
  if ! docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1;then cp -p "$(cat "$STATE/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1||true;exit 4;fi
  docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null
  echo WEBDEV_ROUTE=PASS
}
rollback(){ [ -s "$STATE/baseline" ];cp -p "$STATE/baseline" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null;docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo WEBDEV_ROUTE_ROLLBACK=PASS; }
status(){ printf 'WEBDEV_ROUTE_INSTALLED=';grep -Fq "$BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no; }
case "$ACTION" in apply)apply;;rollback)rollback;;status)status;;*)echo 'usage: install_webdev_route.sh apply|rollback|status' >&2;exit 2;;esac
