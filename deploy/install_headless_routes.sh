#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROUTER_CONF=${CLOUDIFF_ROUTER_CONF:-/srv/cloudif/router/conf.d/default.conf}
NPM_CONF=${CLOUDIFF_NPM_SERVER_PROXY_CONF:-/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf}
STATE=${CLOUDIFF_HEADLESS_ROUTE_STATE:-/var/lib/cloudiff-v2/headless-routes-v51}
CLIENT_CA_SOURCE=${CLOUDIFF_HEADLESS_CLIENT_CA_SOURCE:-/etc/cloudiff-v2/headless-client-ca.pem}
CLIENT_CA_DEST=${CLOUDIFF_HEADLESS_CLIENT_CA_DEST:-/srv/cloudif/proxy/npm/data/nginx/custom/cloudiff-agent-client-ca.pem}
MTLS_BEGIN='# CloudIFF Headless mTLS server BEGIN'
MTLS_END='# CloudIFF Headless mTLS server END'
ROUTER_BEGIN='# CloudIFF AgentUpdate router BEGIN'
ROUTER_END='# CloudIFF AgentUpdate router END'
AGENT_BEGIN='# CloudIFF AgentUpdate npm BEGIN'
AGENT_END='# CloudIFF AgentUpdate npm END'
DIST_BEGIN='# CloudIFF SecureDistribution HTTPS BEGIN'
DIST_END='# CloudIFF SecureDistribution HTTPS END'
mtls_block(){ cat <<'NGINX'
# CloudIFF Headless mTLS server BEGIN
ssl_client_certificate /data/nginx/custom/cloudiff-agent-client-ca.pem;
ssl_verify_client optional;
ssl_verify_depth 3;
# CloudIFF Headless mTLS server END
NGINX
}
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
agent_block(){ cat <<'NGINX'
# CloudIFF AgentUpdate npm BEGIN
location = /cloudiff/portal/api/node-recovery-policy {
    if ($host != cloudiff.duckdns.org) { return 404; }
    if ($ssl_client_verify != SUCCESS) { return 403; }
    access_log off;
    error_log /dev/null crit;
    limit_except GET HEAD { deny all; }
    if ($arg_node_id !~* "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host cloudiff.duckdns.org;
    proxy_set_header Authorization "";
    proxy_set_header X-CloudIFF-Client-DN $ssl_client_s_dn;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    proxy_pass http://10.62.92.7:8099;
}
location ^~ /__cloudiff_agent_updates/ {
    if ($host != cloudiff.duckdns.org) { return 404; }
    if ($ssl_client_verify != SUCCESS) { return 403; }
    access_log off;
    error_log /dev/null crit;
    limit_except GET HEAD { deny all; }
    if ($args != "") { return 400; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Authorization "";
    proxy_set_header X-CloudIFF-Client-DN $ssl_client_s_dn;
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
distribution_block(){ cat <<'NGINX'
# CloudIFF SecureDistribution HTTPS BEGIN
location ^~ /__cloudif_distribution/ {
    if ($host != cloudiff.duckdns.org) { return 404; }
    if ($ssl_client_verify != SUCCESS) { return 403; }
    if ($request_method != GET) { return 405; }
    client_max_body_size 8k;
    proxy_http_version 1.1;
    proxy_set_header Host 10.62.91.3;
    proxy_set_header X-CloudIFF-Client-DN $ssl_client_s_dn;
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
remove_block(){
  local conf=$1 begin=$2 end=$3
  python3 - "$conf" "$begin" "$end" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();a,b=sys.argv[2:]
while a in s:
 i=s.index(a);j=s.find(b,i)
 if j<0:raise SystemExit('unterminated managed block: '+a)
 j+=len(b);s=s[:i]+s[j:].lstrip('\n')
p.write_text(s)
PY
}
replace_router(){
  local backup_dir="$STATE/router" ts bf
  [ -f "$ROUTER_CONF" ];install -d -m 0700 "$backup_dir";ts=$(date -u +%Y%m%dT%H%M%SZ)
  cp -p "$ROUTER_CONF" "$backup_dir/config.$ts";printf '%s\n' "$backup_dir/config.$ts" > "$backup_dir/previous";chmod 0600 "$backup_dir/previous"
  remove_block "$ROUTER_CONF" "$ROUTER_BEGIN" "$ROUTER_END"
  bf=$(mktemp);router_block > "$bf"
  python3 - "$ROUTER_CONF" "$bf" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();block=Path(sys.argv[2]).read_text().rstrip()+"\n";anchor='# CloudIF portal v1 BEGIN'
if anchor not in s:raise SystemExit('router anchor missing')
p.write_text(s.replace(anchor,block+'\n'+anchor,1))
PY
  rm -f "$bf"
}
replace_npm(){
  local backup_dir="$STATE/npm" ts mt ag ds body
  [ -f "$NPM_CONF" ];[ -r "$CLIENT_CA_SOURCE" ];openssl x509 -in "$CLIENT_CA_SOURCE" -noout >/dev/null
  install -d -m 0700 "$backup_dir";ts=$(date -u +%Y%m%dT%H%M%SZ)
  cp -p "$NPM_CONF" "$backup_dir/config.$ts";printf '%s\n' "$backup_dir/config.$ts" > "$backup_dir/previous";chmod 0600 "$backup_dir/previous"
  if [ -f "$CLIENT_CA_DEST" ];then cp -p "$CLIENT_CA_DEST" "$backup_dir/client-ca.$ts";printf '%s\n' "$backup_dir/client-ca.$ts" > "$backup_dir/previous-ca";else : > "$backup_dir/previous-ca";fi
  install -D -o root -g root -m 0644 "$CLIENT_CA_SOURCE" "$CLIENT_CA_DEST"
  for pair in "$MTLS_BEGIN|$MTLS_END" "$AGENT_BEGIN|$AGENT_END" "$DIST_BEGIN|$DIST_END";do remove_block "$NPM_CONF" "${pair%%|*}" "${pair#*|}";done
  mt=$(mktemp);ag=$(mktemp);ds=$(mktemp);body=$(mktemp);mtls_block >"$mt";agent_block >"$ag";distribution_block >"$ds"
  cat "$mt" "$ag" "$ds" > "$body"
  cat "$NPM_CONF" >> "$body";cat "$body" > "$NPM_CONF"
  rm -f "$mt" "$ag" "$ds" "$body"
}
validate_npm(){ docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null;docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null; }
case "$ACTION" in
 router-apply)
   replace_router
   if ! docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1;then cp -p "$(cat "$STATE/router/previous")" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null 2>&1||true;exit 4;fi
   docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo HEADLESS_ROUTER=PASS;;
 router-rollback)
   [ -s "$STATE/router/previous" ];cp -p "$(cat "$STATE/router/previous")" "$ROUTER_CONF";docker exec cloudif-tenant-router nginx -t >/dev/null;docker exec cloudif-tenant-router nginx -s reload >/dev/null;echo HEADLESS_ROUTER_ROLLBACK=PASS;;
 npm-apply)
   replace_npm
   if ! validate_npm;then cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";if [ -s "$STATE/npm/previous-ca" ];then cp -p "$(cat "$STATE/npm/previous-ca")" "$CLIENT_CA_DEST";else rm -f "$CLIENT_CA_DEST";fi;validate_npm||true;echo HEADLESS_NPM_ROLLBACK >&2;exit 4;fi
   echo HEADLESS_NPM=PASS;;
 npm-rollback)
   [ -s "$STATE/npm/previous" ];cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";if [ -s "$STATE/npm/previous-ca" ];then cp -p "$(cat "$STATE/npm/previous-ca")" "$CLIENT_CA_DEST";else rm -f "$CLIENT_CA_DEST";fi;validate_npm;echo HEADLESS_NPM_ROLLBACK=PASS;;
 status)
   printf 'ROUTER_INSTALLED=';grep -Fq "$ROUTER_BEGIN" "$ROUTER_CONF" 2>/dev/null&&echo yes||echo no
   printf 'NPM_MTLS_INSTALLED=';grep -Fq "$MTLS_BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no
   printf 'NPM_AGENT_UPDATE_INSTALLED=';grep -Fq "$AGENT_BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no
   printf 'NPM_DISTRIBUTION_INSTALLED=';grep -Fq "$DIST_BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no
   printf 'CLIENT_CA_INSTALLED=';[ -r "$CLIENT_CA_DEST" ]&&echo yes||echo no;;
 *)echo 'usage: install_headless_routes.sh router-apply|router-rollback|npm-apply|npm-rollback|status' >&2;exit 2;;
esac
