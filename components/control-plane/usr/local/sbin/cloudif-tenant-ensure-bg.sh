#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant obrigatório}"
ACTION="${2:-auto}"
USERNAME="${3:-unknown}"

BASE="/srv/cloudif"
DOMAIN="cloudiff.duckdns.org"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"
CONF="$BASE/router/conf.d/default.conf"
CREATE_SCRIPT="$BASE/bin/cloudif-create-tenant.real.sh"
RENDER="$BASE/bin/cloudif-render-router-sso.sh"
CERT_HELPER="$BASE/bin/cloudif-ensure-tenant-certificate.sh"

STATUS_DIR="/var/lib/cloudif/provision/status"
LOCK_DIR="/var/lib/cloudif/provision/locks"
LOG_DIR="/var/log/cloudif/provision"

mkdir -p "$STATUS_DIR" "$LOCK_DIR" "$LOG_DIR"

STATUS="$STATUS_DIR/$TENANT.env"
LOCK="$LOCK_DIR/$TENANT.lock"
LOG="$LOG_DIR/$TENANT-$(date +%F-%H%M%S).log"

write_status() {
  STATE="$1"
  MSG="$2"
  {
    echo "TENANT=$TENANT"
    echo "ACTION=$ACTION"
    echo "USERNAME=$USERNAME"
    echo "STATE=$STATE"
    echo "MESSAGE=$MSG"
    echo "UPDATED_AT=$(date -Is)"
    echo "LOG=$LOG"
  } > "$STATUS"
}

router_has_tenant() {
  [ -f "$CONF" ] && grep -qE "($TENANT|${TENANT}\.cloudiff\.duckdns\.org)" "$CONF"
}

get_port() {
  [ -f "$ENV" ] || return 1
  grep -E '^(KONG_HTTP_PORT|KONG_PORT|KONG_HTTP)=' "$ENV" \
    | head -n1 \
    | cut -d= -f2- \
    | tr -d '"' \
    | tr -d "'" || true
}

kong_alive() {
  [ -f "$ENV" ] || return 1
  PORT="$(get_port)"
  [ -n "$PORT" ] || return 1

  CODE="$(curl -sS --max-time 8 \
    -H "Host: ${TENANT}.${DOMAIN}" \
    -o /tmp/cloudif-kong-${TENANT}.out \
    -w "%{http_code}" \
    "http://127.0.0.1:${PORT}/" || true)"

  case "$CODE" in
    200|301|302|307|308|401|403|404) return 0 ;;
    *) return 1 ;;
  esac
}

compose_not_bad() {
  [ -d "$TDIR" ] || return 1
  (
    cd "$TDIR"
    docker compose ps > "/tmp/cloudif-compose-${TENANT}.txt" 2>&1
  ) || return 1

  if grep -Eiq 'exited|dead|removing' "/tmp/cloudif-compose-${TENANT}.txt"; then
    return 1
  fi

  grep -Eiq 'kong|studio|db' "/tmp/cloudif-compose-${TENANT}.txt"
}

tenant_healthy() {
  compose_not_bad && kong_alive
}

normalize_env_urls() {
  [ -f "$ENV" ] || return 0

  URL="https://${TENANT}.${DOMAIN}"

  python3 - "$ENV" "$URL" <<'PY'
from pathlib import Path
import sys

env = Path(sys.argv[1])
url = sys.argv[2]

wanted = {
    "API_EXTERNAL_URL": url,
    "SITE_URL": url,
    "SUPABASE_PUBLIC_URL": url,
    "ADDITIONAL_REDIRECT_URLS": url,
}

lines = env.read_text(errors="ignore").splitlines()
out = []
seen = set()

for line in lines:
    if "=" not in line or line.strip().startswith("#"):
        out.append(line)
        continue

    k, v = line.split("=", 1)
    if k in wanted:
        out.append(f"{k}={wanted[k]}")
        seen.add(k)
    else:
        out.append(line)

for k, v in wanted.items():
    if k not in seen:
        out.append(f"{k}={v}")

env.write_text("\n".join(out) + "\n")
PY
}

ensure_certificate() {
  [ -x "$CERT_HELPER" ] || { echo "ERRO: helper de certificado ausente: $CERT_HELPER"; return 1; }
  local attempt
  for attempt in 1 2 3; do
    echo "==> Garantindo certificado TLS do tenant (tentativa $attempt/3)"
    if "$CERT_HELPER" "$TENANT"; then
      echo "OK: certificado TLS emitido/validado e associado ao subdomínio."
      return 0
    fi
    sleep $((attempt * 5))
  done
  echo "ERRO: não foi possível emitir/validar o certificado TLS do tenant."
  return 1
}

exec 9>"$LOCK"
if ! flock -n 9; then
  write_status "running" "Já existe tarefa em andamento para este tenant."
  exit 0
fi

exec > >(tee -a "$LOG") 2>&1

# CloudIF lowmem global lock BEGIN
GLOBAL_LOCK="$LOCK_DIR/global-create-restore.lock"
exec 8>"$GLOBAL_LOCK"
if ! flock -w "${CLOUDIF_GLOBAL_LOCK_WAIT:-300}" 8; then
  write_status "queued" "Servidor ocupado preparando outro tenant. Tente novamente em instantes."
  echo "Servidor ocupado: outro create/restore em andamento."
  exit 0
fi
# CloudIF lowmem global lock END


echo "============================================================"
echo " CloudIF Ensure Tenant Background v253"
echo "============================================================"
echo "TENANT=$TENANT"
echo "ACTION=$ACTION"
echo "USERNAME=$USERNAME"

# CloudIF v2 tunables BEGIN
HEALTH_ATTEMPTS="${CLOUDIF_ENSURE_HEALTH_ATTEMPTS:-30}"
HEALTH_SLEEP="${CLOUDIF_ENSURE_HEALTH_SLEEP:-3}"
STABILIZE_SLEEP="${CLOUDIF_ENSURE_STABILIZE_SLEEP:-6}"
# CloudIF v2 tunables END

# CLOUDIF lowmem health tunning BEGIN
HEALTH_ATTEMPTS="${CLOUDIF_ENSURE_HEALTH_ATTEMPTS:-20}"
HEALTH_SLEEP="${CLOUDIF_ENSURE_HEALTH_SLEEP:-3}"
STABILIZE_SLEEP="${CLOUDIF_ENSURE_STABILIZE_SLEEP:-5}"
# CLOUDIF lowmem health tunning END

NEEDS_RENDER=0

if tenant_healthy && router_has_tenant; then
  if ensure_certificate; then
    write_status "ready" "Ambiente saudável, renderizado e com certificado TLS válido."
    echo "OK: tenant saudável, renderizado e certificado."
    exit 0
  fi
  write_status "failed" "Tenant saudável, mas o certificado TLS não pôde ser emitido/validado."
  exit 1
fi

if [ ! -d "$TDIR" ]; then
  ACTION="create"
  NEEDS_RENDER=1
  write_status "creating" "Tenant não existe. Criando stack Supabase em segundo plano."

  if [ ! -x "$CREATE_SCRIPT" ]; then
    write_status "failed" "Script de criação não encontrado ou não executável: $CREATE_SCRIPT"
    exit 1
  fi

  echo "==> Criando tenant"
  "$CREATE_SCRIPT" "$TENANT"

elif ! router_has_tenant; then
  NEEDS_RENDER=1
  ACTION="render"
  write_status "rendering" "Tenant existe, mas ainda não está no router. Renderizando."

else
  ACTION="restore"
  write_status "restoring" "Tenant existe, mas está instável. Subindo containers sem renderizar router."
fi

normalize_env_urls

if [ -d "$TDIR" ]; then
  echo "==> Subindo/verificando containers"
  (
    cd "$TDIR"
    docker compose --env-file .env up -d --remove-orphans
  )
fi

if [ -x "/srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh" ]; then
  echo "==> Sincronizando roles internas v2"
  /srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh "$TENANT" || true
elif [ -x "/srv/cloudif/bin/cloudif-sync-db-passwords.sh" ]; then
  echo "==> Sincronizando roles internas legado"
  /srv/cloudif/bin/cloudif-sync-db-passwords.sh "$TENANT" || true
fi

if [ "$NEEDS_RENDER" = "1" ]; then
  if router_has_tenant; then
    echo "OK: tenant já apareceu no router. Pulando render extra."
  else
    echo "==> Renderizando router uma única vez"
    "$RENDER"
  fi
else
  echo "OK: restore/check sem render. Evitando reload storm."
fi

write_status "waiting_health" "Aguardando estabilização do ambiente."
sleep "$STABILIZE_SLEEP"

for i in $(seq 1 "$HEALTH_ATTEMPTS"); do
  if tenant_healthy && router_has_tenant; then
    if ensure_certificate; then
      write_status "ready" "Ambiente pronto, saudável e com certificado TLS válido."
      echo "OK: tenant saudável e certificado."
      exit 0
    fi
    write_status "waiting_certificate" "Ambiente saudável; aguardando emissão/validação do certificado TLS."
  fi

  echo "Aguardando saúde/render do tenant... tentativa $i/$HEALTH_ATTEMPTS"
  sleep "$HEALTH_SLEEP"
done

write_status "failed" "Tenant não ficou saudável/renderizado no tempo esperado."
exit 1
