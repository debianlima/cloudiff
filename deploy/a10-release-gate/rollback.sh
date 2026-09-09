#!/usr/bin/env bash
set -euo pipefail
# Fail-closed rollback. Not a promotion script.
[ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
RELEASE_ID=${1:?release-id required}
CLOUDIF_ROOT=${CLOUDIF_ROOT:-/srv/cloudif}
SYSTEMCTL_BIN=${SYSTEMCTL_BIN:-systemctl}
BASE="$CLOUDIF_ROOT/releases/$RELEASE_ID/pre-state"
PTR="$CLOUDIF_ROOT/app-pointers/portal-current"
PREV="$CLOUDIF_ROOT/app-pointers/portal-previous"
PORTAL="$CLOUDIF_ROOT/lib/portal"
SERVICE=cloudif-admin-portal.service
[ -f "$BASE/PRESTATE_COMPLETE" ] || { echo 'pre-state sentinel missing' >&2; exit 20; }
[ -s "$BASE/current.target" ] || { echo 'current target snapshot missing' >&2; exit 21; }
(
  cd "$BASE"
  sha256sum -c PRESTATE.SHA256 >/dev/null
) || { echo 'pre-state integrity failed' >&2; exit 22; }
OLD=$(cat "$BASE/current.target")
OLD_PREVIOUS=$(cat "$BASE/previous.target")
PORTAL_TYPE=$(cat "$BASE/portal.type")
PORTAL_LINK=$(cat "$BASE/portal.link")
PORTAL_REAL=$(cat "$BASE/portal.real")
[ -d "$OLD" ] || { echo 'recorded current release missing' >&2; exit 23; }
case "$PORTAL_TYPE" in
  symlink)
    [ -n "$PORTAL_LINK" ] || { echo 'recorded portal symlink target missing' >&2; exit 24; }
    [ -d "$PORTAL_REAL" ] || { echo 'recorded portal release missing' >&2; exit 25; }
    (
      cd "$PORTAL_REAL"
      sha256sum -c "$BASE/portal-runtime.sha256" >/dev/null
    ) || { echo 'recorded portal release integrity failed' >&2; exit 26; }
    ;;
  directory)
    [ -f "$BASE/portal-runtime.tgz" ] || { echo 'portal runtime archive missing' >&2; exit 27; }
    ;;
  *) echo 'unsupported recorded portal object type' >&2; exit 28 ;;
esac
[ -z "$OLD_PREVIOUS" ] || [ -d "$OLD_PREVIOUS" ] || { echo 'recorded previous release missing' >&2; exit 29; }
# Prepare every replacement before stopping the service.
rm -rf "$CLOUDIF_ROOT/lib/portal.rollback-new"
if [ "$PORTAL_TYPE" = symlink ]; then
  ln -s "$PORTAL_LINK" "$CLOUDIF_ROOT/lib/portal.rollback-new"
  [ "$(readlink -f "$CLOUDIF_ROOT/lib/portal.rollback-new")" = "$PORTAL_REAL" ] || { echo 'prepared portal symlink resolves incorrectly' >&2; exit 30; }
else
  install -d -m 0755 "$CLOUDIF_ROOT/lib/portal.rollback-new"
  tar -C "$CLOUDIF_ROOT/lib/portal.rollback-new" -xzf "$BASE/portal-runtime.tgz"
  (
    cd "$CLOUDIF_ROOT/lib/portal.rollback-new"
    sha256sum -c "$BASE/portal-runtime.sha256" >/dev/null
  ) || { echo 'prepared portal directory integrity failed' >&2; exit 31; }
fi
ln -sfn "$OLD" "$PTR.rollback-new"
if [ -n "$OLD_PREVIOUS" ]; then
  ln -sfn "$OLD_PREVIOUS" "$PREV.rollback-new"
fi
"$SYSTEMCTL_BIN" stop "$SERVICE"
trap '"$SYSTEMCTL_BIN" start "$SERVICE" >/dev/null 2>&1 || true' EXIT
FAILED_PORTAL="$CLOUDIF_ROOT/lib/portal.failed.$(date -u +%Y%m%dT%H%M%SZ)"
mv "$PORTAL" "$FAILED_PORTAL"
mv -Tf "$CLOUDIF_ROOT/lib/portal.rollback-new" "$PORTAL"
tar -C "$CLOUDIF_ROOT" -xzf "$BASE/lib-root-files.tgz"
mv -Tf "$PTR.rollback-new" "$PTR"
if [ -n "$OLD_PREVIOUS" ]; then
  mv -Tf "$PREV.rollback-new" "$PREV"
else
  rm -f "$PREV" "$PREV.rollback-new"
fi
"$SYSTEMCTL_BIN" start "$SERVICE"
trap - EXIT
"$SYSTEMCTL_BIN" is-active --quiet "$SERVICE"
[ "$(readlink -f "$PTR")" = "$OLD" ] || { echo 'portal-current restore verification failed' >&2; exit 32; }
if [ "$PORTAL_TYPE" = symlink ]; then
  [ -L "$PORTAL" ] || { echo 'portal symlink restore verification failed' >&2; exit 33; }
  [ "$(readlink "$PORTAL")" = "$PORTAL_LINK" ] || { echo 'portal symlink target restore verification failed' >&2; exit 34; }
  [ "$(readlink -f "$PORTAL")" = "$PORTAL_REAL" ] || { echo 'portal resolved target restore verification failed' >&2; exit 35; }
fi
if [ -n "$OLD_PREVIOUS" ]; then
  [ "$(readlink -f "$PREV")" = "$OLD_PREVIOUS" ] || { echo 'portal-previous restore verification failed' >&2; exit 36; }
else
  [ ! -e "$PREV" ] && [ ! -L "$PREV" ] || { echo 'portal-previous absence restore verification failed' >&2; exit 37; }
fi
printf 'ROLLBACK=PASS\nCURRENT=%s\nPORTAL_TYPE=%s\nPORTAL_REAL=%s\nPREVIOUS=%s\nFAILED_PORTAL=%s\n' "$(readlink -f "$PTR")" "$PORTAL_TYPE" "$(readlink -f "$PORTAL")" "$OLD_PREVIOUS" "$FAILED_PORTAL"
