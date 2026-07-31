#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"

cd "$TDIR"

POSTGRES_PORT="$(grep -E '^POSTGRES_PORT=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
POSTGRES_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"

[ -n "$POSTGRES_PORT" ] || { echo "ERRO: POSTGRES_PORT vazio"; exit 1; }
[ -n "$POSTGRES_PASSWORD" ] || { echo "ERRO: POSTGRES_PASSWORD vazio"; exit 1; }

docker compose --env-file .env up -d db

for i in $(seq 1 90); do
  if docker compose --env-file .env exec -T db \
      bash -lc "pg_isready -h 127.0.0.1 -p '${POSTGRES_PORT}' -U postgres" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

PW_SQL="${POSTGRES_PASSWORD//\'/\'\'}"

cat > /tmp/cloudif-sync-roles.sql <<SQL
\\set ON_ERROR_STOP off
DO \$\$
DECLARE
  r text;
BEGIN
  FOREACH r IN ARRAY ARRAY[
    'supabase_admin',
    'authenticator',
    'supabase_auth_admin',
    'supabase_storage_admin',
    'supabase_functions_admin',
    'dashboard_user',
    'pgbouncer'
  ]
  LOOP
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', r, '${PW_SQL}');
        RAISE NOTICE 'senha sincronizada para role %', r;
      ELSE
        RAISE NOTICE 'role não existe: %', r;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'não consegui alterar role %: %', r, SQLERRM;
    END;
  END LOOP;
END
\$\$;
SQL

docker compose --env-file .env exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
  psql -h 127.0.0.1 -p "$POSTGRES_PORT" -U postgres -d postgres < /tmp/cloudif-sync-roles.sql

echo "OK: roles sincronizados para tenant=$TENANT"
