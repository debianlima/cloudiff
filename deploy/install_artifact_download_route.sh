#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROUTER_CONF=${CLOUDIFF_ROUTER_CONF:-/srv/cloudif/router/conf.d/default.conf}
NPM_CONF=${CLOUDIFF_NPM_SERVER_PROXY_CONF:-/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf}
STATE=${CLOUDIFF_DOWNLOAD_ROUTE_STATE:-/var/lib/cloudiff-v2/mcp-download-route}
ROUTER_BEGIN='# CloudIFF ArtifactDownloadCapability router BEGIN'
ROUTER_END='# CloudIFF ArtifactDownloadCapability router END'
NPM_BEGIN='# CloudIFF ArtifactDownloadCapability npm BEGIN'
NPM_END='# CloudIFF ArtifactDownloadCapability npm END'
router_block(){ cat <<'NGINX'
# CloudIFF ArtifactDownloadCapability router BEGIN
location ~ "^/cloudiff/artifact-download/(dlt_[a-f0-9]{24}_[a-f0-9]{48})$" {
    access_log off;
    error_log /dev/null crit;
    if ($request_method != GET) { return 405; }
    if ($args != "") { return 400; }
    set $cloudiff_download_ticket $1;
    proxy_http_version 1.1;
    proxy_set_header Host 127.0.0.1;
    proxy_set_header Authorization "";
    proxy_set_header X-CloudIF-Download-Ticket $cloudiff_download_ticket;
    proxy_set_header X-Real-IP 127.0.0.1;
    proxy_set_header X-Forwarded-For "";
    proxy_set_header X-Forwarded-Proto https;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 7200s;
    proxy_send_timeout 7200s;
    rewrite ^ /v1/artifact/download/capability/read break;
    proxy_pass http://127.0.0.1:18206;
}
# CloudIFF ArtifactDownloadCapability router END
NGINX
}
npm_block(){ cat <<'NGINX'
# CloudIFF ArtifactDownloadCapability npm BEGIN
location ^~ /cloudiff/artifact-download/ {
    access_log off;
    error_log /dev/null crit;
    if ($request_method != GET) { return 405; }
    if ($args != "") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Host $host;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 7200s;
    proxy_send_timeout 7200s;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    proxy_pass http://10.62.92.7:8099;
}
# CloudIFF ArtifactDownloadCapability npm END
NGINX
}
replace_block(){
  local conf=$1 begin=$2 end=$3 block_fn=$4 anchor=$5 backup_dir=$6
  [ -f "$conf" ];install -d -m 0700 "$backup_dir";local ts;ts=$(date -u +%Y%m%dT%H%M%SZ);cp -p "$conf" "$backup_dir/config.$ts";printf '%s\n' "$backup_dir/config.$ts" > "$backup_dir/previous";chmod 0600 "$backup_dir/previous"
  local block_file;block_file=$(mktemp);$block_fn > "$block_file"
  python3 - "$conf" "$begin" "$end" "$anchor" "$block_file" <<'PY'
from pathlib import Path
import sys
conf,begin,end,anchor,bf=sys.argv[1:];p=Path(conf);s=p.read_text();block=Path(bf).read_text().rstrip()+"\n"
while begin in s:
 i=s.index(begin);j=s.find(end,i)
 if j<0:raise SystemExit('unterminated managed block')
 j+=len(end);s=s[:i]+s[j:].lstrip('\n')
if anchor not in s:raise SystemExit('route anchor missing')
s=s.replace(anchor,block+'\n'+anchor,1);p.write_text(s)
PY
  rm -f "$block_file"
}
case "$ACTION" in
 router-apply)
   replace_block "$ROUTER_CONF" "$ROUTER_BEGIN" "$ROUTER_END" router_block '# CloudIF portal v1 BEGIN' "$STATE/router"
   if ! docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1; then cp -p "$(cat "$STATE/router/previous")" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1 || true;exit 4;fi
   docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo ROUTER_ROUTE=PASS;;
 router-rollback)
   [ -s "$STATE/router/previous" ];cp -p "$(cat "$STATE/router/previous")" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null;docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo ROUTER_ROLLBACK=PASS;;
 npm-apply)
   replace_block "$NPM_CONF" "$NPM_BEGIN" "$NPM_END" npm_block '# CloudIFF SecureDistribution HTTPS BEGIN' "$STATE/npm"
   if ! docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1; then cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1 || true;exit 4;fi
   docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo NPM_ROUTE=PASS;;
 npm-rollback)
   [ -s "$STATE/npm/previous" ];cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null;docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo NPM_ROLLBACK=PASS;;
 status)
   printf 'ROUTER_INSTALLED=';grep -Fq "$ROUTER_BEGIN" "$ROUTER_CONF" 2>/dev/null&&echo yes||echo no
   printf 'NPM_INSTALLED=';grep -Fq "$NPM_BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no;;
 *) echo 'usage: install_artifact_download_route.sh router-apply|router-rollback|npm-apply|npm-rollback|status' >&2;exit 2;;
esac
