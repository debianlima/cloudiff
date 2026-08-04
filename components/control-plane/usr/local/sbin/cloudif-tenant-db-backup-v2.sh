#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/databases-v2
TENANTS=/srv/cloudif/tenants
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
install -d -m 0700 "$BASE"
install -d -m 0700 "$DEST"
backed_up=0
skipped=0
failed=0

cleanup() {
  if [ "$backed_up" -eq 0 ]; then rm -rf "$DEST"; fi
}
trap cleanup EXIT

for tdir in "$TENANTS"/*; do
  [ -d "$tdir" ] || continue
  tenant=$(basename "$tdir")
  compose=''
  for candidate in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
    if [ -f "$tdir/$candidate" ]; then compose="$tdir/$candidate"; break; fi
  done
  if [ -z "$compose" ]; then
    printf '%s tenant=%s status=skipped reason=compose_missing\n' "$(date -Is)" "$tenant" >&2
    skipped=$((skipped+1)); continue
  fi
  services=$(docker compose -f "$compose" --env-file "$tdir/.env" config --services 2>/dev/null || true)
  if ! grep -qx db <<<"$services"; then
    printf '%s tenant=%s status=skipped reason=db_service_missing\n' "$(date -Is)" "$tenant" >&2
    skipped=$((skipped+1)); continue
  fi
  was_running=0
  cid=$(docker compose -f "$compose" --env-file "$tdir/.env" ps -q db 2>/dev/null || true)
  if [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || true)" = true ]; then
    was_running=1
  else
    if ! docker compose -f "$compose" --env-file "$tdir/.env" up -d db >/dev/null; then
      printf '%s tenant=%s status=failed reason=db_start_failed\n' "$(date -Is)" "$tenant" >&2
      failed=$((failed+1)); continue
    fi
    cid=$(docker compose -f "$compose" --env-file "$tdir/.env" ps -q db)
  fi
  ready=0
  for _ in $(seq 1 60); do
    if docker exec "$cid" sh -lc 'pg_isready -U "$POSTGRES_USER" -d postgres' >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
  done
  if [ "$ready" -ne 1 ]; then
    printf '%s tenant=%s status=failed reason=db_not_ready\n' "$(date -Is)" "$tenant" >&2
    failed=$((failed+1))
    [ "$was_running" -eq 1 ] || docker compose -f "$compose" --env-file "$tdir/.env" stop db >/dev/null 2>&1 || true
    continue
  fi
  tdest="$DEST/$tenant"; install -d -m 0700 "$tdest"
  if ! docker exec "$cid" sh -lc 'pg_dumpall -U "$POSTGRES_USER" --globals-only' | gzip -9 > "$tdest/globals.sql.gz"; then
    printf '%s tenant=%s status=failed reason=globals_dump_failed\n' "$(date -Is)" "$tenant" >&2
    rm -rf "$tdest"; failed=$((failed+1))
    [ "$was_running" -eq 1 ] || docker compose -f "$compose" --env-file "$tdir/.env" stop db >/dev/null 2>&1 || true
    continue
  fi
  mapfile -t names < <(docker exec "$cid" sh -lc 'psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where datistemplate=false order by datname"')
  printf '%s\n' "${names[@]}" > "$tdest/databases.txt"
  tenant_ok=1
  for db in "${names[@]}"; do
    safe=$(printf '%s' "$db" | sed 's/[^A-Za-z0-9_.-]/_/g')
    if ! docker exec "$cid" sh -lc 'pg_dump -U "$POSTGRES_USER" -Fc --no-owner --no-privileges -d "$1"' sh "$db" > "$tdest/$safe.dump" || [ ! -s "$tdest/$safe.dump" ]; then
      tenant_ok=0; break
    fi
  done
  if [ "$tenant_ok" -eq 1 ] && gzip -t "$tdest/globals.sql.gz"; then
    backed_up=$((backed_up+1)); printf '%s tenant=%s status=ok container=%s\n' "$(date -Is)" "$tenant" "$cid"
  else
    printf '%s tenant=%s status=failed reason=database_dump_failed\n' "$(date -Is)" "$tenant" >&2
    rm -rf "$tdest"; failed=$((failed+1))
  fi
  [ "$was_running" -eq 1 ] || docker compose -f "$compose" --env-file "$tdir/.env" stop db >/dev/null 2>&1 || true
done

if [ "$backed_up" -eq 0 ]; then
  printf '%s status=failed reason=no_tenant_backed_up skipped=%s failed=%s\n' "$(date -Is)" "$skipped" "$failed" >&2
  exit 1
fi
find "$DEST" -type f -exec chmod 0600 {} +
(cd "$DEST" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
tar -C "$BASE" -czf "$BASE/$STAMP.tar.gz" "$STAMP"
chmod 0600 "$BASE/$STAMP.tar.gz"
rm -rf "$DEST"
trap - EXIT
find "$BASE" -maxdepth 1 -type f -name '*.tar.gz' -mtime +14 -delete
printf '%s backup=%s size=%s tenants=%s skipped=%s failed=%s\n' "$(date -Is)" "$BASE/$STAMP.tar.gz" "$(stat -c %s "$BASE/$STAMP.tar.gz")" "$backed_up" "$skipped" "$failed"
[ "$failed" -eq 0 ]
