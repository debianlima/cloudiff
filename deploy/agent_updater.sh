#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-apply}
CFG=${CLOUDIFF_AGENT_UPDATE_CONFIG:-/etc/cloudiff-agent/update.json}
[ -r "$CFG" ]
read_cfg(){ python3 - "$CFG" "$1" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));v=x
for p in sys.argv[2].split('.'):v=v[p]
print(v)
PY
}
ROOT=$(read_cfg layout.root);RELEASES=$(read_cfg layout.releases);CURRENT=$(read_cfg layout.current);STATE=$(read_cfg layout.state);PUB=$(read_cfg layout.public_key);BASE=$(read_cfg repository.url);SERVICE=$(read_cfg activation.restart_service)
POLICY_URL_TEMPLATE=$(read_cfg policy.url_template);NODE_ID_FILE=$(read_cfg policy.node_id_file);POLICY_CACHE=$(read_cfg policy.cache_file);POLICY_DEFAULT=$(read_cfg policy.default_reboot_enabled);REBOOT_COOLDOWN=$(read_cfg policy.reboot_cooldown_seconds)
install -d -m 0755 "$ROOT" "$RELEASES";install -d -m 0700 "$STATE"
fetch(){ curl -fsS --max-time 15 --connect-timeout 4 "$1" -o "$2"; }
verify_manifest(){ openssl pkeyutl -verify -rawin -pubin -inkey "$PUB" -in "$1" -sigfile "$2" >/dev/null 2>&1; }
current_version(){ [ -x "$CURRENT/cloudiff-agent" ] && "$CURRENT/cloudiff-agent" --version | sed -n 's/.* \([0-9][0-9.]*\)-shadow$/\1/p' || true; }
policy_url(){ python3 - "$POLICY_URL_TEMPLATE" "$1" <<'PY'
import sys,uuid
u=str(uuid.UUID(sys.argv[2]));print(sys.argv[1].replace('{node_id}',u))
PY
}
refresh_policy(){
  [ -r "$NODE_ID_FILE" ] || return 1
  local node url tmp;node=$(tr -d '\r\n' < "$NODE_ID_FILE");url=$(policy_url "$node") || return 1;tmp=$(mktemp "$STATE/policy.XXXXXX")
  if ! fetch "$url" "$tmp";then rm -f "$tmp";return 1;fi
  python3 - "$tmp" "$node" <<'PY'
import json,sys,uuid
p,node=sys.argv[1:];node=str(uuid.UUID(node));x=json.load(open(p))
assert set(x)=={'node_id','automatic_reboot_enabled','revision'}
assert str(uuid.UUID(x['node_id']))==node
assert isinstance(x['automatic_reboot_enabled'],bool)
assert isinstance(x['revision'],int) and x['revision']>=0
PY
  install -D -m 0600 "$tmp" "$POLICY_CACHE.new";mv -Tf "$POLICY_CACHE.new" "$POLICY_CACHE";rm -f "$tmp";return 0
}
reboot_enabled(){
  if [ -r "$POLICY_CACHE" ] && [ -r "$NODE_ID_FILE" ];then
    python3 - "$POLICY_CACHE" "$NODE_ID_FILE" <<'PY'
import json,sys,uuid
try:
 x=json.load(open(sys.argv[1]));node=str(uuid.UUID(open(sys.argv[2]).read().strip()));assert str(uuid.UUID(x['node_id']))==node;print('1' if x['automatic_reboot_enabled'] else '0')
except Exception: print('1')
PY
    return
  fi
  if [ "$POLICY_DEFAULT" = True ] || [ "$POLICY_DEFAULT" = true ];then echo 1;else echo 0;fi
}
maybe_reboot(){
  [ "$(reboot_enabled)" = 1 ] || { echo AGENT_RECOVERY_REBOOT=DISABLED;return 1; }
  local stamp="$STATE/last-reboot-request" now last=0;now=$(date +%s);[ ! -r "$stamp" ] || last=$(cat "$stamp" 2>/dev/null || echo 0)
  if [ $((now-last)) -lt "$REBOOT_COOLDOWN" ];then echo AGENT_RECOVERY_REBOOT=COOLDOWN;return 1;fi
  printf '%s\n' "$now" > "$stamp";chmod 0600 "$stamp"
  if [ "${CLOUDIFF_AGENT_UPDATE_TEST_MODE:-0}" = 1 ];then echo AGENT_RECOVERY_REBOOT=WOULD_REBOOT;return 0;fi
  echo AGENT_RECOVERY_REBOOT=REQUESTED
  systemctl reboot
}
ensure_agent_service(){
  systemctl list-unit-files "$SERVICE" --no-legend 2>/dev/null | grep -q "$SERVICE" || return 0
  systemctl is-active --quiet "$SERVICE" && return 0
  systemctl restart "$SERVICE" || true;sleep 1
  systemctl is-active --quiet "$SERVICE" && { echo AGENT_RECOVERY=RESTARTED;return 0; }
  maybe_reboot || true
  return 1
}
apply_update(){
  refresh_policy || echo AGENT_POLICY=STALE_OR_DEFAULT
  [ -r "$PUB" ];tmp=$(mktemp -d "$STATE/tmp.XXXXXX");trap 'rm -rf "$tmp"' RETURN
  fetch "$BASE/stable/manifest.json" "$tmp/manifest.json";fetch "$BASE/stable/manifest.sig" "$tmp/manifest.sig"
  verify_manifest "$tmp/manifest.json" "$tmp/manifest.sig"
  eval "$(python3 - "$tmp/manifest.json" <<'PY'
import json,re,shlex,sys
x=json.load(open(sys.argv[1]));v=x['version'];a=x['artifact'];h=x['sha256'];z=x['size']
assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',v);assert a==f'releases/{v}/cloudiff-agent';assert re.fullmatch(r'[a-f0-9]{64}',h);assert isinstance(z,int) and z>0
print('VER='+shlex.quote(v));print('ART='+shlex.quote(a));print('SHA='+shlex.quote(h));print('SIZE='+str(z))
PY
)"
  cur=$(current_version);if [ "$cur" = "$VER" ];then ensure_agent_service || true;echo AGENT_UPDATE=NOOP;return 0;fi
  fetch "$BASE/$ART" "$tmp/cloudiff-agent"
  [ "$(stat -c %s "$tmp/cloudiff-agent")" = "$SIZE" ];[ "$(sha256sum "$tmp/cloudiff-agent"|awk '{print $1}')" = "$SHA" ]
  chmod 0755 "$tmp/cloudiff-agent";"$tmp/cloudiff-agent" --version | grep -q " $VER-shadow$"
  target="$RELEASES/$VER";install -d -m 0755 "$target";install -m 0755 "$tmp/cloudiff-agent" "$target/cloudiff-agent"
  prev=$(readlink -f "$CURRENT" 2>/dev/null || true);ln -sfn "$target" "$CURRENT.new";mv -Tf "$CURRENT.new" "$CURRENT"
  if systemctl list-unit-files "$SERVICE" --no-legend 2>/dev/null | grep -q "$SERVICE";then
    if ! systemctl restart "$SERVICE" || ! systemctl is-active --quiet "$SERVICE";then
      if [ -n "$prev" ];then ln -sfn "$prev" "$CURRENT.new";mv -Tf "$CURRENT.new" "$CURRENT";systemctl restart "$SERVICE" || true;fi
      if ! systemctl is-active --quiet "$SERVICE";then maybe_reboot || true;fi
      echo AGENT_UPDATE=ROLLBACK >&2;return 5
    fi
  fi
  cp -f "$tmp/manifest.json" "$STATE/last-manifest.json";chmod 0600 "$STATE/last-manifest.json"
  echo "AGENT_UPDATE=APPLIED VERSION=$VER"
}
rollback(){ prev=$(find "$RELEASES" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n'|sort -nr|sed -n '2{s/^[^ ]* //;p}');[ -n "$prev" ];ln -sfn "$prev" "$CURRENT.new";mv -Tf "$CURRENT.new" "$CURRENT";systemctl restart "$SERVICE" || true;echo AGENT_UPDATE_ROLLBACK=PASS; }
case "$ACTION" in apply|check)apply_update;;rollback)rollback;;status)echo "CURRENT_VERSION=$(current_version)";;*)exit 2;;esac
