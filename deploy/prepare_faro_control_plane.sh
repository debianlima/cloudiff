#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CFG="$ROOT/config/faro-node-reservation.json"
STATE=/var/lib/cloudiff-v2/faro-node-reservation
USERS=/etc/cloudiff-v2/nats-users.conf
CONTROL=cloudiff-v2-control.service
BEGIN='# CloudIFF Faro 10.62.91.5 BEGIN'
END='# CloudIFF Faro 10.62.91.5 END'
install -d -m 0700 "$STATE"
node_id(){ python3 -c 'import json;print(json.load(open("'"$CFG"'"))["identity"]["nodeId"])'; }
reserve(){
  local nid;nid=$(node_id)
  install -m 0644 "$CFG" /etc/cloudiff-v2/faro-node-reservation.json
  chown root:root /etc/cloudiff-v2/faro-node-reservation.json
  printf '%s\n' "$nid" > "$STATE/node-id"
  chmod 0644 "$STATE/node-id";chown root:root "$STATE/node-id"
  if [ ! -s "$STATE/nats-password" ];then umask 077;openssl rand -hex 32 > "$STATE/nats-password";fi
  chmod 0600 "$STATE/nats-password";chown root:root "$STATE/nats-password"
  python3 - "$CFG" "$STATE/reservation.json" <<'PY'
import json,sys,time
x=json.load(open(sys.argv[1]))
o={'node_id':x['identity']['nodeId'],'hostname':'faro','address':'10.62.91.5','status':'reserved-not-onboarded','role':'unresolved','capabilities':'unresolved','reserved_at':int(time.time())}
json.dump(o,open(sys.argv[2],'w'),separators=(',',':'))
PY
  chmod 0600 "$STATE/reservation.json";chown root:root "$STATE/reservation.json"
  echo FARO_RESERVATION=PASS
}
nats_apply(){
  reserve
  [ -f "$USERS" ]
  [ -s "$STATE/nats-users.before" ] || cp -p "$USERS" "$STATE/nats-users.before"
  local nid pw;nid=$(node_id);pw=$(tr -d '\r\n' < "$STATE/nats-password")
  python3 - "$USERS" "$nid" "$pw" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import sys
path,nid,pw,begin,end=sys.argv[1:]
p=Path(path);s=p.read_text()
while begin in s:
    i=s.index(begin);j=s.find(end,i)
    if j<0: raise SystemExit('unterminated Faro NATS block')
    j+=len(end);s=s[:i]+s[j:].lstrip('\n')
anchor='  users = [\n'
if anchor not in s: raise SystemExit('users anchor missing')
block=(begin+'\n'
       '    {\n'
       f'      user: "{nid}"\n'
       f'      password: "{pw}"\n'
       '      permissions: { publish: { allow: ["cloudiff.v2.node.observed"] }, subscribe: { deny: [">"] } }\n'
       '    },\n'
       +end+'\n')
p.write_text(s.replace(anchor,anchor+block,1))
PY
  unset pw
  docker exec cloudiff-v2-nats nats-server -t -c /etc/nats/nats.conf >/dev/null
  docker kill --signal=HUP cloudiff-v2-nats >/dev/null
  sleep 1
  docker inspect cloudiff-v2-nats --format '{{.State.Running}}' | grep -qx true
  echo FARO_NATS_USER=PASS
}
control_fix(){
  [ -s "$STATE/etc-cloudiff-v2-mode.before" ] || stat -c '%a' /etc/cloudiff-v2 > "$STATE/etc-cloudiff-v2-mode.before"
  chmod 0751 /etc/cloudiff-v2
  systemctl reset-failed "$CONTROL" || true
  systemctl restart "$CONTROL"
  for _ in $(seq 1 40);do systemctl is-active --quiet "$CONTROL" && break;sleep .25;done
  systemctl is-active --quiet "$CONTROL"
  echo CONTROL_TLS_ACCESS=PASS
}
rollback(){
  if [ -s "$STATE/nats-users.before" ];then
    cp -p "$STATE/nats-users.before" "$USERS"
    docker exec cloudiff-v2-nats nats-server -t -c /etc/nats/nats.conf >/dev/null
    docker kill --signal=HUP cloudiff-v2-nats >/dev/null
  fi
  if [ -s "$STATE/etc-cloudiff-v2-mode.before" ];then chmod "$(cat "$STATE/etc-cloudiff-v2-mode.before")" /etc/cloudiff-v2;fi
  echo FARO_CONTROL_PLANE_ROLLBACK=PASS
}
case "$ACTION" in
  apply) reserve;nats_apply;control_fix;echo FARO_CONTROL_PLANE=READY_FOR_SSH;;
  reserve) reserve;;
  nats-apply) nats_apply;;
  control-fix) control_fix;;
  rollback) rollback;;
  status)
    printf 'NODE_RESERVED=';[ -s "$STATE/node-id" ]&&echo yes||echo no
    printf 'NATS_USER=';nid=$(node_id);grep -Fq "user: \"$nid\"" "$USERS"&&echo present||echo absent
    printf 'CONTROL=';systemctl is-active "$CONTROL" 2>/dev/null||true
    printf 'SSH=pending\n'
    ;;
  *) echo 'usage: prepare_faro_control_plane.sh apply|reserve|nats-apply|control-fix|rollback|status' >&2;exit 2;;
esac
