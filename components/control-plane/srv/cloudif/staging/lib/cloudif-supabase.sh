#!/usr/bin/env bash
# TIPO=library
# AÇÃO=funções para tenants Supabase CloudIF
# ALTERA=Supabase/router apenas quando funções de criação/render forem chamadas

cloudif_supabase_tenants_dir() {
  echo "${CLOUDIF_SUPABASE_TENANTS_DIR:-/srv/cloudif/tenants}"
}

cloudif_supabase_create_script() {
  echo "${CLOUDIF_CREATE_TENANT_SCRIPT:-/srv/cloudif/bin/cloudif-create-tenant.real.sh}"
}

cloudif_supabase_render_script() {
  echo "${CLOUDIF_RENDER_ROUTER_SCRIPT:-/srv/cloudif/bin/cloudif-render-router-sso.sh}"
}

cloudif_supabase_domain() {
  echo "${CLOUDIF_DOMAIN:-cloudiff.duckdns.org}"
}

cloudif_supabase_tenant_dir() {
  TENANT="$1"
  echo "$(cloudif_supabase_tenants_dir)/$TENANT"
}

cloudif_supabase_tenant_exists() {
  TENANT="$1"
  test -d "$(cloudif_supabase_tenant_dir "$TENANT")"
}

cloudif_supabase_tenant_url() {
  TENANT="$1"
  echo "https://${TENANT}.$(cloudif_supabase_domain)/project/default"
}

cloudif_supabase_compose_ps() {
  TENANT="$1"
  TDIR="$(cloudif_supabase_tenant_dir "$TENANT")"

  if [ ! -d "$TDIR" ]; then
    return 1
  fi

  (
    cd "$TDIR"
    docker compose ps
  )
}

cloudif_supabase_tenant_has_compose() {
  TENANT="$1"
  TDIR="$(cloudif_supabase_tenant_dir "$TENANT")"
  test -f "$TDIR/docker-compose.yml" || test -f "$TDIR/compose.yml"
}

cloudif_supabase_tenant_has_bad_containers() {
  TENANT="$1"
  TMP="/tmp/cloudif-supabase-ps-${TENANT}.txt"

  cloudif_supabase_compose_ps "$TENANT" > "$TMP" 2>&1 || return 0

  if grep -Eiq 'exited|dead|removing|unhealthy' "$TMP"; then
    return 0
  fi

  return 1
}

cloudif_supabase_required_services() {
  echo "${CLOUDIF_SUPABASE_REQUIRED_SERVICES:-db kong studio meta auth rest storage realtime supavisor}"
}

cloudif_supabase_tenant_basic_health() {
  TENANT="$1"
  TDIR="$(cloudif_supabase_tenant_dir "$TENANT")"

  cloudif_supabase_tenant_exists "$TENANT" || return 1
  cloudif_supabase_tenant_has_compose "$TENANT" || return 1

  for SERVICE in $(cloudif_supabase_required_services); do
    CID="$(cd "$TDIR" && docker compose --env-file .env ps -q "$SERVICE" 2>/dev/null || true)"
    [ -n "$CID" ] || return 1

    STATE="$(docker inspect -f '{{.State.Status}}' "$CID" 2>/dev/null || true)"
    [ "$STATE" = "running" ] || return 1

    HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID" 2>/dev/null || true)"
    case "$HEALTH" in
      healthy|none) ;;
      *) return 1 ;;
    esac
  done

  return 0
}

cloudif_supabase_wait_until_ready() {
  TENANT="$1"
  TIMEOUT="${2:-${CLOUDIF_TENANT_READY_TIMEOUT:-2700}}"
  INTERVAL="${3:-${CLOUDIF_TENANT_READY_INTERVAL:-10}}"
  START="$(date +%s)"
  ATTEMPT=0

  while true; do
    ATTEMPT=$((ATTEMPT + 1))
    if cloudif_supabase_tenant_basic_health "$TENANT"; then
      echo "Tenant $TENANT pronto após $ATTEMPT verificações."
      return 0
    fi

    NOW="$(date +%s)"
    ELAPSED=$((NOW - START))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
      echo "Timeout aguardando tenant $TENANT após ${ELAPSED}s." >&2
      cloudif_supabase_compose_ps "$TENANT" >&2 || true
      return 1
    fi

    echo "Aguardando tenant $TENANT: serviços críticos ainda não estão prontos (${ELAPSED}s/${TIMEOUT}s)."
    sleep "$INTERVAL"
  done
}

cloudif_supabase_create_tenant() {
  TENANT="$1"
  CREATE_SCRIPT="$(cloudif_supabase_create_script)"

  if [ ! -x "$CREATE_SCRIPT" ]; then
    cloudif_error "Script de criação de tenant não encontrado ou não executável: $CREATE_SCRIPT"
    return 1
  fi

  "$CREATE_SCRIPT" "$TENANT"
}

cloudif_supabase_render_router() {
  RENDER_SCRIPT="$(cloudif_supabase_render_script)"

  if [ ! -x "$RENDER_SCRIPT" ]; then
    cloudif_error "Script de render do router não encontrado ou não executável: $RENDER_SCRIPT"
    return 1
  fi

  "$RENDER_SCRIPT"
}
