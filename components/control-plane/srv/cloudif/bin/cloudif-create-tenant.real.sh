#!/usr/bin/env bash
set -Eeuo pipefail

TENANT_RAW="${1:?Informe o tenant}"
BASE="/srv/cloudif"
SRC="${CLOUDIF_SUPABASE_TEMPLATE_DIR:-/opt/cloudif-src/supabase/docker}"
REGISTRY="$BASE/registry/tenants.csv"

PUBLIC_HOST="cloudiff.duckdns.org"

TENANT="$(echo "$TENANT_RAW" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^[._-]+//; s/[._-]+$//')"
[ -n "$TENANT" ] || { echo "Tenant inválido"; exit 1; }

TDIR="$BASE/tenants/$TENANT"
LOCK_ROOT="/run/cloudif-operation-locks"
mkdir -p "$LOCK_ROOT"
LOCK="$LOCK_ROOT/tenant-${TENANT}.lock"

exec 9>"$LOCK"
flock -x 9

if grep -q "^${TENANT}," "$REGISTRY" 2>/dev/null; then
  echo "Tenant já registrado: $TENANT"
else
  max_kong="$(awk -F, 'NR>1 && $2 ~ /^[0-9]+$/ {if($2>m)m=$2} END{print m+0}' "$REGISTRY")"
  max_studio="$(awk -F, 'NR>1 && $3 ~ /^[0-9]+$/ {if($3>m)m=$3} END{print m+0}' "$REGISTRY")"
  max_db="$(awk -F, 'NR>1 && $4 ~ /^[0-9]+$/ {if($4>m)m=$4} END{print m+0}' "$REGISTRY")"

  if [ "$TENANT" = "akadmin" ]; then
    KONG=8102; STUDIO=30010; DB=54330; KONG_SSL=8444; POOL_TX=65430; POOL_SESS=54320; INBUCKET=54325
  elif [ "$TENANT" = "iff1742962" ]; then
    KONG=8101; STUDIO=30011; DB=54331; KONG_SSL=8445; POOL_TX=65431; POOL_SESS=54321; INBUCKET=54326
  else
    KONG=$(( max_kong > 8110 ? max_kong + 1 : 8110 ))
    STUDIO=$(( max_studio > 30100 ? max_studio + 1 : 30100 ))
    DB=$(( max_db > 54400 ? max_db + 1 : 54400 ))
    KONG_SSL=$(( KONG + 1000 ))
    POOL_TX=$(( 65400 + KONG - 8100 ))
    POOL_SESS=$(( 54300 + KONG - 8100 ))
    INBUCKET=$(( 54320 + KONG - 8100 ))
  fi

  echo "${TENANT},${KONG},${STUDIO},${DB},${KONG_SSL},${POOL_TX},${POOL_SESS},${INBUCKET},$(date -Is)" >> "$REGISTRY"
fi

IFS=, read -r TENANT KONG STUDIO DB KONG_SSL POOL_TX POOL_SESS INBUCKET CREATED < <(grep "^${TENANT}," "$REGISTRY" | tail -1)

if [ ! -f "$SRC/docker-compose.yml" ]; then
  echo "Template Supabase não encontrado: $SRC" >&2
  exit 2
fi

if [ ! -f "$TDIR/docker-compose.yml" ]; then
  echo "Criando ou reparando tenant $TENANT em $TDIR"
  mkdir -p "$TDIR"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.git' \
      --exclude 'volumes/db/data' \
      --exclude 'volumes/storage/s3' \
      --exclude 'volumes/logs/*.log' \
      "$SRC/" "$TDIR/"
  else
    (
      cd "$SRC"
      tar \
        --exclude='./.git' \
        --exclude='./volumes/db/data' \
        --exclude='./volumes/storage/s3' \
        --exclude='./volumes/logs/*.log' \
        -cf - .
    ) | (cd "$TDIR" && tar -xf -)
  fi
fi

cd "$TDIR"

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
  else
    touch .env
  fi
fi

PROJECT_SAFE="$(echo "cloudif_${TENANT}" | sed -E 's/[^a-z0-9_-]+/_/g')"
POSTGRES_PASSWORD="$(openssl rand -hex 18)"
JWT_SECRET="$(openssl rand -hex 32)"
ANON_KEY="$("$BASE/bin/cloudif-jwt.py" "$JWT_SECRET" anon)"
SERVICE_ROLE_KEY="$("$BASE/bin/cloudif-jwt.py" "$JWT_SECRET" service_role)"
DASH_PASS="$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-22)"
SECRET_KEY_BASE="$(openssl rand -hex 32)"
VAULT_KEY="$(openssl rand -hex 16)"
PG_META_CRYPTO_KEY="$(openssl rand -hex 32)"
LOGFLARE_KEY="$(openssl rand -hex 16)"
S3_ACCESS_KEY_ID="$(openssl rand -hex 12)"
S3_ACCESS_KEY_SECRET="$(openssl rand -hex 24)"

"$BASE/bin/cloudif-env-set.py" ".env" \
  "COMPOSE_PROJECT_NAME=${PROJECT_SAFE}" \
  "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  "JWT_SECRET=${JWT_SECRET}" \
  "ANON_KEY=${ANON_KEY}" \
  "SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}" \
  "SUPABASE_ANON_KEY=${ANON_KEY}" \
  "SUPABASE_SERVICE_KEY=${SERVICE_ROLE_KEY}" \
  "SUPABASE_PUBLISHABLE_KEY=sb_publishable_$(openssl rand -hex 24)" \
  "SUPABASE_SECRET_KEY=sb_secret_$(openssl rand -hex 32)" \
  "DASHBOARD_USERNAME=cloudif" \
  "DASHBOARD_PASSWORD=${DASH_PASS}" \
  "SECRET_KEY_BASE=${SECRET_KEY_BASE}" \
  "VAULT_ENC_KEY=${VAULT_KEY}" \
  "PG_META_CRYPTO_KEY=${PG_META_CRYPTO_KEY}" \
  "LOGFLARE_API_KEY=${LOGFLARE_KEY}" \
  "LOGFLARE_BACKEND_API_KEY=${LOGFLARE_KEY}" \
  "STUDIO_DEFAULT_ORGANIZATION=CloudIF" \
  "STUDIO_DEFAULT_PROJECT=${TENANT}" \
  "POSTGRES_HOST=db" \
  "POSTGRES_DB=postgres" \
  "JWT_EXPIRY=3600" \
  "PGRST_DB_SCHEMAS=public,storage,graphql_public" \
  "FUNCTIONS_VERIFY_JWT=false" \
  "POOLER_TENANT_ID=${TENANT}" \
  "POOLER_DEFAULT_POOL_SIZE=20" \
  "POOLER_DB_POOL_SIZE=5" \
  "POOLER_MAX_CLIENT_CONN=100" \
  "POSTGRES_HOST=db" \
  "POSTGRES_DB=postgres" \
  "JWT_EXPIRY=3600" \
  "PGRST_DB_SCHEMAS=public,storage,graphql_public" \
  "FUNCTIONS_VERIFY_JWT=false" \
  "POOLER_TENANT_ID=${TENANT}" \
  "POOLER_DEFAULT_POOL_SIZE=20" \
  "POOLER_DB_POOL_SIZE=5" \
  "POOLER_MAX_CLIENT_CONN=100" \
  "STUDIO_PORT=${STUDIO}" \
  "KONG_HTTP_PORT=${KONG}" \
  "KONG_HTTPS_PORT=${KONG_SSL}" \
  "POSTGRES_PORT=${DB}" \
  "POOLER_PROXY_PORT_TRANSACTION=${POOL_TX}" \
  "POOLER_PROXY_PORT_SESSION=${POOL_SESS}" \
  "INBUCKET_PORT=${INBUCKET}" \
  "API_EXTERNAL_URL=https://${TENANT}.cloudiff.duckdns.org" \
  "SUPABASE_PUBLIC_URL=https://${TENANT}.cloudiff.duckdns.org" \
  "SITE_URL=https://${TENANT}.cloudiff.duckdns.org" \
  "ADDITIONAL_REDIRECT_URLS=https://${TENANT}.cloudiff.duckdns.org" \
  "DISABLE_SIGNUP=false" \
  "ENABLE_EMAIL_SIGNUP=true" \
  "ENABLE_EMAIL_AUTOCONFIRM=true" \
  "ENABLE_PHONE_SIGNUP=false" \
  "ENABLE_PHONE_AUTOCONFIRM=false" \
  "ENABLE_ANONYMOUS_USERS=false" \
  "SMTP_HOST=" \
  "SMTP_PORT=587" \
  "SMTP_USER=" \
  "SMTP_PASS=" \
  "SMTP_ADMIN_EMAIL=admin@cloudiff.local" \
  "SMTP_SENDER_NAME=CloudIF" \
  "MAILER_URLPATHS_CONFIRMATION=/auth/v1/verify" \
  "MAILER_URLPATHS_INVITE=/auth/v1/verify" \
  "MAILER_URLPATHS_RECOVERY=/auth/v1/verify" \
  "MAILER_URLPATHS_EMAIL_CHANGE=/auth/v1/verify" \
  "GLOBAL_S3_BUCKET=cloudif-${TENANT}" \
  "REGION=us-east-1" \
  "S3_PROTOCOL_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}" \
  "S3_PROTOCOL_ACCESS_KEY_SECRET=${S3_ACCESS_KEY_SECRET}" \
  "IMGPROXY_AUTO_WEBP=true" \
  "OPENAI_API_KEY="

echo "Preparando docker-compose e kong.yml do tenant $TENANT"
"$BASE/bin/cloudif-sanitize-compose.sh" "$TENANT"
"$BASE/bin/cloudif-fix-compose-db-internal-port.sh" "$TENANT"
"$BASE/bin/cloudif-write-kong-v134.sh" "$TENANT"

echo "Subindo tenant $TENANT"
docker compose --env-file .env up -d db imgproxy kong studio

"$BASE/bin/cloudif-sync-db-passwords.sh" "$TENANT" || true

EXPECTED_SERVICES=(db imgproxy kong studio auth rest storage realtime supavisor meta functions)
for attempt in $(seq 1 60); do
  docker compose --env-file .env up -d "${EXPECTED_SERVICES[@]}"
  running=0
  for service in "${EXPECTED_SERVICES[@]}"; do
    cid="$(docker compose --env-file .env ps -q "$service" 2>/dev/null || true)"
    [ -n "$cid" ] || continue
    state="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    [ "$state" = "running" ] && running=$((running+1))
  done
  echo "Tenant $TENANT: $running/${#EXPECTED_SERVICES[@]} serviços ativos (tentativa $attempt/60)"
  if [ "$running" -eq "${#EXPECTED_SERVICES[@]}" ]; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    docker compose --env-file .env ps -a >&2 || true
    echo "Falha: tenant $TENANT não estabilizou todos os serviços." >&2
    exit 3
  fi
  sleep 5
done

# Não conclua apenas porque os containers foram criados. Aguarde todos os
# serviços críticos entrarem em execução e, quando houver healthcheck, ficarem
# saudáveis.
if [ -f /srv/cloudif/lib/cloudif-supabase.sh ]; then
  # shellcheck source=/srv/cloudif/lib/cloudif-supabase.sh
  source /srv/cloudif/lib/cloudif-supabase.sh
  cloudif_supabase_wait_until_ready "$TENANT" "${CLOUDIF_TENANT_READY_TIMEOUT:-2700}" "${CLOUDIF_TENANT_READY_INTERVAL:-10}"
fi

"$BASE/bin/cloudif-render-router.sh"

# CloudIF v162: renderiza router SSO/Basic shield após criar/atualizar tenant.
if [ -x /srv/cloudif/bin/cloudif-render-router-sso.sh ]; then
  /srv/cloudif/bin/cloudif-render-router-sso.sh
fi

# O tenant só é anunciado como pronto depois que o certificado e a rota HTTPS
# pública também estiverem reconciliados.
if [ -x /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh ]; then
  /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh "$TENANT"
fi

echo "Tenant pronto: $TENANT"
echo "URL: https://${TENANT}.cloudiff.duckdns.org/"
echo "Credencial interna do dashboard está em: $TDIR/.env"
