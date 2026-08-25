#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-apply}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
COMPOSE="$ROOT/deploy/compose.webdev.yaml"
UNIT_SOURCE="$ROOT/deploy/systemd/cloudiff-webdev.service"
WORKSPACE=/srv/cloudif/webdev-workspace
RUNTIME_ROOT=/var/lib/cloudiff-webdev
CHAIN=CLOUDIFF_WEBDEV
HOST_IP=10.62.91.2
VIEWER_CIDR=10.0.0.0/16
PROXY_IP=10.62.91.3

assert_forja(){
  local addrs
  addrs=$(ip -4 -o addr show)
  grep -q '10[.]62[.]91[.]2/' <<<"$addrs"
  command -v docker >/dev/null
  docker compose version >/dev/null
}

firewall_apply(){
  assert_forja
  for _ in $(seq 1 60); do
    iptables -S DOCKER-USER >/dev/null 2>&1 && break
    sleep .5
  done
  iptables -S DOCKER-USER >/dev/null 2>&1
  iptables -N "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN"
  iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  iptables -A "$CHAIN" -s "$VIEWER_CIDR" -j RETURN
  iptables -A "$CHAIN" -s "$PROXY_IP/32" -j RETURN
  iptables -A "$CHAIN" -s 127.0.0.0/8 -j RETURN
  iptables -A "$CHAIN" -s "$HOST_IP/32" -j RETURN
  iptables -A "$CHAIN" -j DROP
  while iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdst "$HOST_IP" --ctorigdstport 17900 -j "$CHAIN" 2>/dev/null; do
    iptables -D DOCKER-USER -p tcp -m conntrack --ctorigdst "$HOST_IP" --ctorigdstport 17900 -j "$CHAIN"
  done
  iptables -I DOCKER-USER 1 -p tcp -m conntrack --ctorigdst "$HOST_IP" --ctorigdstport 17900 -j "$CHAIN"
}

firewall_remove(){
  while iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdst "$HOST_IP" --ctorigdstport 17900 -j "$CHAIN" 2>/dev/null; do
    iptables -D DOCKER-USER -p tcp -m conntrack --ctorigdst "$HOST_IP" --ctorigdstport 17900 -j "$CHAIN"
  done
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
}

health(){
  local h=''
  for _ in $(seq 1 120); do
    h=$(docker inspect cloudiff-webdev-browser --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)
    [ "$h" = healthy ] && break
    sleep 1
  done
  [ "$h" = healthy ]
  curl -fsS --max-time 5 http://127.0.0.1:14444/status >/dev/null
}

runtime_equivalent(){
  local cur live_unit=/etc/systemd/system/cloudiff-webdev.service
  cur=$(readlink -f "$RUNTIME_ROOT/current" 2>/dev/null || true)
  [ -n "$cur" ] || return 1
  [ -f "$cur/deploy/compose.webdev.yaml" ] || return 1
  [ -f "$cur/deploy/install_webdev_workspace.sh" ] || return 1
  [ -f "$cur/config/webdev-workspace.json" ] || return 1
  [ -f "$live_unit" ] || return 1
  cmp -s "$cur/deploy/compose.webdev.yaml" "$ROOT/deploy/compose.webdev.yaml" || return 1
  cmp -s "$cur/deploy/install_webdev_workspace.sh" "$ROOT/deploy/install_webdev_workspace.sh" || return 1
  cmp -s "$cur/config/webdev-workspace.json" "$ROOT/config/webdev-workspace.json" || return 1
  cmp -s "$live_unit" "$UNIT_SOURCE" || return 1
  systemctl is-active --quiet cloudiff-webdev.service || return 1
  return 0
}

apply(){
  assert_forja
  install -d -m 0755 "$WORKSPACE" "$WORKSPACE/projects" "$WORKSPACE/evidence" "$RUNTIME_ROOT"
  docker compose -f "$COMPOSE" config -q
  if runtime_equivalent; then
    firewall_apply
    health
    echo WEBDEV_WORKSPACE=NOOP
    echo WEBDEV_LINK=https://cloudiff.duckdns.org/__cloudiff_webdev/
    echo WEBDEV_DIRECT_LINK=http://10.62.91.2:17900/
    return 0
  fi
  ln -sfn "$(cd "$ROOT" && pwd)" "$RUNTIME_ROOT/current.new"
  mv -Tf "$RUNTIME_ROOT/current.new" "$RUNTIME_ROOT/current"
  install -m 0644 "$UNIT_SOURCE" /etc/systemd/system/cloudiff-webdev.service
  systemctl daemon-reload
  systemctl enable cloudiff-webdev.service >/dev/null
  systemctl restart cloudiff-webdev.service
  systemctl is-active --quiet cloudiff-webdev.service
  health
  echo WEBDEV_WORKSPACE=PASS
  echo WEBDEV_LINK=https://cloudiff.duckdns.org/__cloudiff_webdev/
  echo WEBDEV_DIRECT_LINK=http://10.62.91.2:17900/
}

remove(){
  assert_forja
  systemctl disable --now cloudiff-webdev.service >/dev/null 2>&1 || true
  docker compose -f "$COMPOSE" down --remove-orphans >/dev/null 2>&1 || true
  firewall_remove
  echo WEBDEV_WORKSPACE_REMOVE=PASS
}

status(){
  systemctl is-active cloudiff-webdev.service 2>/dev/null || true
  docker ps --filter name=cloudiff-webdev-browser --format '{{.Names}}|{{.Status}}|{{.Ports}}'
  iptables -S "$CHAIN" 2>/dev/null || true
}

case "$ACTION" in
  apply) apply ;;
  remove) remove ;;
  status) status ;;
  health) health ;;
  firewall-apply) firewall_apply ;;
  firewall-remove) firewall_remove ;;
  *) exit 2 ;;
esac
