#!/usr/bin/env bash
# TIPO=real
# AÇÃO=garante tenant Supabase pessoal do usuário
# ALTERA=Supabase/router se o tenant não existir; se existir, valida e registra estado
set -Eeuo pipefail

BASE="/srv/cloudif"
. "$BASE/lib/cloudif-common.sh"
. "$BASE/lib/cloudif-supabase.sh"

cloudif_require_root
cloudif_require_command docker

USERNAME_RAW="${1:?Informe o username}"
USERNAME="$(cloudif_sanitize_username "$USERNAME_RAW")"

if [ -z "$USERNAME" ]; then
  cloudif_error "Username inválido: $USERNAME_RAW"
  exit 1
fi

if [ "$USERNAME" != "$USERNAME_RAW" ]; then
  cloudif_error "Username informado difere do sanitizado. Informado='$USERNAME_RAW' Sanitizado='$USERNAME'"
  exit 1
fi

TENANT="$USERNAME"
LOCK="/run/cloudif/supabase-tenant-$TENANT.lock"
STATE_DIR="/var/lib/cloudif/user-workspaces"
LOG_STATE="$STATE_DIR/$USERNAME.env"

mkdir -p "$STATE_DIR"
cloudif_lock_or_exit "$LOCK"

cloudif_info "Usuário: $USERNAME"
cloudif_info "Tenant: $TENANT"
cloudif_info "Diretório: $(cloudif_supabase_tenant_dir "$TENANT")"
cloudif_info "URL: $(cloudif_supabase_tenant_url "$TENANT")"

TENANT_CREATED=0

if cloudif_supabase_tenant_exists "$TENANT"; then
  cloudif_info "Tenant já existe."
else
  cloudif_info "Tenant não existe. Criando tenant Supabase real."
  cloudif_supabase_create_tenant "$TENANT"
  TENANT_CREATED=1
fi

if [ "$TENANT_CREATED" = "1" ]; then
  cloudif_info "Tenant novo criado. Renderizando router uma única vez."
  cloudif_supabase_render_router
else
  cloudif_info "Tenant já existia. Router não será renderizado por este comando."
fi

cloudif_info "Conferindo docker compose do tenant"
cloudif_supabase_compose_ps "$TENANT" || true

if cloudif_supabase_tenant_basic_health "$TENANT"; then
  STATUS="ready"
  MESSAGE="Tenant Supabase existe e não possui containers em estado ruim no compose."
  cloudif_info "OK: health básico aprovado."
else
  STATUS="attention"
  MESSAGE="Tenant existe, mas precisa de atenção no compose/containers."
  cloudif_warn "Health básico não aprovado."
fi

{
  echo "USERNAME=$USERNAME"
  echo "TENANT=$TENANT"
  echo "SUPABASE_URL=$(cloudif_supabase_tenant_url "$TENANT")"
  echo "SUPABASE_STATUS=$STATUS"
  echo "SUPABASE_MESSAGE=$MESSAGE"
  echo "UPDATED_AT=$(date -Is)"
} > "$LOG_STATE"

chmod 0640 "$LOG_STATE"

cloudif_info "Estado atualizado: $LOG_STATE"
cloudif_info "Resultado: $STATUS - $MESSAGE"

if [ "$STATUS" != "ready" ]; then
  exit 2
fi

cloudif_info "OK: tenant Supabase pessoal garantido."
