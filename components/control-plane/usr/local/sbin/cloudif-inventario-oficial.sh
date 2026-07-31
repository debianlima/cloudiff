#!/usr/bin/env bash
set -Eeuo pipefail

OUT="/srv/cloudif/oficial/inventory/cloudif-inventory-$(hostname)-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$(dirname "$OUT")"

{
  echo "============================================================"
  echo " CLOUDIF - INVENTÁRIO OFICIAL"
  echo "============================================================"
  echo "Data: $(date -Is)"
  echo "Host: $(hostname)"
  echo

  echo "===== SCRIPTS CLOUDIF EM /usr/local/bin ====="
  find /usr/local/bin -maxdepth 1 -type f -iname '*cloudif*' -printf '%p\n' 2>/dev/null | sort
  echo

  echo "===== SCRIPTS CLOUDIF EM /usr/local/sbin ====="
  find /usr/local/sbin -maxdepth 1 -type f -iname '*cloudif*' -printf '%p\n' 2>/dev/null | sort
  echo

  echo "===== ARQUIVOS CLOUDIF EM /srv/cloudif ====="
  find /srv/cloudif -maxdepth 4 -type f \( -iname '*cloudif*' -o -iname '*.yml' -o -iname '*.env' -o -iname '*.sh' -o -iname '*.py' \) 2>/dev/null | sort
  echo

  echo "===== SERVIÇOS SYSTEMD CLOUDIF ====="
  systemctl list-unit-files | grep -Ei 'cloudif|komodo|forgejo|authentik|supabase|nginx|proxy|docker' || true
  echo

  echo "===== CONTAINERS CLOUDIF ====="
  docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true
  echo

  echo "===== PORTAS IMPORTANTES ====="
  ss -tulpn | grep -E ':(80|443|3000|2222|8000|8099|9000|9443|9120|18091|18092|18093)\b' || true
  echo

} | tee "$OUT"

echo
echo "Arquivo gerado: $OUT"
