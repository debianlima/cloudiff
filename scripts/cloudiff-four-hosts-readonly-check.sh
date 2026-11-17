#!/usr/bin/env bash
# Read-only CloudIFF access/status check via pre-existing SSH wrappers.
set -Eeuo pipefail
ROOT=/srv/mcp-workspace/cloudiff-admin
for host in forja hospedagem mauricio faro; do
  printf 'HOST=%s\n' "$host"
  wrapper="$ROOT/ssh-$host"
  if [[ ! -x "$wrapper" ]]; then printf 'SSH=UNAVAILABLE\n'; continue; fi
  if output=$(timeout -k 2 16 "$wrapper" 'hostname; sudo -n /usr/local/sbin/cloudiff-rootctl status' 2>/dev/null); then
    printf 'SSH=AUTHENTICATED_DELEGATED\n'
    printf '%s\n' "$output" | grep -E '^(HOST=|TARGET=|USER_EFFECTIVE=|UID=|LOAD=|HEALTH |degraded$|forja$|hospedagem$|mauricio$|faro$)' | cut -c1-200 || true
  else printf 'SSH_OR_ROOTCTL=NOT_VERIFIED\n'; fi
done
