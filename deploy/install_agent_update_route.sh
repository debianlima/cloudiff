#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROUTER_CONF=${CLOUDIFF_ROUTER_CONF:-/srv/cloudif/router/conf.d/default.conf}
NPM_CONF=${CLOUDIFF_NPM_SERVER_PROXY_CONF:-/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf}
STATE=${CLOUDIFF_AGENT_UPDATE_ROUTE_STATE:-/var/lib/cloudiff-v2/agent-update-route-v35}
ROUTER_BEGIN='# CloudIFF AgentUpdate router BEGIN'
ROUTER_END='# CloudIFF AgentUpdate router END'
NPM_BEGIN='# CloudIFF AgentUpdate npm BEGIN'
NPM_END='# CloudIFF AgentUpdate npm END'
router_block(){ cat <<'NGINX'
# CloudIFF AgentUpdate router BEGIN
location = /cloudiff/portal/api/node-recovery-policy {
    access_log off;
    error_log /dev/null crit;
    allow 10.62.91.3;
    deny all;
    limit_except GET HEAD { deny all; }
    if ($arg_node_id !~* "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host cloudiff.duckdns.org;
    proxy_set_header Authorization "";
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For "";
    proxy_set_header X-Forwarded-Proto https;
    proxy_pass http://10.62.92.7:18094;
}
location ^~ /__cloudiff_agent_updates/ {
    access_log off;
    error_log /dev/null crit;
    allow 10.62.91.3;
    deny all;
    limit_except GET HEAD { deny all; }
    if ($args != "") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host 127.0.0.1;
    proxy_set_header Authorization "";
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For "";
    proxy_set_header X-Forwarded-Proto https;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
    proxy_pass http://127.0.0.1:18250/;
}
# CloudIFF AgentUpdate router END
NGINX
}
npm_block(){ cat <<'NGINX'
# CloudIFF AgentUpdate npm BEGIN
location = /cloudiff/portal/api/node-recovery-policy {
    access_log off;
    error_log /dev/null crit;
    allow 10.62.91.2;
    allow 10.62.91.3;
    allow 10.62.91.5;
    allow 10.62.92.7;
    deny all;
    limit_except GET HEAD { deny all; }
    if ($arg_node_id !~* "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host cloudiff.duckdns.org;
    proxy_set_header Authorization "";
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    proxy_pass http://10.62.92.7:8099;
}
location ^~ /__cloudiff_agent_updates/ {
    access_log off;
    error_log /dev/null crit;
    allow 10.62.91.2;
    allow 10.62.91.3;
    allow 10.62.91.5;
    allow 10.62.92.7;
    deny all;
    limit_except GET HEAD { deny all; }
    if ($args != "") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Authorization "";
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    proxy_pass http://10.62.92.7:8099;
}
# CloudIFF AgentUpdate npm END
NGINX
}
replace_block(){
  local conf=$1 begin=$2 end=$3 block_fn=$4 anchor=$5 backup_dir=$6
  [ -f "$conf" ];install -d -m 0700 "$backup_dir";local ts;ts=$(date -u +%Y%m%dT%H%M%SZ)
  cp -p "$conf" "$backup_dir/config.$ts";printf '%s\n' "$backup_dir/config.$ts" > "$backup_dir/previous";chmod 0600 "$backup_dir/previous"
  if [ ! -s "$backup_dir/baseline" ];then cp -p "$conf" "$backup_dir/baseline";chmod 0600 "$backup_dir/baseline";fi
  local bf;bf=$(mktemp);$block_fn > "$bf"
  python3 - "$conf" "$begin" "$end" "$anchor" "$bf" <<'PY'
from pathlib import Path
import sys
conf,begin,end,anchor,bf=sys.argv[1:];p=Path(conf);s=p.read_text();block=Path(bf).read_text().rstrip()+"\n"
while begin in s:
    i=s.index(begin);j=s.find(end,i)
    if j<0:raise SystemExit('unterminated managed block')
    j+=len(end);s=s[:i]+s[j:].lstrip('\n')
if anchor not in s:raise SystemExit('route anchor missing')
p.write_text(s.replace(anchor,block+'\n'+anchor,1))
PY
  rm -f "$bf"
}
case "$ACTION" in
 router-apply)
   replace_block "$ROUTER_CONF" "$ROUTER_BEGIN" "$ROUTER_END" router_block '# CloudIF portal v1 BEGIN' "$STATE/router"
   if ! docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1;then cp -p "$(cat "$STATE/router/previous")" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1||true;exit 4;fi
   docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo AGENT_UPDATE_ROUTER=PASS;;
 router-rollback)
   [ -s "$STATE/router/baseline" ];cp -p "$STATE/router/baseline" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null;docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo AGENT_UPDATE_ROUTER_ROLLBACK=PASS;;
 npm-apply)
   replace_block "$NPM_CONF" "$NPM_BEGIN" "$NPM_END" npm_block '# CloudIFF SecureDistribution HTTPS BEGIN' "$STATE/npm"
   if ! docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1;then cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1||true;exit 4;fi
   docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo AGENT_UPDATE_NPM=PASS;;
 npm-rollback)
   [ -s "$STATE/npm/baseline" ];cp -p "$STATE/npm/baseline" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null;docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo AGENT_UPDATE_NPM_ROLLBACK=PASS;;
 status)
   printf 'ROUTER_INSTALLED=';grep -Fq "$ROUTER_BEGIN" "$ROUTER_CONF" 2>/dev/null&&echo yes||echo no
   printf 'NPM_INSTALLED=';grep -Fq "$NPM_BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no;;
 *)echo 'usage: install_agent_update_route.sh router-apply|router-rollback|npm-apply|npm-rollback|status' >&2;exit 2;;
esac
