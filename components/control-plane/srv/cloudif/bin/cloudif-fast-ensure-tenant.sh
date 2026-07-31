#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/srv/cloudif"
TENANT="${1:?tenant}"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"
REGISTRY="$BASE/registry/tenants.csv"
REAL="$BASE/bin/cloudif-create-tenant.real.sh"
RENDER="$BASE/bin/cloudif-render-router-sso.sh"
DEEP="$BASE/bin/cloudif-tenant-deep-check.sh"
LOG="$BASE/logs/fast-ensure-${TENANT}.log"
LOCK="/tmp/cloudif-fast-ensure-${TENANT}.lock"

mkdir -p "$BASE/logs"

exec >> "$LOG" 2>&1

echo
echo "============================================================"
echo "Fast ensure tenant=$TENANT date=$(date -Is)"
echo "============================================================"

sanitize() {
  echo "$1" | tr -cd 'A-Za-z0-9_.-'
}

TENANT="$(sanitize "$TENANT")"

if [ -z "$TENANT" ]; then
  echo "ERRO: tenant vazio após sanitize"
  exit 1
fi

(
  flock -n 9 || {
    echo "Outro ensure já está rodando para $TENANT. Liberando sem bloquear."
    exit 0
  }

  healthy=0

  if [ -f "$ENV" ] && grep -qE "^${TENANT}," "$REGISTRY" 2>/dev/null; then
    port="$(grep -E '^KONG_HTTP_PORT=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
    [ -n "$port" ] || port="$(awk -F, -v t="$TENANT" 'NR>1 && $1==t {print $2}' "$REGISTRY")"

    user="$(grep -E '^DASHBOARD_USERNAME=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
    pass="$(grep -E '^DASHBOARD_PASSWORD=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
    [ -n "$user" ] || user="admin"

    if [ -n "$port" ] && [ -n "$pass" ]; then
      b64="$(printf '%s:%s' "$user" "$pass" | base64 -w0)"
      code="$(curl -sS -o "/tmp/cloudif-fast-${TENANT}.html" -w '%{http_code}' --max-time 5 \
        -H "Authorization: Basic $b64" \
        "http://10.62.92.7:${port}/" || true)"

      echo "Kong check tenant=$TENANT port=$port code=$code"

      case "$code" in
        200|301|302|303|307|308)
          healthy=1
          ;;
      esac
    fi
  fi

  if [ "$healthy" = "1" ]; then
    echo "FAST PATH: tenant já responde. Não vou recriar nem reiniciar."

    if [ -x "$RENDER" ]; then
      "$RENDER" || true
    fi

    if [ -x "$DEEP" ]; then
      nohup "$DEEP" "$TENANT" >/dev/null 2>&1 &
      echo "Deep-check iniciado em background."
    fi


# CloudIFF automatic tenant TLS
if [ -x /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh ]; then
  /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh "$TENANT" || echo "AVISO: certificado do tenant será reconciliado pelo monitor"
fi

    exit 0
  fi

  echo "SLOW PATH: tenant não existe ou Kong não responde. Chamando criador real."

  if [ ! -x "$REAL" ]; then
    echo "ERRO: criador real não existe: $REAL"
    exit 1
  fi

  "$REAL" "$TENANT"

  if [ -x "$RENDER" ]; then
    "$RENDER" || true
  fi

  if [ -x "$DEEP" ]; then
    nohup "$DEEP" "$TENANT" >/dev/null 2>&1 &
  fi

# CloudIFF automatic tenant TLS
if [ -x /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh ]; then
  /srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh "$TENANT" || echo "AVISO: certificado do tenant será reconciliado pelo monitor"
fi

) 9>"$LOCK"
