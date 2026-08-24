#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROOT=/srv/cloudif-v2
POINTER=/srv/cloudif/app-pointers/mcp-gateway-current
STATE=/var/lib/cloudiff-v2/mcp-gateway-v21
PATCH="$ROOT/compat/mcp-gateway-upload-fallback.patch"
TEST="$ROOT/tests/test_mcp_gateway_upload_fallback.py"
BASE_SHA=948e071ab08e45cd6a0683375669217aaaa76af5b8cc07bbd0092a7e1e71c846
PATCHED_SHA=b218ec85083e0d3f1b6f0a02befa6210301363b5ac0e9c0630338825b67a7841
SERVICE=cloudif-mcp-gateway.service
mkdir -p "$STATE"; chmod 0700 "$STATE"
current(){ readlink -f "$POINTER"; }
source_path(){ printf '%s/cloudif-mcp-gateway.py\n' "$1"; }
smoke(){
  systemctl is-active --quiet "$SERVICE"
  set -a; . /etc/cloudif/mcp-gateway.env; set +a
  ready=0
  for _ in $(seq 1 40); do
    if curl -fsS --max-time 2 "http://${CLOUDIF_MCP_HOST:-127.0.0.1}:${CLOUDIF_MCP_PORT:-18198}/health" >/dev/null 2>&1; then ready=1; break; fi
    sleep .25
  done
  [ "$ready" = 1 ]
  python3 - <<'PY'
import json,os,urllib.request
host=os.environ.get('CLOUDIF_MCP_HOST','127.0.0.1');port=os.environ.get('CLOUDIF_MCP_PORT','18198')
body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}).encode()
r=urllib.request.Request(f'http://{host}:{port}/mcp',data=body,method='POST',headers={'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=5) as x:data=json.load(x)
assert data.get('result',{}).get('tools')
PY
}
case "$ACTION" in
 status)
   cur=$(current); src=$(source_path "$cur"); printf 'CURRENT=%s\nSHA256=%s\n' "$cur" "$(sha256sum "$src"|awk '{print $1}')"; systemctl show "$SERVICE" -p ActiveState -p SubState -p NRestarts --no-pager
   ;;
 apply)
   old=$(current); oldsrc=$(source_path "$old"); oldsha=$(sha256sum "$oldsrc"|awk '{print $1}')
   if [ "$oldsha" = "$PATCHED_SHA" ]; then smoke; echo ALREADY_APPLIED; exit 0; fi
   [ "$oldsha" = "$BASE_SHA" ] || { echo "unexpected_source_sha:$oldsha" >&2; exit 3; }
   release=/srv/cloudif/app-releases/mcp-gateway/platform-v21-upload-fallback-20260820
   rm -rf "$release.tmp"; cp -a "$old" "$release.tmp"
   (cd "$release.tmp" && patch --batch --forward -p1 < "$PATCH")
   python3 -m py_compile "$release.tmp/cloudif-mcp-gateway.py"
   python3 "$TEST" --source "$release.tmp/cloudif-mcp-gateway.py" --base-source "$oldsrc"
   newsha=$(sha256sum "$release.tmp/cloudif-mcp-gateway.py"|awk '{print $1}'); [ "$newsha" = "$PATCHED_SHA" ]
   if [ -e "$release" ]; then rm -rf "$release"; fi; mv "$release.tmp" "$release"
   printf '%s\n' "$old" > "$STATE/previous-pointer"; chmod 0600 "$STATE/previous-pointer"
   ln -sfn "$release" "$POINTER"
   if ! systemctl restart "$SERVICE" || ! smoke; then
      ln -sfn "$old" "$POINTER"; systemctl restart "$SERVICE" || true; smoke || true; echo ROLLED_BACK >&2; exit 4
   fi
   echo APPLY=PASS
   ;;
 rollback)
   [ -s "$STATE/previous-pointer" ] || { echo previous_pointer_missing >&2; exit 5; }
   old=$(cat "$STATE/previous-pointer"); [ -f "$old/cloudif-mcp-gateway.py" ]
   ln -sfn "$old" "$POINTER"; systemctl restart "$SERVICE"; smoke; echo ROLLBACK=PASS
   ;;
 *) echo 'usage: apply_mcp_gateway_upload_fallback.sh apply|rollback|status' >&2; exit 2;;
esac
