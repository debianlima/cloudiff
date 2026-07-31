#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/config
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
install -d -m 0700 "$DEST"
python3 - <<PY
import sqlite3
src='/var/lib/cloudif/portal/cloudif-portal.db'
dst='$DEST/cloudif-portal.db'
a=sqlite3.connect(src); b=sqlite3.connect(dst); a.backup(b); b.close(); a.close()
PY
cp -a /etc/systemd/system/cloudif-*.service /etc/systemd/system/cloudif-*.timer "$DEST"/ 2>/dev/null || true
cp -a /etc/systemd/system/cloudif-*.service.d "$DEST"/ 2>/dev/null || true
cp -a /etc/cloudif "$DEST/etc-cloudif" 2>/dev/null || true
cp -a /usr/local/sbin/cloudif-* "$DEST"/ 2>/dev/null || true
install -d -m 0700 "$DEST/tenants"
for d in /srv/cloudif/tenants/*; do
  [ -d "$d" ] || continue
  n=$(basename "$d"); install -d -m 0700 "$DEST/tenants/$n"
  cp -a "$d/.env" "$d/docker-compose.yml" "$d/compose.yml" "$DEST/tenants/$n/" 2>/dev/null || true
done
find "$DEST" -type f -exec chmod 0600 {} +
find "$DEST" -type f -exec sha256sum {} + > "$DEST/SHA256SUMS.txt"
tar -C "$BASE" -czf "$BASE/$STAMP.tar.gz" "$STAMP"
chmod 0600 "$BASE/$STAMP.tar.gz"
rm -rf "$DEST"
find "$BASE" -maxdepth 1 -type f -name '*.tar.gz' -mtime +7 -delete
printf '%s backup=%s size=%s\n' "$(date -Is)" "$BASE/$STAMP.tar.gz" "$(stat -c %s "$BASE/$STAMP.tar.gz")"
