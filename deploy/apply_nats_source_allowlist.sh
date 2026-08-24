#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-apply}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
COMPOSE="$ROOT/deploy/compose.yaml"
PROJECT_DIR=$(dirname "$COMPOSE")
PROJECT=$(docker inspect cloudiff-v2-nats --format '{{ index .Config.Labels "com.docker.compose.project" }}' 2>/dev/null || true)
PROJECT=${PROJECT:-deploy}
STATE=/var/lib/cloudiff-v2/nats-source-allowlist
SOCKET=cloudiff-v2-nats-source-allowlist.socket
SERVICE=cloudiff-v2-nats-source-allowlist.service
install -d -m 0700 "$STATE"
health(){ curl -fsS --max-time 4 http://127.0.0.1:18222/varz >/dev/null; }
stop_proxy(){
  systemctl stop "$SOCKET" >/dev/null 2>&1 || true
  systemctl stop "$SERVICE" >/dev/null 2>&1 || true
  for _ in $(seq 1 30);do ! ss -H -lnt | grep -q '10.62.92.7:14222' && break;sleep .1;done
  ! ss -H -lnt | grep -q '10.62.92.7:14222'
}
ensure_network(){
  local net="${PROJECT}_default"
  if ! docker inspect cloudiff-v2-nats --format '{{json .NetworkSettings.Networks}}' | grep -q "\"$net\""; then
    docker network inspect "$net" >/dev/null
    docker network connect "$net" cloudiff-v2-nats
  fi
}
write_rollback_compose(){
  python3 - "$COMPOSE" "$STATE/rollback-compose.yaml" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
needle='      - "127.0.0.1:14222:4222"\n'
external='      - "10.62.92.7:14222:4222"\n'
if needle not in src:
    raise SystemExit('loopback NATS port anchor missing')
if external not in src:
    src=src.replace(needle,needle+external,1)
Path(sys.argv[2]).write_text(src)
PY
  chmod 0600 "$STATE/rollback-compose.yaml"
  docker compose --project-directory "$PROJECT_DIR" -p "$PROJECT" -f "$STATE/rollback-compose.yaml" config --quiet
}
install_units(){
  install -m 0644 "$ROOT/deploy/systemd/$SERVICE" "/etc/systemd/system/$SERVICE"
  install -m 0644 "$ROOT/deploy/systemd/$SOCKET" "/etc/systemd/system/$SOCKET"
  systemctl daemon-reload
  systemd-analyze verify "/etc/systemd/system/$SERVICE" "/etc/systemd/system/$SOCKET" >/dev/null
}
apply_proxy(){
  grep -q '127.0.0.1:14222:4222' "$COMPOSE"
  ! grep -q '10.62.92.7:14222:4222' "$COMPOSE"
  write_rollback_compose
  install_units
  systemctl disable "$SOCKET" >/dev/null 2>&1 || true
  stop_proxy
  docker compose --project-directory "$PROJECT_DIR" -p "$PROJECT" -f "$COMPOSE" up -d --force-recreate nats >/dev/null
  ensure_network
  for _ in $(seq 1 60);do health && break;sleep .25;done
  health
  systemctl enable --now "$SOCKET" >/dev/null
  systemctl is-active --quiet "$SOCKET"
  ss -H -lnt | grep -q '10.62.92.7:14222'
  python3 - <<'PY'
import json,subprocess
x=json.loads(subprocess.check_output("docker inspect cloudiff-v2-nats --format '{{json .HostConfig.PortBindings}}'",shell=True,text=True))
assert x['4222/tcp']==[{'HostIp':'127.0.0.1','HostPort':'14222'}]
PY
  echo NATS_SOCKET_PROXY_ALLOWLIST=PASS
}
rollback(){
  write_rollback_compose
  systemctl disable "$SOCKET" >/dev/null 2>&1 || true
  stop_proxy
  docker compose --project-directory "$PROJECT_DIR" -p "$PROJECT" -f "$STATE/rollback-compose.yaml" up -d --force-recreate nats >/dev/null
  ensure_network
  for _ in $(seq 1 60);do health && break;sleep .25;done
  health
  ss -H -lnt | grep -q '10.62.92.7:14222'
  python3 - <<'PY'
import json,subprocess
x=json.loads(subprocess.check_output("docker inspect cloudiff-v2-nats --format '{{json .HostConfig.PortBindings}}'",shell=True,text=True))
b=x['4222/tcp'];assert {'HostIp':'127.0.0.1','HostPort':'14222'} in b and {'HostIp':'10.62.92.7','HostPort':'14222'} in b
PY
  echo NATS_SOCKET_PROXY_ROLLBACK=PASS
}
case "$ACTION" in
  apply) if ! apply_proxy;then rollback || true;exit 4;fi;;
  rollback) rollback;;
  status)
    printf 'SOCKET=';systemctl is-active "$SOCKET" 2>/dev/null||true
    printf 'SOCKET_ENABLED=';systemctl is-enabled "$SOCKET" 2>/dev/null||true
    printf 'NATS_LOCAL=';ss -H -lnt|grep -q '127.0.0.1:14222'&&echo yes||echo no
    printf 'NATS_EXTERNAL=';ss -H -lnt|grep -q '10.62.92.7:14222'&&echo yes||echo no
    ;;
  *)echo 'usage: apply_nats_source_allowlist.sh apply|rollback|status' >&2;exit 2;;
esac
