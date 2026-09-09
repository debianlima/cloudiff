#!/usr/bin/env bash
set -euo pipefail
# Fail-closed rollback. Not a promotion script.
[ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
RELEASE_ID=${1:?release-id required}
BASE="/srv/cloudif/releases/$RELEASE_ID/pre-state"
PTR=/srv/cloudif/app-pointers/portal-current
SERVICE=cloudif-admin-portal.service
[ -f "$BASE/PRESTATE_COMPLETE" ] || { echo 'pre-state sentinel missing' >&2; exit 20; }
[ -s "$BASE/current.target" ] || { echo 'current target snapshot missing' >&2; exit 21; }
sha256sum -c "$BASE/PRESTATE.SHA256" >/dev/null || { echo 'pre-state integrity failed' >&2; exit 22; }
OLD=$(cat "$BASE/current.target")
[ -d "$OLD" ] || { echo 'recorded previous current release missing' >&2; exit 23; }
# Restore shared lib payload while Portal is stopped so app/lib cannot be observed half-restored.
systemctl stop "$SERVICE"
trap 'systemctl start "$SERVICE" >/dev/null 2>&1 || true' EXIT
rm -rf /srv/cloudif/lib/portal.rollback-new
install -d -m 0755 /srv/cloudif/lib/portal.rollback-new
tar -C /srv/cloudif/lib/portal.rollback-new --strip-components=1 -xzf "$BASE/portal-runtime.tgz" portal
mv /srv/cloudif/lib/portal "/srv/cloudif/lib/portal.failed.$(date -u +%Y%m%dT%H%M%SZ)"
mv /srv/cloudif/lib/portal.rollback-new /srv/cloudif/lib/portal
tar -C /srv/cloudif -xzf "$BASE/lib-root-files.tgz"
ln -sfn "$OLD" "$PTR.rollback-new"
mv -Tf "$PTR.rollback-new" "$PTR"
systemctl start "$SERVICE"
trap - EXIT
systemctl is-active --quiet "$SERVICE"
printf 'ROLLBACK=PASS\nCURRENT=%s\n' "$(readlink -f "$PTR")"
