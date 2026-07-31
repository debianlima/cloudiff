#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/databases
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
install -d -m 0700 "$DEST"
declare -A DBS=( [akadmin]=supabase-db [aluno]=cloudif_aluno-db-1 [iff1742962]=cloudif_iff1742962-db-1 )
for tenant in "${!DBS[@]}"; do
  c=${DBS[$tenant]}
  docker inspect "$c" >/dev/null
  docker exec "$c" sh -lc 'pg_dumpall -U "$POSTGRES_USER"' | gzip -9 > "$DEST/$tenant.sql.gz"
  gzip -t "$DEST/$tenant.sql.gz"
  test -s "$DEST/$tenant.sql.gz"
done
find "$DEST" -type f -exec chmod 0600 {} +
(cd "$DEST" && sha256sum *.sql.gz > SHA256SUMS.txt)
tar -C "$BASE" -czf "$BASE/$STAMP.tar.gz" "$STAMP"
chmod 0600 "$BASE/$STAMP.tar.gz"
rm -rf "$DEST"
find "$BASE" -maxdepth 1 -type f -name '*.tar.gz' -mtime +3 -delete
printf '%s backup=%s size=%s\n' "$(date -Is)" "$BASE/$STAMP.tar.gz" "$(stat -c %s "$BASE/$STAMP.tar.gz")"
