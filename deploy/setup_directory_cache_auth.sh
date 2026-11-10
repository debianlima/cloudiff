#!/bin/bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
TARGET=/etc/credstore.encrypted/cloudif-directory-cache-authentik.cred
install -d -o root -g root -m 0700 /etc/credstore.encrypted
umask 077
TMP=$(mktemp /etc/credstore.encrypted/.cloudif-directory-cache.XXXXXX)
trap 'rm -f "$TMP"' EXIT
systemd-creds encrypt --name=authentik_token - "$TMP" >/dev/null
[ -s "$TMP" ] || { echo 'encrypted credential was not created' >&2; exit 3; }
mv -f "$TMP" "$TARGET"
chmod 0600 "$TARGET"
trap - EXIT
echo DIRECTORY_CACHE_CREDENTIAL=PASS
