#!/usr/bin/env bash
set -euo pipefail
# Read-only inventory + pre-state capture. This script does not alter pointers or restart services.
[ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
RELEASE_ID=${1:?release-id required}
CLOUDIF_ROOT=${CLOUDIF_ROOT:-/srv/cloudif}
SYSTEMCTL_BIN=${SYSTEMCTL_BIN:-systemctl}
BASE="$CLOUDIF_ROOT/releases/$RELEASE_ID/pre-state"
PTR="$CLOUDIF_ROOT/app-pointers/portal-current"
PREV="$CLOUDIF_ROOT/app-pointers/portal-previous"
PORTAL="$CLOUDIF_ROOT/lib/portal"
SERVICE=cloudif-admin-portal.service
[ -L "$PTR" ] || { echo 'portal-current is not a symlink' >&2; exit 10; }
CURRENT=$(readlink -f "$PTR")
[ -d "$CURRENT" ] || { echo 'current target missing' >&2; exit 11; }
PREVIOUS=''
[ -L "$PREV" ] && PREVIOUS=$(readlink -f "$PREV") || true
[ ! -e "$BASE" ] || { echo "pre-state already exists: $BASE" >&2; exit 13; }
install -d -m 0700 "$BASE"
printf '%s\n' "$CURRENT" > "$BASE/current.target"
printf '%s\n' "$PREVIOUS" > "$BASE/previous.target"
"$SYSTEMCTL_BIN" show "$SERVICE" -p ActiveState -p SubState -p MainPID -p FragmentPath -p ExecStart -p EnvironmentFiles > "$BASE/service.txt"
find "$CURRENT" -maxdepth 1 -type f -print0 | sort -z | xargs -0 -r sha256sum > "$BASE/current.sha256"
if [ -L "$PORTAL" ]; then
  PORTAL_TYPE=symlink
  PORTAL_LINK=$(readlink "$PORTAL")
  PORTAL_REAL=$(readlink -f "$PORTAL")
elif [ -d "$PORTAL" ]; then
  PORTAL_TYPE=directory
  PORTAL_LINK=''
  PORTAL_REAL=$(readlink -f "$PORTAL")
else
  echo 'live lib/portal missing or unsupported object type' >&2
  exit 12
fi
[ -d "$PORTAL_REAL" ] || { echo 'resolved live lib/portal target missing' >&2; exit 14; }
if [ "$PORTAL_TYPE" = symlink ]; then
  case "$PORTAL_REAL" in
    "$CLOUDIF_ROOT/lib-releases/portal-v2/"*) : ;;
    *) echo 'live lib/portal symlink resolves outside managed portal-v2 releases' >&2; exit 15 ;;
  esac
fi
printf '%s\n' "$PORTAL_TYPE" > "$BASE/portal.type"
printf '%s\n' "$PORTAL_LINK" > "$BASE/portal.link"
printf '%s\n' "$PORTAL_REAL" > "$BASE/portal.real"
(
  cd "$PORTAL_REAL"
  find . -type f ! -name '*.pyc' ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 -r sha256sum
) > "$BASE/portal-runtime.sha256"
tar -C "$PORTAL_REAL" --exclude='*.pyc' --exclude='*/__pycache__' --exclude='*/__pycache__/**' -czf "$BASE/portal-runtime.tgz" .
find "$CLOUDIF_ROOT/lib" -maxdepth 1 -type f -print0 | sort -z | xargs -0 -r sha256sum > "$BASE/lib-root.sha256"
mapfile -d '' ROOT_LIB_FILES < <(find "$CLOUDIF_ROOT/lib" -maxdepth 1 -type f -printf 'lib/%f\0' | sort -z)
if ((${#ROOT_LIB_FILES[@]})); then
  tar -C "$CLOUDIF_ROOT" -czf "$BASE/lib-root-files.tgz" "${ROOT_LIB_FILES[@]}"
else
  tar -C "$CLOUDIF_ROOT" -czf "$BASE/lib-root-files.tgz" --files-from /dev/null
fi
find "$BASE" -maxdepth 1 -type f ! -name PRESTATE.SHA256 ! -name PRESTATE_COMPLETE -print0 | sort -z | xargs -0 -r sha256sum > "$BASE/PRESTATE.SHA256"
touch "$BASE/PRESTATE_COMPLETE"
printf 'PRESTATE=%s\nCURRENT=%s\nPREVIOUS=%s\nPORTAL_TYPE=%s\nPORTAL_REAL=%s\n' "$BASE" "$CURRENT" "$PREVIOUS" "$PORTAL_TYPE" "$PORTAL_REAL"
