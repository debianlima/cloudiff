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

cloudif_supabase_tenant_basic_health() {
  TENANT="$1"

  cloudif_supabase_tenant_exists "$TENANT" || return 1
  cloudif_supabase_tenant_has_compose "$TENANT" || return 1

  if cloudif_supabase_tenant_has_bad_containers "$TENANT"; then
    return 1
  fi

  return 0
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
