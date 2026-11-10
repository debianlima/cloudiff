#!/bin/bash
set -Eeuo pipefail
ACTION=${1:-status}
SRC=${2:-.}
STATE=/var/lib/cloudif/directory-cache-release
CRED=/etc/credstore.encrypted/cloudif-directory-cache-authentik.cred
FILES=(
  /usr/local/sbin/cloudif-directory-cache-sync.py
  /etc/systemd/system/cloudif-directory-cache-sync.service
  /etc/systemd/system/cloudif-directory-cache-sync.timer
)
source_for(){
  case "$1" in
    /usr/local/sbin/cloudif-directory-cache-sync.py) printf '%s\n' "$SRC/components/control-plane/usr/local/sbin/cloudif-directory-cache-sync.py" ;;
    /etc/systemd/system/cloudif-directory-cache-sync.service) printf '%s\n' "$SRC/components/control-plane/etc/systemd/system/cloudif-directory-cache-sync.service" ;;
    /etc/systemd/system/cloudif-directory-cache-sync.timer) printf '%s\n' "$SRC/components/control-plane/etc/systemd/system/cloudif-directory-cache-sync.timer" ;;
  esac
}
status(){
  printf 'CREDENTIAL=%s\n' "$([ -s "$CRED" ] && echo present || echo missing)"
  for f in "${FILES[@]}"; do [ -e "$f" ] && printf 'FILE=%s present\n' "$f" || printf 'FILE=%s missing\n' "$f"; done
  systemctl is-enabled cloudif-directory-cache-sync.timer 2>/dev/null || true
  systemctl is-active cloudif-directory-cache-sync.timer 2>/dev/null || true
  systemctl show cloudif-directory-cache-sync.service -p Result -p ExecMainStatus 2>/dev/null || true
  [ -f /var/lib/cloudif/portal/directory-cache.db ] && sqlite3 /var/lib/cloudif/portal/directory-cache.db 'select key||"="||value from metadata order by key;' || true
}
apply(){
  [ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
  [ -s "$CRED" ] || { echo 'encrypted Authentik credential missing' >&2; exit 3; }
  install -d -m 0700 "$STATE/previous"
  : > "$STATE/existed"
  for f in "${FILES[@]}"; do
    src=$(source_for "$f"); [ -f "$src" ] || { echo "source missing: $src" >&2; exit 4; }
    key=$(printf '%s' "$f" | sha256sum | awk '{print $1}')
    if [ -e "$f" ]; then cp -a "$f" "$STATE/previous/$key"; printf '%s\n' "$f" >> "$STATE/existed"; fi
  done
  install -o root -g root -m 0755 "$(source_for /usr/local/sbin/cloudif-directory-cache-sync.py)" /usr/local/sbin/cloudif-directory-cache-sync.py
  install -o root -g root -m 0644 "$(source_for /etc/systemd/system/cloudif-directory-cache-sync.service)" /etc/systemd/system/cloudif-directory-cache-sync.service
  install -o root -g root -m 0644 "$(source_for /etc/systemd/system/cloudif-directory-cache-sync.timer)" /etc/systemd/system/cloudif-directory-cache-sync.timer
  systemctl daemon-reload
  systemctl start cloudif-directory-cache-sync.service
  systemctl enable --now cloudif-directory-cache-sync.timer
  systemctl is-active --quiet cloudif-directory-cache-sync.timer
  sqlite3 /var/lib/cloudif/portal/directory-cache.db 'pragma quick_check;' | grep -qx ok
  echo DIRECTORY_CACHE_INSTALL=PASS
}
rollback(){
  [ "$(id -u)" -eq 0 ] || { echo 'run as root on Hospedagem' >&2; exit 2; }
  [ -f "$STATE/existed" ] || { echo 'rollback state missing' >&2; exit 5; }
  systemctl disable --now cloudif-directory-cache-sync.timer 2>/dev/null || true
  for f in "${FILES[@]}"; do
    key=$(printf '%s' "$f" | sha256sum | awk '{print $1}')
    if grep -Fxq "$f" "$STATE/existed"; then
      [ -f "$STATE/previous/$key" ] || { echo "backup missing: $f" >&2; exit 6; }
      cp -a "$STATE/previous/$key" "$f"
    else
      rm -f "$f"
    fi
  done
  systemctl daemon-reload
  echo DIRECTORY_CACHE_ROLLBACK=PASS
}
case "$ACTION" in apply) apply ;; status) status ;; rollback) rollback ;; *) echo 'usage: install_directory_cache_sync.sh {apply|status|rollback} [source-root]' >&2; exit 64 ;; esac
