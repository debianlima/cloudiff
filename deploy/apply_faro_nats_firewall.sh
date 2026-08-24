#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-apply}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CFG=${CLOUDIFF_FARO_RESERVATION_CONFIG:-/etc/cloudiff-v2/faro-node-reservation.json}
CHAIN=CLOUDIFF_V2_NATS_INPUT
DEST=10.62.92.7
PORT=14222
sources(){ python3 - "$CFG" <<'PY'
import json,sys
for s in json.load(open(sys.argv[1]))['nats']['sourceAllowlist']: print(s)
PY
}
remove_jump(){
  while iptables -C INPUT -d "$DEST/32" -p tcp --dport "$PORT" -j "$CHAIN" 2>/dev/null; do
    iptables -D INPUT -d "$DEST/32" -p tcp --dport "$PORT" -j "$CHAIN"
  done
}
apply_rules(){
  iptables -N "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN"
  iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  while read -r src; do [ -n "$src" ] && iptables -A "$CHAIN" -s "$src" -j RETURN; done < <(sources)
  iptables -A "$CHAIN" -j DROP
  remove_jump
  iptables -I INPUT 1 -d "$DEST/32" -p tcp --dport "$PORT" -j "$CHAIN"
  [ "$(iptables -S INPUT | grep -Fc -- "-d $DEST/32 -p tcp -m tcp --dport $PORT -j $CHAIN")" = 1 ]
  echo FARO_NATS_FIREWALL=PASS
}
rollback(){
  remove_jump
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
  echo FARO_NATS_FIREWALL_ROLLBACK=PASS
}
status(){
  iptables -S INPUT | grep -- "-d $DEST/32 -p tcp -m tcp --dport $PORT -j $CHAIN" || true
  iptables -S "$CHAIN" 2>/dev/null || true
}
case "$ACTION" in
  apply) apply_rules;;
  rollback) rollback;;
  status) status;;
  *) echo 'usage: apply_faro_nats_firewall.sh apply|rollback|status' >&2; exit 2;;
esac
