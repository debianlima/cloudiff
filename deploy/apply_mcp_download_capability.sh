#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-/srv/cloudif-v2}
STATE=/var/lib/cloudiff-v2/mcp-download-v26
WS_PTR=/srv/cloudif/app-pointers/workspace-broker-current
MCP_PTR=/srv/cloudif/app-pointers/mcp-gateway-current
WS_SERVICE=cloudif-workspace-broker.service
MCP_SERVICE=cloudif-mcp-gateway.service
WS_MAIN_BASE=196b4452e85babca99fbbab611a38c49dfaaea377c36360d9f7d4c24c02aaf33
WS_HELPER_BASE=99bb293fd46c2db05413aefcd7b3707d13213d08faa77dd9eb68dabc372bbc99
WS_MAIN_PATCHED=cdb7d1a919dc83507ab68cf0ed4e4a0dc5ffcde5c42cf17b1956115d344c15bd
WS_HELPER_PATCHED=f760fa3cb7ebd2453f14de8ff892c4c02283c5e4b866e56ccf1b5ca268910608
MCP_BASE=b218ec85083e0d3f1b6f0a02befa6210301363b5ac0e9c0630338825b67a7841
MCP_PATCHED=f332023a009c80e831eadfebb1ef11b36084f36ed0bd4ce5255cead9bef86df8
install -d -m 0700 "$STATE"
sha(){ sha256sum "$1"|awk '{print $1}'; }
wait_http(){ local url=$1;for _ in $(seq 1 60);do curl -fsS --max-time 2 "$url" >/dev/null 2>&1&&return 0;sleep .25;done;return 1; }
ws_smoke(){
  wait_http http://127.0.0.1:18206/health
  python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:18206/health',timeout=3) as x:v=json.load(x)
assert v.get('ok') is True and v.get('service')=='cloudif-workspace-broker'
print('WORKSPACE_SMOKE=PASS')
PY
}
mcp_ready(){
  local ready=0
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 http://127.0.0.1:18198/health >/dev/null 2>&1; then ready=1;break;fi
    sleep .25
  done
  [ "$ready" = 1 ]
}
mcp_smoke(){
  mcp_ready
  python3 - <<'PY'
import json,urllib.request
body=json.dumps({'jsonrpc':'2.0','id':'v26-smoke','method':'tools/list','params':{}},separators=(',',':')).encode()
r=urllib.request.Request('http://127.0.0.1:18198/mcp',data=body,method='POST',headers={'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=5) as x:v=json.load(x)
names={t.get('name') for t in (v.get('result') or {}).get('tools',[])}
assert 'workspace.artifact.download' in names
print('MCP_TOOL_SMOKE=PASS')
PY
}
rollback_all(){
  set +e
  if [ -s "$STATE/previous-ws-pointer" ];then ln -sfn "$(cat "$STATE/previous-ws-pointer")" "$WS_PTR";systemctl restart "$WS_SERVICE";ws_smoke||true;fi
  if [ -s "$STATE/previous-mcp-pointer" ];then ln -sfn "$(cat "$STATE/previous-mcp-pointer")" "$MCP_PTR";systemctl restart "$MCP_SERVICE";mcp_ready||true;fi
  set -e
}
apply_ws(){
  local old main helper release tmp
  old=$(readlink -f "$WS_PTR");main="$old/cloudif-workspace-broker.py";helper="$old/cloudif_workspace_artifact.py"
  if [ "$(sha "$main")" = "$WS_MAIN_PATCHED" ] && [ "$(sha "$helper")" = "$WS_HELPER_PATCHED" ];then ws_smoke;echo WORKSPACE_ALREADY_PATCHED;return;fi
  [ "$(sha "$main")" = "$WS_MAIN_BASE" ]&&[ "$(sha "$helper")" = "$WS_HELPER_BASE" ]||{ echo unexpected_workspace_source_sha >&2;exit 3; }
  release=/srv/cloudif/app-releases/workspace-broker/platform-v26-download-capability-20260821;tmp="$release.tmp";rm -rf "$tmp";cp -a "$old" "$tmp"
  (cd "$tmp"&&patch --batch --forward -p1 < "$ROOT/compat/workspace-broker-download-capability.patch")
  python3 "$ROOT/tests/test_workspace_download_capability.py" --main-base "$main" --helper-base "$helper" --patch "$ROOT/compat/workspace-broker-download-capability.patch" --source-dir "$tmp"
  [ "$(sha "$tmp/cloudif-workspace-broker.py")" = "$WS_MAIN_PATCHED" ]&&[ "$(sha "$tmp/cloudif_workspace_artifact.py")" = "$WS_HELPER_PATCHED" ]
  rm -rf "$release";mv "$tmp" "$release";printf '%s\n' "$old" > "$STATE/previous-ws-pointer";chmod 0600 "$STATE/previous-ws-pointer";ln -sfn "$release" "$WS_PTR"
  systemctl restart "$WS_SERVICE";ws_smoke;echo WORKSPACE_PATCH=PASS
}
apply_mcp(){
  local old src release tmp
  old=$(readlink -f "$MCP_PTR");src="$old/cloudif-mcp-gateway.py"
  if [ "$(sha "$src")" = "$MCP_PATCHED" ];then mcp_smoke;echo MCP_ALREADY_PATCHED;return;fi
  [ "$(sha "$src")" = "$MCP_BASE" ]||{ echo unexpected_mcp_source_sha >&2;exit 3; }
  release=/srv/cloudif/app-releases/mcp-gateway/platform-v26-download-resource-20260821;tmp="$release.tmp";rm -rf "$tmp";cp -a "$old" "$tmp"
  (cd "$tmp"&&patch --batch --forward -p1 < "$ROOT/compat/mcp-gateway-download-resource.patch")
  (set -a; . /etc/cloudif/mcp-gateway.env; set +a; python3 "$ROOT/tests/test_mcp_download_resource.py" --base "$src" --patch "$ROOT/compat/mcp-gateway-download-resource.patch" --source "$tmp/cloudif-mcp-gateway.py")
  [ "$(sha "$tmp/cloudif-mcp-gateway.py")" = "$MCP_PATCHED" ]
  rm -rf "$release";mv "$tmp" "$release";printf '%s\n' "$old" > "$STATE/previous-mcp-pointer";chmod 0600 "$STATE/previous-mcp-pointer";ln -sfn "$release" "$MCP_PTR"
  systemctl restart "$MCP_SERVICE";mcp_smoke;echo MCP_PATCH=PASS
}
case "$ACTION" in
 apply)
   on_error(){ rc=$?;trap - ERR;rollback_all;echo MCP_DOWNLOAD_ROLLBACK >&2;exit "$rc"; }
   trap on_error ERR
   apply_ws;apply_mcp
   trap - ERR
   echo MCP_DOWNLOAD_ROLLOUT=PASS;;
 rollback) rollback_all;echo MCP_DOWNLOAD_ROLLBACK=PASS;;
 status)
   printf 'WS_POINTER=';readlink -f "$WS_PTR";printf 'WS_MAIN_SHA=';sha "$WS_PTR/cloudif-workspace-broker.py";printf 'WS_HELPER_SHA=';sha "$WS_PTR/cloudif_workspace_artifact.py"
   printf 'MCP_POINTER=';readlink -f "$MCP_PTR";printf 'MCP_SHA=';sha "$MCP_PTR/cloudif-mcp-gateway.py"
   systemctl show "$WS_SERVICE" -p ActiveState -p NRestarts --no-pager;systemctl show "$MCP_SERVICE" -p ActiveState -p NRestarts --no-pager;;
 *) echo 'usage: apply_mcp_download_capability.sh apply|rollback|status' >&2;exit 2;;
esac
