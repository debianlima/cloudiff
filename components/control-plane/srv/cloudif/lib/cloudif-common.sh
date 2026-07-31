#!/usr/bin/env bash
# TIPO=library
# AÇÃO=funções comuns CloudIF
# ALTERA=nada quando apenas carregado

cloudif_now() {
  date -Is
}

cloudif_log() {
  LEVEL="$1"
  shift
  printf '[%s] [%s] %s\n' "$(cloudif_now)" "$LEVEL" "$*"
}

cloudif_info() {
  cloudif_log "INFO" "$@"
}

cloudif_warn() {
  cloudif_log "WARN" "$@"
}

cloudif_error() {
  cloudif_log "ERROR" "$@"
}

cloudif_require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    cloudif_error "Execute como root."
    exit 1
  fi
}

cloudif_require_command() {
  CMD="$1"
  if ! command -v "$CMD" >/dev/null 2>&1; then
    cloudif_error "Comando obrigatório não encontrado: $CMD"
    exit 1
  fi
}

cloudif_sanitize_username() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9._-]+/-/g; s/^[.-]+//; s/[.-]+$//' \
    | cut -c1-48
}

cloudif_sanitize_slug() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9-]+/-/g; s/^-+//; s/-+$//' \
    | cut -c1-63
}

cloudif_lock_or_exit() {
  LOCKFILE="$1"
  mkdir -p "$(dirname "$LOCKFILE")"
  exec 9>"$LOCKFILE"
  if ! flock -n 9; then
    cloudif_error "Outra execução já está em andamento: $LOCKFILE"
    exit 1
  fi
}
