#!/usr/bin/env bash
set -euo pipefail
set -a; . /etc/cloudif/machine-admin-db.env; set +a
OUT=/srv/cloudif/managed-backups/machine-admin-postgres
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DAY=$(date -u +%Y-%m-%d)
DIR=$OUT/daily/$DAY
install -d -m 0700 "$DIR" "$OUT/monthly"
FILE=$DIR/cloudif-machine-admin-$STAMP.dump
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" cloudif-machine-admin-db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=9 --no-owner --no-acl > "$FILE"
docker exec -i cloudif-machine-admin-db pg_restore --list < "$FILE" >/dev/null
sha256sum "$FILE" > "$FILE.sha256"
chmod 0600 "$FILE" "$FILE.sha256"
if [ "$(date -u +%d)" = 01 ]; then cp -a "$FILE" "$OUT/monthly/cloudif-machine-admin-$(date -u +%Y-%m).dump"; cp -a "$FILE.sha256" "$OUT/monthly/cloudif-machine-admin-$(date -u +%Y-%m).dump.sha256"; fi
find "$OUT/daily" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf -- {} +
find "$OUT/monthly" -maxdepth 1 -type f -name '*.dump' -mtime +400 -delete
find "$OUT/monthly" -maxdepth 1 -type f -name '*.sha256' -mtime +400 -delete
echo "$FILE"
