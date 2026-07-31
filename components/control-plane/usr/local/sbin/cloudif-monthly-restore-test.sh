#!/usr/bin/env bash
set -euo pipefail
OUT=/var/log/cloudif-restore-test.log
exec >>"$OUT" 2>&1
echo "$(date -Is) restore-test start"
for tenant in akadmin aluno iff1742962; do
  case "$tenant" in
    akadmin) script=/tmp/cloudif-restore-akadmin-runtime.sh;;
    *) script=/tmp/cloudif-restore-generic-runtime.sh;;
  esac
  if [ "$tenant" = akadmin ]; then
    bash /usr/local/libexec/cloudif/clone_restore_akadmin.sh
    C=cloudif-restore-clone-akadmin
    LATEST=$(ls -1t /srv/cloudif/managed-backups/databases-v2/*.tar.gz | head -1)
    TMP=$(mktemp -d); tar -xzf "$LATEST" -C "$TMP"; D=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
    docker exec "$C" sh -lc 'psql -U "$POSTGRES_USER" -d template1 -v ON_ERROR_STOP=1 -c "alter database postgres with allow_connections false" -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='"'"'postgres'"'"'" -c "drop database postgres" -c "create database postgres owner supabase_admin"' >/dev/null
    docker exec "$C" sh -lc 'psql -U "$POSTGRES_USER" -d template1 -v ON_ERROR_STOP=1 -c "alter database _supabase with allow_connections false" -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='"'"'_supabase'"'"'" -c "drop database _supabase"' >/dev/null || true
    docker exec "$C" sh -lc 'createdb -U "$POSTGRES_USER" -O supabase_admin _supabase' >/dev/null
    for db in postgres _supabase; do docker cp "$D/akadmin/$db.dump" "$C:/tmp/$db.dump" >/dev/null; docker exec "$C" sh -lc 'pg_restore -U "$POSTGRES_USER" -d '"$db"' --no-owner --no-privileges --exit-on-error /tmp/'"$db"'.dump' >/dev/null; done
    docker exec "$C" sh -lc 'psql -U "$POSTGRES_USER" -d postgres -Atc "select count(*) from pg_class where relkind='"'"'r'"'"'"'
    docker exec "$C" sh -lc 'psql -U "$POSTGRES_USER" -d _supabase -Atc "select count(*) from pg_class where relkind='"'"'r'"'"'"'
    docker rm -f "$C" >/dev/null; docker volume rm cloudif_restorelab_db-config >/dev/null 2>&1 || true; rm -rf /srv/cloudif/restore-lab/akadmin "$TMP"
  else
    bash /usr/local/libexec/cloudif/clone_restore_tenant.sh "$tenant"
    docker rm -f "cloudif-restore-clone-$tenant" >/dev/null 2>&1 || true
    docker volume rm "cloudif_restorelab_${tenant}_db-config" >/dev/null 2>&1 || true
    rm -rf "/srv/cloudif/restore-lab/$tenant"
  fi
  echo "$(date -Is) restore-test tenant=$tenant ok"
done
find /srv/cloudif/restore-lab -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null || true
echo "$(date -Is) restore-test success"
