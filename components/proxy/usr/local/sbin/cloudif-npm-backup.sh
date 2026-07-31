#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/proxy/npm
DEST=/srv/cloudif/proxy/managed-backups
STAMP=$(date +%Y%m%d-%H%M%S)
WORK="$DEST/$STAMP"
install -d -m 0700 "$WORK"
# Consistent SQLite copy.
sqlite3 "$BASE/data/database.sqlite" ".backup '$WORK/database.sqlite'"
CHECK=$(sqlite3 "$WORK/database.sqlite" 'pragma integrity_check;')
[ "$CHECK" = ok ]
cp -a "$BASE/docker-compose.yml" "$WORK/"
[ -f "$BASE/docker-compose.override.yml" ] && cp -a "$BASE/docker-compose.override.yml" "$WORK/"
cp -a "$BASE/custom" "$WORK/"
cp -a "$BASE/letsencrypt" "$WORK/"
find "$WORK" -type f -exec chmod 0600 {} +
(cd "$WORK" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
tar -C "$DEST" -czf "$DEST/npm-$STAMP.tar.gz" "$STAMP"
chmod 0600 "$DEST/npm-$STAMP.tar.gz"
rm -rf "$WORK"
find "$DEST" -maxdepth 1 -type f -name 'npm-*.tar.gz' -mtime +14 -delete
printf '%s backup=%s sqlite_integrity=%s size=%s\n' "$(date -Is)" "$DEST/npm-$STAMP.tar.gz" "$CHECK" "$(stat -c %s "$DEST/npm-$STAMP.tar.gz")"
