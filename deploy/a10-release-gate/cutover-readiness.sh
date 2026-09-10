#!/usr/bin/env bash
set -euo pipefail
# Read-only cutover readiness validator. This script MUST NOT change pointers,
# extract over live paths, stop/restart services, or promote a candidate.
RELEASE_ID=${1:?release-id required}
EXPECTED_ARCHIVE_SHA256=${2:?expected archive sha256 required}
EXPECTED_SOURCE_COMMIT=${3:?expected source commit required}
CLOUDIF_ROOT=${CLOUDIF_ROOT:-/srv/cloudif}
SYSTEMCTL_BIN=${SYSTEMCTL_BIN:-systemctl}
SERVICE=cloudif-admin-portal.service
BASE="$CLOUDIF_ROOT/releases/$RELEASE_ID"
PRE="$BASE/pre-state"
ARCHIVE="$BASE/candidate/$RELEASE_ID.tar.gz"
PTR="$CLOUDIF_ROOT/app-pointers/portal-current"
PREV="$CLOUDIF_ROOT/app-pointers/portal-previous"
PORTAL="$CLOUDIF_ROOT/lib/portal"

fail() { printf '%s\n' "$1" >&2; exit "${2:-1}"; }
case "$RELEASE_ID" in
  ''|*[!A-Za-z0-9._-]*) fail 'invalid release id' 2 ;;
esac
case "$EXPECTED_ARCHIVE_SHA256" in
  *[!0-9a-fA-F]*|'') fail 'invalid expected archive sha256' 3 ;;
esac
[ "${#EXPECTED_ARCHIVE_SHA256}" -eq 64 ] || fail 'invalid expected archive sha256 length' 3
case "$EXPECTED_SOURCE_COMMIT" in
  *[!0-9a-fA-F]*|'') fail 'invalid expected source commit' 4 ;;
esac
[ "${#EXPECTED_SOURCE_COMMIT}" -ge 7 ] || fail 'invalid expected source commit length' 4

[ -f "$ARCHIVE" ] || fail 'candidate archive missing' 10
ACTUAL_ARCHIVE_SHA256=$(sha256sum "$ARCHIVE" | awk '{print $1}')
[ "$ACTUAL_ARCHIVE_SHA256" = "${EXPECTED_ARCHIVE_SHA256,,}" ] || fail 'candidate archive hash mismatch' 11

python3 - "$ARCHIVE" "$RELEASE_ID" "$EXPECTED_SOURCE_COMMIT" <<'PY' || exit 12
import json, pathlib, sys, tarfile
archive, release_id, expected_source = sys.argv[1:]
try:
    with tarfile.open(archive, 'r:gz') as tf:
        members = [m for m in tf.getmembers() if pathlib.PurePosixPath(m.name).name == 'release-manifest.json' and m.isfile()]
        if len(members) != 1:
            raise SystemExit('candidate manifest missing or ambiguous')
        stream = tf.extractfile(members[0])
        if stream is None:
            raise SystemExit('candidate manifest unreadable')
        manifest = json.loads(stream.read().decode('utf-8'))
except (OSError, tarfile.TarError, UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise SystemExit(f'candidate manifest invalid: {type(exc).__name__}')
if manifest.get('release_id') != release_id:
    raise SystemExit('candidate manifest release id mismatch')
if manifest.get('source_commit') != expected_source:
    raise SystemExit('candidate manifest source commit mismatch')
if manifest.get('promotion_authorized') is not False:
    raise SystemExit('candidate manifest must remain promotion_authorized=false')
if manifest.get('requires_live_preflight') is not True:
    raise SystemExit('candidate manifest requires_live_preflight contract missing')
PY

[ -f "$PRE/PRESTATE_COMPLETE" ] || fail 'pre-state sentinel missing' 20
[ -s "$PRE/PRESTATE.SHA256" ] || fail 'pre-state checksum file missing' 21
(
  cd "$PRE"
  sha256sum -c PRESTATE.SHA256 >/dev/null
) || fail 'pre-state integrity failed' 22
for f in current.target previous.target portal.type portal.link portal.real current.sha256 portal-runtime.sha256 lib-root.sha256 service.txt; do
  [ -f "$PRE/$f" ] || fail "pre-state component missing: $f" 23
done

RECORDED_CURRENT=$(cat "$PRE/current.target")
RECORDED_PREVIOUS=$(cat "$PRE/previous.target")
RECORDED_PORTAL_TYPE=$(cat "$PRE/portal.type")
RECORDED_PORTAL_LINK=$(cat "$PRE/portal.link")
RECORDED_PORTAL_REAL=$(cat "$PRE/portal.real")

[ -L "$PTR" ] || fail 'portal-current is no longer a symlink' 30
[ "$(readlink -f "$PTR")" = "$RECORDED_CURRENT" ] || fail 'portal-current drifted since preflight' 31
[ -d "$RECORDED_CURRENT" ] || fail 'recorded current release missing' 32
if [ -n "$RECORDED_PREVIOUS" ]; then
  [ -L "$PREV" ] || fail 'portal-previous drifted since preflight' 33
  [ "$(readlink -f "$PREV")" = "$RECORDED_PREVIOUS" ] || fail 'portal-previous drifted since preflight' 33
else
  [ ! -e "$PREV" ] && [ ! -L "$PREV" ] || fail 'portal-previous appeared since preflight' 33
fi

case "$RECORDED_PORTAL_TYPE" in
  symlink)
    [ -L "$PORTAL" ] || fail 'lib/portal type drifted since preflight' 34
    [ "$(readlink "$PORTAL")" = "$RECORDED_PORTAL_LINK" ] || fail 'lib/portal link drifted since preflight' 35
    [ "$(readlink -f "$PORTAL")" = "$RECORDED_PORTAL_REAL" ] || fail 'lib/portal resolved target drifted since preflight' 36
    ;;
  directory)
    [ -d "$PORTAL" ] && [ ! -L "$PORTAL" ] || fail 'lib/portal type drifted since preflight' 34
    [ "$(readlink -f "$PORTAL")" = "$RECORDED_PORTAL_REAL" ] || fail 'lib/portal resolved target drifted since preflight' 36
    ;;
  *) fail 'unsupported recorded portal object type' 37 ;;
esac
[ -d "$RECORDED_PORTAL_REAL" ] || fail 'recorded portal runtime missing' 38

sha256sum -c "$PRE/current.sha256" >/dev/null || fail 'active app release drifted since preflight' 40
(
  cd "$RECORDED_PORTAL_REAL"
  sha256sum -c "$PRE/portal-runtime.sha256" >/dev/null
) || fail 'active portal runtime drifted since preflight' 41
sha256sum -c "$PRE/lib-root.sha256" >/dev/null || fail 'active root lib overlay drifted since preflight' 42

SERVICE_STATE=$("$SYSTEMCTL_BIN" show "$SERVICE" -p ActiveState -p SubState -p MainPID 2>/dev/null) || fail 'unable to read portal service state' 50
ACTIVE=$(printf '%s\n' "$SERVICE_STATE" | awk -F= '$1=="ActiveState"{print $2}')
SUB=$(printf '%s\n' "$SERVICE_STATE" | awk -F= '$1=="SubState"{print $2}')
PID=$(printf '%s\n' "$SERVICE_STATE" | awk -F= '$1=="MainPID"{print $2}')
[ "$ACTIVE" = active ] || fail 'portal service is not active' 51
[ "$SUB" = running ] || fail 'portal service is not running' 52
case "$PID" in ''|0|*[!0-9]*) fail 'portal service MainPID is not valid' 53 ;; esac

printf 'CUTOVER_READINESS=PASS\nRELEASE_ID=%s\nSOURCE_COMMIT=%s\nARCHIVE_SHA256=%s\nCURRENT=%s\nPREVIOUS=%s\nPORTAL_TYPE=%s\nPORTAL_REAL=%s\nSERVICE_PID=%s\n' \
  "$RELEASE_ID" "$EXPECTED_SOURCE_COMMIT" "$ACTUAL_ARCHIVE_SHA256" "$RECORDED_CURRENT" "$RECORDED_PREVIOUS" "$RECORDED_PORTAL_TYPE" "$RECORDED_PORTAL_REAL" "$PID"
