#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/databases-v2
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
install -d -m 0700 "$DEST"
declare -A DBS=( [akadmin]=supabase-db [aluno]=cloudif_aluno-db-1 [iff1742962]=cloudif_iff1742962-db-1 )
for tenant in "${!DBS[@]}"; do
  c=${DBS[$tenant]}
  tdir="$DEST/$tenant"
  install -d -m 0700 "$tdir"
  docker exec "$c" sh -lc 'pg_dumpall -U "$POSTGRES_USER" --globals-only' | gzip -9 > "$tdir/globals.sql.gz"
  mapfile -t names < <(docker exec "$c" sh -lc 'psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where datistemplate=false order by datname"')
  printf '%s\n' "${names[@]}" > "$tdir/databases.txt"
  for db in "${names[@]}"; do
    safe=$(printf '%s' "$db" | sed 's/[^A-Za-z0-9_.-]/_/g')
    docker exec "$c" sh -lc 'pg_dump -U "$POSTGRES_USER" -Fc --no-owner --no-privileges -d "$1"' sh "$db" > "$tdir/$safe.dump"
    test -s "$tdir/$safe.dump"
  done
  gzip -t "$tdir/globals.sql.gz"
done
find "$DEST" -type f -exec chmod 0600 {} +
(cd "$DEST" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
tar -C "$BASE" -czf "$BASE/$STAMP.tar.gz" "$STAMP"
chmod 0600 "$BASE/$STAMP.tar.gz"
rm -rf "$DEST"
find "$BASE" -maxdepth 1 -type f -name '*.tar.gz' -mtime +3 -delete
printf '%s backup=%s size=%s\n' "$(date -Is)" "$BASE/$STAMP.tar.gz" "$(stat -c %s "$BASE/$STAMP.tar.gz")"
