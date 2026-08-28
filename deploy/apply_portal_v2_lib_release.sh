#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-status}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
MODULE=cloudif_portal_v2_coexist.py
SOURCE=${CLOUDIFF_PORTAL_V2_SOURCE_FILE:-$ROOT/components/control-plane/srv/cloudif/lib/$MODULE}
LIVE=${CLOUDIFF_PORTAL_V2_LIVE_FILE:-/srv/cloudif/lib/$MODULE}
LIB_DIR=$(dirname "$LIVE")
RELEASE_ROOT=${CLOUDIFF_PORTAL_V2_RELEASE_ROOT:-/srv/cloudif/lib-releases/portal-v2}
META_ROOT=${CLOUDIFF_RELEASE_META_ROOT:-/srv/cloudif/releases}
STATE=${CLOUDIFF_PORTAL_V2_STATE:-/var/lib/cloudiff-v2/portal-v2-lib}
PORTAL_PTR=${CLOUDIFF_PORTAL_PTR:-/srv/cloudif/app-pointers/portal-current}
PORTAL_ENV=${CLOUDIFF_PORTAL_ENV:-/etc/cloudif/portal.env}
SERVICE=${CLOUDIFF_PORTAL_SERVICE:-cloudif-admin-portal.service}
SHADOW_PORT=${CLOUDIFF_PORTAL_V2_SHADOW_PORT:-}
ALLOW_NONROOT=${CLOUDIFF_PORTAL_V2_ALLOW_NONROOT:-0}

CANDIDATE_HASH=
RELEASE_ID=
CANDIDATE_DIR=
CURRENT_TARGET=

fail(){ printf 'PORTAL_V2_LIB_RELEASE=FAIL reason=%s\n' "$1" >&2; exit "${2:-1}"; }
sha(){ sha256sum "$1" | awk '{print $1}'; }

require_root(){
  if [ "$ALLOW_NONROOT" != 1 ] && [ "$(id -u)" -ne 0 ]; then
    fail root_required 20
  fi
}

atomic_link(){
  local name=$1 target=$2
  local tmp="$RELEASE_ROOT/.${name}.new.$$"
  ln -s "$target" "$tmp"
  mv -Tf "$tmp" "$RELEASE_ROOT/$name"
}

ensure_dirs(){
  install -d -m 0755 "$RELEASE_ROOT" "$META_ROOT"
  install -d -m 0700 "$STATE"
}

ensure_baseline(){
  [ -f "$LIVE" ] || fail live_file_missing 21
  if [ -L "$RELEASE_ROOT/current" ]; then
    CURRENT_TARGET=$(readlink -f "$RELEASE_ROOT/current")
    [ -f "$CURRENT_TARGET/$MODULE" ] || fail current_payload_missing 22
    return 0
  fi
  local live_hash baseline tmp
  live_hash=$(sha "$LIVE")
  baseline="$RELEASE_ROOT/baseline-${live_hash:0:16}"
  if [ ! -d "$baseline" ]; then
    tmp="${baseline}.new.$$"
    rm -rf "$tmp"
    install -d -m 0755 "$tmp"
    install -m 0444 "$LIVE" "$tmp/$MODULE"
    chmod 0555 "$tmp"
    mv "$tmp" "$baseline"
  fi
  [ "$(sha "$baseline/$MODULE")" = "$live_hash" ] || fail baseline_hash_mismatch 23
  atomic_link current "$baseline"
  CURRENT_TARGET=$baseline
}

build_candidate(){
  [ -f "$SOURCE" ] || fail source_file_missing 24
  CANDIDATE_HASH=$(sha "$SOURCE")
  RELEASE_ID="portal-v2-lib-${CANDIDATE_HASH:0:16}"
  CANDIDATE_DIR="$RELEASE_ROOT/$RELEASE_ID"
  if [ -d "$CANDIDATE_DIR" ]; then
    [ -f "$CANDIDATE_DIR/$MODULE" ] || fail candidate_payload_missing 25
    [ "$(sha "$CANDIDATE_DIR/$MODULE")" = "$CANDIDATE_HASH" ] || fail candidate_hash_mismatch 26
    return 0
  fi
  local tmp="${CANDIDATE_DIR}.new.$$"
  rm -rf "$tmp"
  install -d -m 0755 "$tmp"
  install -m 0644 "$SOURCE" "$tmp/$MODULE"
  python3 -m py_compile "$tmp/$MODULE"
  rm -rf "$tmp/__pycache__"
  chmod 0444 "$tmp/$MODULE"
  chmod 0555 "$tmp"
  mv "$tmp" "$CANDIDATE_DIR"
}

write_rollback_metadata(){
  local meta="$META_ROOT/$RELEASE_ID" tmp current_hash service_state
  if [ -d "$meta" ]; then
    [ -s "$meta/pre-state/live.sha256" ] || fail release_metadata_incomplete 27
    [ -x "$meta/rollback.sh" ] || fail rollback_script_missing 28
    bash -n "$meta/rollback.sh"
    return 0
  fi
  tmp="${meta}.new.$$"
  rm -rf "$tmp"
  install -d -m 0755 "$tmp/pre-state"
  current_hash=$(sha "$LIVE")
  printf '%s\n' "$current_hash" > "$tmp/pre-state/live.sha256"
  printf '%s\n' "$CURRENT_TARGET" > "$tmp/pre-state/current-target"
  if command -v systemctl >/dev/null 2>&1; then
    service_state=$(systemctl is-active "$SERVICE" 2>/dev/null || true)
  else
    service_state=unavailable
  fi
  printf '%s\n' "${service_state:-unknown}" > "$tmp/pre-state/service-state"
  install -m 0555 "$0" "$tmp/apply_portal_v2_lib_release.sh"
  {
    printf '#!/usr/bin/env bash\nset -euo pipefail\n'
    printf 'export CLOUDIFF_PORTAL_V2_LIVE_FILE=%q\n' "$LIVE"
    printf 'export CLOUDIFF_PORTAL_V2_RELEASE_ROOT=%q\n' "$RELEASE_ROOT"
    printf 'export CLOUDIFF_RELEASE_META_ROOT=%q\n' "$META_ROOT"
    printf 'export CLOUDIFF_PORTAL_V2_STATE=%q\n' "$STATE"
    printf 'export CLOUDIFF_PORTAL_PTR=%q\n' "$PORTAL_PTR"
    printf 'export CLOUDIFF_PORTAL_ENV=%q\n' "$PORTAL_ENV"
    printf 'export CLOUDIFF_PORTAL_SERVICE=%q\n' "$SERVICE"
    printf 'exec %q rollback\n' "$meta/apply_portal_v2_lib_release.sh"
  } > "$tmp/rollback.sh"
  chmod 0555 "$tmp/rollback.sh"
  bash -n "$tmp/rollback.sh"
  chmod 0444 "$tmp/pre-state/"*
  chmod 0555 "$tmp/pre-state"
  chmod 0555 "$tmp/apply_portal_v2_lib_release.sh" "$tmp/rollback.sh" "$tmp/pre-state" "$tmp"
  mv "$tmp" "$meta"
  bash -n "$meta/rollback.sh"
}

prepare(){
  require_root
  ensure_dirs
  ensure_baseline
  build_candidate
  write_rollback_metadata
  printf 'PORTAL_V2_LIB_PREPARE=PASS release=%s current=%s\n' "$RELEASE_ID" "$(basename "$CURRENT_TARGET")"
}

smoke_url(){
  local base=$1 root_page alias_page nav_json
  root_page=$(mktemp "$STATE/root.XXXXXX")
  alias_page=$(mktemp "$STATE/alias.XXXXXX")
  nav_json=$(mktemp "$STATE/navigation.XXXXXX")
  trap 'rm -f "$root_page" "$alias_page" "$nav_json"' RETURN
  local headers=(
    -H 'Host: cloudiff.duckdns.org'
    -H 'X-Forwarded-Proto: https'
    -H 'X-authentik-username: ui-audit-admin'
    -H 'X-authentik-email: ui-audit-admin@example.invalid'
    -H 'X-authentik-groups: CloudIF-Tenants-Admin,CloudIF-Professor'
  )
  curl -fsS --max-time 8 "${headers[@]}" "$base/cloudiff/portal/" > "$root_page"
  curl -fsS --max-time 8 "${headers[@]}" "$base/cloudiff/portal/?tab=resumo" > "$alias_page"
  local marker
  for marker in 'Meus sites' 'Meus bancos' 'Saúde da plataforma'; do
    grep -Fq "$marker" "$root_page" || return 31
    grep -Fq "$marker" "$alias_page" || return 32
  done
  curl -fsS --max-time 8 "${headers[@]}" "$base/cloudiff/portal/api/navigation" > "$nav_json"
  python3 - "$nav_json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x.get('secrets_exposed') is False
assert x.get('unique_routes_required') is True
assert x.get('policy') == 'one_item_one_route_one_purpose'
PY
  rm -f "$root_page" "$alias_page" "$nav_json"
  trap - RETURN
}

port_busy(){
  local port=$1
  ss -H -ltn "sport = :$port" 2>/dev/null | grep -q .
}

resolve_shadow_port(){
  if [ -n "$SHADOW_PORT" ]; then
    port_busy "$SHADOW_PORT" && fail shadow_port_busy 36
    return 0
  fi
  local candidate
  for candidate in $(seq 19080 19088); do
    if ! port_busy "$candidate"; then
      SHADOW_PORT=$candidate
      return 0
    fi
  done
  fail no_shadow_port_available 36
}

stop_shadow(){
  local pid_file="$STATE/shadow.pid"
  [ -s "$pid_file" ] || return 0
  local pid; pid=$(cat "$pid_file")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep .1; done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

shadow_candidate(){
  require_root
  [ -n "$CANDIDATE_DIR" ] || fail candidate_not_prepared 33
  [ -d "$PORTAL_PTR" ] || fail portal_pointer_missing 34
  [ -f "$PORTAL_PTR/cloudif-admin-portal.py" ] || fail portal_launcher_missing 35
  resolve_shadow_port
  local log="$STATE/shadow-$RELEASE_ID.log" pid rc=0
  stop_shadow
  (
    set -a
    [ -r "$PORTAL_ENV" ] && . "$PORTAL_ENV"
    set +a
    export CLOUDIF_PORTAL_HOST=127.0.0.1
    export CLOUDIF_PORTAL_PORT="$SHADOW_PORT"
    export CLOUDIF_PORTAL_V2=1
    export PYTHONPATH="$CANDIDATE_DIR:$LIB_DIR"
    exec /usr/bin/python3 "$PORTAL_PTR/cloudif-admin-portal.py"
  ) >"$log" 2>&1 &
  pid=$!
  printf '%s\n' "$pid" > "$STATE/shadow.pid"
  trap stop_shadow EXIT INT TERM
  local ready=0
  for _ in $(seq 1 60); do
    kill -0 "$pid" 2>/dev/null || break
    if curl -sS --max-time 1 "http://127.0.0.1:$SHADOW_PORT/cloudiff/portal/" >/dev/null 2>&1; then ready=1; break; fi
    sleep .25
  done
  if [ "$ready" != 1 ]; then
    printf 'PORTAL_V2_LIB_SHADOW=FAIL log=%s\n' "$log" >&2
    rc=37
  else
    local owned
    owned=$(ss -H -ltnp "sport = :$SHADOW_PORT" 2>/dev/null || true)
    if ! grep -Fq "pid=$pid" <<<"$owned" || ! grep -Fq "127.0.0.1:$SHADOW_PORT" <<<"$owned"; then
      rc=38
    elif grep -Ev "127\.0\.0\.1:${SHADOW_PORT}[[:space:]]" <<<"$owned" | grep -q .; then
      rc=39
    elif ! smoke_url "http://127.0.0.1:$SHADOW_PORT"; then
      rc=$?
      [ "$rc" -ne 0 ] || rc=40
    fi
  fi
  stop_shadow
  trap - EXIT INT TERM
  [ "$rc" -eq 0 ] || return "$rc"
  printf 'PORTAL_V2_LIB_SHADOW=PASS release=%s port=%s\n' "$RELEASE_ID" "$SHADOW_PORT"
}

live_port(){
  local value
  value=$(
    set -a
    [ -r "$PORTAL_ENV" ] && . "$PORTAL_ENV"
    set +a
    printf '%s' "${CLOUDIF_PORTAL_PORT:-18094}"
  )
  printf '%s' "$value"
}

restart_service(){
  systemctl restart "$SERVICE"
  for _ in $(seq 1 60); do
    systemctl is-active --quiet "$SERVICE" && return 0
    sleep .2
  done
  return 1
}

copy_release_to_live(){
  local release=$1
  local payload="$release/$MODULE" tmp mode
  [ -f "$payload" ] || return 41
  mode=$(stat -c '%a' "$LIVE")
  tmp="${LIVE}.new.$$"
  install -m "$mode" "$payload" "$tmp"
  if [ "$(id -u)" -eq 0 ]; then chown --reference="$LIVE" "$tmp"; fi
  mv -Tf "$tmp" "$LIVE"
}

smoke_live(){
  local port; port=$(live_port)
  smoke_url "http://127.0.0.1:$port"
  printf 'PORTAL_V2_LIB_LIVE_SMOKE=PASS port=%s\n' "$port"
}

rollback(){
  require_root
  ensure_dirs
  [ -L "$RELEASE_ROOT/current" ] || fail current_pointer_missing 42
  [ -L "$RELEASE_ROOT/previous" ] || fail previous_pointer_missing 43
  local current previous
  current=$(readlink -f "$RELEASE_ROOT/current")
  previous=$(readlink -f "$RELEASE_ROOT/previous")
  [ "$current" != "$previous" ] || fail previous_equals_current 44
  copy_release_to_live "$previous"
  atomic_link current "$previous"
  atomic_link previous "$current"
  restart_service
  smoke_live
  printf 'PORTAL_V2_LIB_ROLLBACK=PASS current=%s previous=%s\n' "$(basename "$previous")" "$(basename "$current")"
}

apply_release(){
  prepare
  shadow_candidate
  local live_hash old_current
  live_hash=$(sha "$LIVE")
  if [ "$live_hash" = "$CANDIDATE_HASH" ]; then
    old_current=$(readlink -f "$RELEASE_ROOT/current")
    if [ "$old_current" != "$CANDIDATE_DIR" ]; then
      atomic_link previous "$old_current"
      atomic_link current "$CANDIDATE_DIR"
    fi
    smoke_live
    printf 'PORTAL_V2_LIB_APPLY=NOOP release=%s\n' "$RELEASE_ID"
    return 0
  fi
  old_current=$(readlink -f "$RELEASE_ROOT/current")
  atomic_link previous "$old_current"
  copy_release_to_live "$CANDIDATE_DIR"
  atomic_link current "$CANDIDATE_DIR"
  if ! restart_service || ! smoke_live; then
    printf 'PORTAL_V2_LIB_APPLY=FAILED_ROLLING_BACK release=%s\n' "$RELEASE_ID" >&2
    rollback || true
    return 45
  fi
  printf 'PORTAL_V2_LIB_APPLY=PASS release=%s previous=%s\n' "$RELEASE_ID" "$(basename "$old_current")"
}

status(){
  local live_hash=missing current=missing previous=missing
  [ -f "$LIVE" ] && live_hash=$(sha "$LIVE")
  [ -L "$RELEASE_ROOT/current" ] && current=$(basename "$(readlink -f "$RELEASE_ROOT/current")")
  [ -L "$RELEASE_ROOT/previous" ] && previous=$(basename "$(readlink -f "$RELEASE_ROOT/previous")")
  printf 'PORTAL_V2_LIB_STATUS live_sha256=%s current=%s previous=%s service=%s\n' "$live_hash" "$current" "$previous" "$(systemctl is-active "$SERVICE" 2>/dev/null || echo unavailable)"
}

plan(){
  [ -f "$SOURCE" ] || fail source_file_missing 24
  [ -f "$LIVE" ] || fail live_file_missing 21
  local source_hash live_hash
  source_hash=$(sha "$SOURCE"); live_hash=$(sha "$LIVE")
  printf 'PORTAL_V2_LIB_PLAN=PASS source_sha256=%s live_sha256=%s release=portal-v2-lib-%s action=%s\n' "$source_hash" "$live_hash" "${source_hash:0:16}" "$([ "$source_hash" = "$live_hash" ] && echo noop || echo promote)"
}

case "$ACTION" in
  plan|dry-run) plan ;;
  prepare) prepare ;;
  shadow) prepare; shadow_candidate ;;
  apply) apply_release ;;
  rollback) rollback ;;
  smoke) require_root; smoke_live ;;
  status) status ;;
  *) fail invalid_action 2 ;;
esac
