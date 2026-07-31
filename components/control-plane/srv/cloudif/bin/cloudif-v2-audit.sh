#!/usr/bin/env bash
set -Eeuo pipefail

echo "============================================================"
echo " CloudIF v2 audit"
echo " Data: $(date -Is)"
echo "============================================================"

echo
echo "===== Serviços ====="
systemctl --no-pager --full status cloudif-authz-gate cloudif-tenant-guard cloudif-supabase-session-broker cloudif-supabase-launch-api 2>/dev/null | sed -n '1,160p' || true

echo
echo "===== Env v2 ====="
cat /etc/cloudif/cloudif-access.env 2>/dev/null || true

echo
echo "===== Tenants ====="
find /srv/cloudif/tenants -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort || true

echo
echo "===== Status provision ====="
for f in /var/lib/cloudif/provision/status/*.env; do
  [ -f "$f" ] || continue
  echo
  echo "--- $f ---"
  cat "$f"
done

echo
echo "===== Docker CloudIF ====="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -Ei 'cloudif|supabase|realtime|pooler|kong|studio' || true

echo
echo "===== Testes locais authz/guard ====="
curl -sS -I --max-time 5 http://10.62.92.7:18092/health 2>/dev/null || true
curl -sS -I --max-time 5 http://10.62.92.7:18093/health 2>/dev/null || true
