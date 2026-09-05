#!/bin/bash
set -euo pipefail
MODE=${1:-apply}
NPM_COMPOSE=${NPM_COMPOSE:-/srv/cloudif/proxy/npm/docker-compose.yml}
STATE=/srv/cloudif/releases/remote-443-relay
backup(){ mkdir -p "$STATE"; [ -f "$STATE/npm-compose.before" ] || cp -a "$NPM_COMPOSE" "$STATE/npm-compose.before"; }
apply(){
  backup
  python3 - "$NPM_COMPOSE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if '127.0.0.1:10443:443' not in s:
    assert '443:443' in s
    s=s.replace('"443:443"','"127.0.0.1:10443:443"',1)
p.write_text(s)
PY
  (cd "$(dirname "$NPM_COMPOSE")" && docker compose config -q && docker compose up -d --force-recreate nginx-proxy-manager >/dev/null)
  for i in $(seq 1 120);do curl -ksS --resolve cloudiff.duckdns.org:10443:127.0.0.1 -o /dev/null https://cloudiff.duckdns.org:10443/ >/dev/null 2>&1&&break;sleep .25;done
  systemctl enable --now cloudif-remote-gateway.service cloudif-remote-gateway-sync.service cloudif-remote-gateway-reaper.timer cloudif-443-relay.service >/dev/null
  systemctl is-active --quiet cloudif-443-relay.service
}
rollback(){
  systemctl disable --now cloudif-443-relay.service cloudif-remote-gateway-reaper.timer cloudif-remote-gateway-sync.service cloudif-remote-gateway.service 2>/dev/null||true
  [ -f "$STATE/npm-compose.before" ] || { echo missing_backup >&2; exit 2; }
  cp -a "$STATE/npm-compose.before" "$NPM_COMPOSE"
  (cd "$(dirname "$NPM_COMPOSE")" && docker compose up -d --force-recreate nginx-proxy-manager >/dev/null)
}
case "$MODE" in apply) apply;; rollback) rollback;; *) echo 'usage: install_remote_443_relay.sh [apply|rollback]' >&2;exit 2;; esac
