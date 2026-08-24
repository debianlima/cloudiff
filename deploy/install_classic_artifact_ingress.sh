#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
STATE=${CLOUDIFF_CLASSIC_INGRESS_STATE:-/var/lib/cloudiff-v2/classic-artifact-ingress}
TOKEN_FILE=/etc/cloudiff-v2/classic-artifact.token
SOCKET_UNIT=cloudiff-v2-artifact-classic-ingress.socket
SERVICE_UNIT=cloudiff-v2-artifact-classic-ingress.service
ARTIFACT_SERVICE=cloudiff-v2-artifact-executor-shadow.service
NPM_CONF=/srv/cloudif/proxy/npm/data/nginx/custom/http.conf
WORKER_ENV=/etc/cloudiff-v2/build-worker.env
ARTIFACT_ENV=/etc/cloudiff-v2/artifact-shadow.env
ARTIFACT_PTR=/opt/cloudiff-v2/artifact-shadow-current
ARTIFACT_PREVIOUS=/opt/cloudiff-v2/artifact-shadow-previous
ARTIFACT_RELEASE=/opt/cloudiff-v2/releases/20260821-v27-artifact-shadow
WORKER_PTR=/opt/cloudiff-v2/build-worker-current
WORKER_PREVIOUS=/opt/cloudiff-v2/build-worker-previous
WORKER_RELEASE=/opt/cloudiff-v2/releases/20260821-v27-build-worker
BEGIN='# CloudIFF ClassicArtifactIngress BEGIN'
END='# CloudIFF ClassicArtifactIngress END'
install -d -m 0700 "$STATE"

check_token(){
  [ -f "$TOKEN_FILE" ]
  [ "$(stat -c '%a' "$TOKEN_FILE")" = 600 ]
  [ "$(stat -c '%U:%G' "$TOKEN_FILE")" = root:root ]
  local n;n=$(tr -d '\r\n' < "$TOKEN_FILE" | wc -c | tr -d ' ')
  [ "$n" = 64 ]
}
set_env_value(){
  local file=$1 key=$2 value=$3
  python3 - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);k=sys.argv[2];v=sys.argv[3]
lines=p.read_text().splitlines();out=[];done=False
for line in lines:
    if line.startswith(k+'='):
        if not done:out.append(k+'='+v);done=True
    else:out.append(line)
if not done:out.append(k+'='+v)
p.write_text('\n'.join(out)+'\n')
PY
}

forja_apply(){
  check_token;install -d -m 0700 "$STATE/forja"
  [ -s "$STATE/forja/artifact-env.before" ] || cp -p "$ARTIFACT_ENV" "$STATE/forja/artifact-env.before"
  for u in "$SOCKET_UNIT" "$SERVICE_UNIT"; do
    if [ -e "/etc/systemd/system/$u" ] && [ ! -e "$STATE/forja/$u.before" ]; then cp -p "/etc/systemd/system/$u" "$STATE/forja/$u.before"; fi
  done
  [ -x "$ARTIFACT_RELEASE/bin/cloudiff-agent" ];[ -L "$ARTIFACT_PREVIOUS" ]
  [ -s "$STATE/forja/artifact-pointer.before" ] || readlink -f "$ARTIFACT_PREVIOUS" > "$STATE/forja/artifact-pointer.before"
  token=$(tr -d '\r\n' < "$TOKEN_FILE");set_env_value "$ARTIFACT_ENV" CLOUDIFF_ARTIFACT_CLASSIC_TOKEN "$token";unset token
  chmod 0600 "$ARTIFACT_ENV";chown root:root "$ARTIFACT_ENV";ln -sfn "$ARTIFACT_RELEASE" "$ARTIFACT_PTR"
  install -m 0644 "$ROOT/deploy/systemd/$SOCKET_UNIT" "/etc/systemd/system/$SOCKET_UNIT"
  install -m 0644 "$ROOT/deploy/systemd/$SERVICE_UNIT" "/etc/systemd/system/$SERVICE_UNIT"
  systemctl daemon-reload
  systemd-analyze verify "/etc/systemd/system/$SOCKET_UNIT" "/etc/systemd/system/$SERVICE_UNIT"
  systemctl restart "$ARTIFACT_SERVICE"
  for _ in $(seq 1 60);do curl -fsS --max-time 2 http://127.0.0.1:18226/health >/dev/null 2>&1&&break;sleep .25;done
  curl -fsS --max-time 3 http://127.0.0.1:18226/health >/dev/null
  systemctl enable --now "$SOCKET_UNIT"
  systemctl is-active --quiet "$SOCKET_UNIT"
  ss -H -lnt | grep -q '10.62.91.2:18228'
  echo FORJA_CLASSIC_INGRESS=PASS
}
forja_rollback(){
  systemctl disable --now "$SOCKET_UNIT" >/dev/null 2>&1 || true
  [ -s "$STATE/forja/artifact-env.before" ] && cp -p "$STATE/forja/artifact-env.before" "$ARTIFACT_ENV"
  rm -f "/etc/systemd/system/$SOCKET_UNIT" "/etc/systemd/system/$SERVICE_UNIT"
  if [ -s "$STATE/forja/artifact-pointer.before" ];then ln -sfn "$(cat "$STATE/forja/artifact-pointer.before")" "$ARTIFACT_PTR";else ln -sfn "$(readlink -f "$ARTIFACT_PREVIOUS")" "$ARTIFACT_PTR";fi
  systemctl daemon-reload;systemctl restart "$ARTIFACT_SERVICE";echo FORJA_CLASSIC_INGRESS_ROLLBACK=PASS
}

npm_block(){ cat <<'NGINX'
# CloudIFF ClassicArtifactIngress BEGIN
server {
    listen 80;
    server_name cloudif-artifact-executor-v2.internal;
    allow 10.62.92.7;
    deny all;
    location = /v1/build {
        if ($request_method != POST) { return 405; }
        proxy_http_version 1.1;
        proxy_set_header Host 127.0.0.1;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For "";
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Content-Type $http_content_type;
        proxy_pass http://10.62.91.2:18228/v1/build;
        proxy_read_timeout 950s;
        proxy_send_timeout 950s;
    }
    location / { return 404; }
}
# CloudIFF ClassicArtifactIngress END
NGINX
}
npm_apply(){
  install -d -m 0700 "$STATE/npm";local ts;ts=$(date -u +%Y%m%dT%H%M%SZ)
  cp -p "$NPM_CONF" "$STATE/npm/http.$ts";printf '%s\n' "$STATE/npm/http.$ts" > "$STATE/npm/previous";chmod 0600 "$STATE/npm/previous"
  block=$(mktemp);npm_block > "$block"
  python3 - "$NPM_CONF" "$block" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();block=Path(sys.argv[2]).read_text().rstrip()+'\n';begin='# CloudIFF ClassicArtifactIngress BEGIN';end='# CloudIFF ClassicArtifactIngress END';anchor='# CloudIF artifact executor internal BEGIN'
while begin in s:
 i=s.index(begin);j=s.find(end,i)
 if j<0:raise SystemExit('unterminated ingress block')
 j+=len(end);s=s[:i]+s[j:].lstrip('\n')
if anchor not in s:raise SystemExit('legacy artifact anchor missing')
p.write_text(s.replace(anchor,block+'\n'+anchor,1))
PY
  rm -f "$block"
  if ! docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1;then cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1||true;exit 4;fi
  docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo NPM_CLASSIC_INGRESS=PASS
}
npm_rollback(){
  [ -s "$STATE/npm/previous" ];cp -p "$(cat "$STATE/npm/previous")" "$NPM_CONF";docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null;docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null;echo NPM_CLASSIC_INGRESS_ROLLBACK=PASS
}

worker_apply(){
  check_token;install -d -m 0700 "$STATE/worker";[ -s "$STATE/worker/build-worker.env.before" ]||cp -p "$WORKER_ENV" "$STATE/worker/build-worker.env.before";[ -s "$STATE/worker/build-worker-pointer.before" ]||readlink -f "$WORKER_PREVIOUS" > "$STATE/worker/build-worker-pointer.before"
  [ -x "$WORKER_RELEASE/bin/cloudiff-worker" ];ln -sfn "$WORKER_RELEASE" "$WORKER_PTR"
  token=$(tr -d '\r\n' < "$TOKEN_FILE")
  set_env_value "$WORKER_ENV" CLOUDIFF_BUILD_ARTIFACT_HOST 10.62.91.3
  set_env_value "$WORKER_ENV" CLOUDIFF_BUILD_ARTIFACT_PORT 80
  set_env_value "$WORKER_ENV" CLOUDIFF_BUILD_ARTIFACT_HOST_HEADER cloudif-artifact-executor-v2.internal
  set_env_value "$WORKER_ENV" CLOUDIFF_BUILD_ARTIFACT_TOKEN "$token";unset token
  chmod 0640 "$WORKER_ENV";chown root:cloudiff-v2-worker "$WORKER_ENV";echo WORKER_CLASSIC_INGRESS=PASS
}
worker_rollback(){ [ -s "$STATE/worker/build-worker.env.before" ];cp -p "$STATE/worker/build-worker.env.before" "$WORKER_ENV";if [ -s "$STATE/worker/build-worker-pointer.before" ];then ln -sfn "$(cat "$STATE/worker/build-worker-pointer.before")" "$WORKER_PTR";else ln -sfn "$(readlink -f "$WORKER_PREVIOUS")" "$WORKER_PTR";fi;echo WORKER_CLASSIC_INGRESS_ROLLBACK=PASS; }


case "$ACTION" in
 forja-apply)forja_apply;;
 forja-rollback)forja_rollback;;
 npm-apply)npm_apply;;
 npm-rollback)npm_rollback;;
 worker-apply)worker_apply;;
 worker-rollback)worker_rollback;;
 status)
   printf 'TOKEN_FILE=';[ -f "$TOKEN_FILE" ]&&echo present||echo absent
   printf 'SOCKET=';systemctl is-active "$SOCKET_UNIT" 2>/dev/null||true
   printf 'NPM_MARKER=';grep -Fq "$BEGIN" "$NPM_CONF" 2>/dev/null&&echo yes||echo no
   printf 'WORKER_HOST=';sed -n 's/^CLOUDIFF_BUILD_ARTIFACT_HOST_HEADER=//p' "$WORKER_ENV" 2>/dev/null||true;;
 *)echo 'usage: install_classic_artifact_ingress.sh forja-apply|forja-rollback|npm-apply|npm-rollback|worker-apply|worker-rollback|status' >&2;exit 2;;
esac
