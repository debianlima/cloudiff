#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"

[ -d "$TDIR" ] || { echo "ERRO: tenant não existe: $TDIR"; exit 1; }
[ -f "$ENV" ] || { echo "ERRO: .env não encontrado: $ENV"; exit 1; }

cd "$TDIR"

get_env() {
  awk -F= -v k="$1" '$1==k {print substr($0, length(k)+2); exit}' "$ENV" | sed 's/^"//;s/"$//;s/^'\''//;s/'\''$//'
}

PGPORT="$(get_env POSTGRES_PORT || true)"
POSTGRES_PASSWORD="$(get_env POSTGRES_PASSWORD || true)"
COMPOSE_PROJECT_NAME="$(get_env COMPOSE_PROJECT_NAME || true)"

[ -n "$PGPORT" ] || PGPORT="5432"
[ -n "$POSTGRES_PASSWORD" ] || { echo "ERRO: POSTGRES_PASSWORD vazio"; exit 1; }

echo "============================================================"
echo " CloudIF sync-db-passwords v2"
echo " Tenant: $TENANT"
echo " TDIR: $TDIR"
echo " PGPORT: $PGPORT"
echo "============================================================"

docker compose --env-file .env up -d db

echo "Aguardando banco..."
for i in $(seq 1 90); do
  if docker compose --env-file .env exec -T db bash -lc "pg_isready -h 127.0.0.1 -p '$PGPORT' -U supabase_admin >/dev/null 2>&1 || pg_isready -h 127.0.0.1 -p '$PGPORT' -U postgres >/dev/null 2>&1"; then
    break
  fi
  sleep 2
done

run_psql() {
  local user="$1"
  local sql="$2"
  docker compose --env-file .env exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
    psql -h 127.0.0.1 -p "$PGPORT" -U "$user" -d postgres -v ON_ERROR_STOP=1 -c "$sql"
}

ADMIN_USER=""
if run_psql supabase_admin "select current_user;" >/dev/null 2>&1; then
  if [ "$(run_psql supabase_admin "select rolsuper from pg_roles where rolname=current_user;" -At 2>/dev/null || true)" != "" ]; then
    ADMIN_USER="supabase_admin"
  fi
fi

if [ -z "$ADMIN_USER" ]; then
  if run_psql postgres "select current_user;" >/dev/null 2>&1; then
    ADMIN_USER="postgres"
  fi
fi

[ -n "$ADMIN_USER" ] || { echo "ERRO: não consegui autenticar como supabase_admin nem postgres"; exit 1; }

echo "Usuário administrativo usado: $ADMIN_USER"

ROLES=(
  supabase_admin
  authenticator
  supabase_auth_admin
  supabase_storage_admin
  supabase_functions_admin
  dashboard_user
  pgbouncer
)

FAIL=0
for role in "${ROLES[@]}"; do
  echo "Sincronizando role: $role"
  if run_psql "$ADMIN_USER" "DO \$\$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$role') THEN EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '$role', '$POSTGRES_PASSWORD'); END IF; END \$\$;"; then
    echo "OK: $role"
  else
    echo "ERRO/WARN: falha ao ajustar $role"
    FAIL=1
  fi
done

echo
echo "Testes locais das roles críticas:"
CRITICAL=(supabase_admin authenticator supabase_auth_admin supabase_storage_admin)
for role in "${CRITICAL[@]}"; do
  echo -n "$role: "
  if docker compose --env-file .env exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
      psql -h 127.0.0.1 -p "$PGPORT" -U "$role" -d postgres -Atc "select current_user;" >/tmp/cloudif-role-test-$TENANT.txt 2>&1; then
    cat /tmp/cloudif-role-test-$TENANT.txt
  else
    echo "FALHOU"
    cat /tmp/cloudif-role-test-$TENANT.txt || true
    FAIL=1
  fi
done

NET="$(docker inspect "$(docker compose --env-file .env ps -q db)" --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' | head -n1 || true)"
if [ -n "$NET" ]; then
  echo
  echo "Teste supabase_admin via rede Docker: $NET"
  if docker run --rm --network "$NET" -e PGPASSWORD="$POSTGRES_PASSWORD" --entrypoint psql supabase/postgres:15.8.1.085 \
      -h db -p "$PGPORT" -U supabase_admin -d postgres -Atc "select current_user;" >/tmp/cloudif-net-test-$TENANT.txt 2>&1; then
    cat /tmp/cloudif-net-test-$TENANT.txt
  else
    echo "ERRO: teste via rede Docker falhou"
    cat /tmp/cloudif-net-test-$TENANT.txt || true
    FAIL=1
  fi
else
  echo "WARN: rede Docker do tenant não detectada"
fi

if [ "$FAIL" != "0" ]; then
  echo "ERRO: sincronização terminou com falhas."
  exit 2
fi

echo "OK: roles sincronizadas e validadas para tenant=$TENANT"
