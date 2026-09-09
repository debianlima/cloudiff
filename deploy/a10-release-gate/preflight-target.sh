#!/usr/bin/env bash
set -euo pipefail
# Read-only inventory + pre-state capture. This script does not alter current/previous or restart services.
[ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
RELEASE_ID=${1:?release-id required}
BASE="/srv/cloudif/releases/$RELEASE_ID/pre-state"
PTR=/srv/cloudif/app-pointers/portal-current
PREV=/srv/cloudif/app-pointers/portal-previous
SERVICE=cloudif-admin-portal.service
[ -L "$PTR" ] || { echo 'portal-current is not a symlink' >&2; exit 10; }
CURRENT=$(readlink -f "$PTR")
[ -d "$CURRENT" ] || { echo 'current target missing' >&2; exit 11; }
PREVIOUS=''
[ -L "$PREV" ] && PREVIOUS=$(readlink -f "$PREV") || true
install -d -m 0700 "$BASE"
printf '%s\n' "$CURRENT" > "$BASE/current.target"
printf '%s\n' "$PREVIOUS" > "$BASE/previous.target"
systemctl show "$SERVICE" -p ActiveState -p SubState -p MainPID -p FragmentPath -p ExecStart -p EnvironmentFiles > "$BASE/service.txt"
find "$CURRENT" -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum > "$BASE/current.sha256"
[ -d /srv/cloudif/lib/portal ] || { echo 'live /srv/cloudif/lib/portal missing' >&2; exit 12; }
tar -C /srv/cloudif/lib -czf "$BASE/portal-runtime.tgz" portal
find /srv/cloudif/lib -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum > "$BASE/lib-root.sha256"
tar -C /srv/cloudif -czf "$BASE/lib-root-files.tgz" --exclude='lib/portal' $(find /srv/cloudif/lib -maxdepth 1 -type f -printf 'lib/%f\n' | sort)
sha256sum "$BASE"/*.tgz "$BASE"/*.sha256 "$BASE"/*.target "$BASE"/service.txt > "$BASE/PRESTATE.SHA256"
touch "$BASE/PRESTATE_COMPLETE"
printf 'PRESTATE=%s\nCURRENT=%s\nPREVIOUS=%s\n' "$BASE" "$CURRENT" "$PREVIOUS"
