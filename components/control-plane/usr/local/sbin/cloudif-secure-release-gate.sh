#!/usr/bin/env bash
set -euo pipefail
python3 -m py_compile \
 /usr/local/sbin/cloudif-admin-portal.py \
 /usr/local/sbin/cloudif-project-template-apply.py \
 /srv/cloudif/lib/cloudif_ui_pages.py \
 /srv/cloudif/lib/cloudif_ui_components.py
/srv/cloudif/tests/cloudif-ui-security-tests.py
/usr/local/sbin/cloudif-control-plane-integrity.py check >/dev/null
for u in \
 https://cloudiff.duckdns.org/ \
 https://admin.cloudiff.duckdns.org/ \
 https://authiff.duckdns.org/ \
 https://komodoiff.duckdns.org/ \
 https://supabaseiff.duckdns.org/; do
 code=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$u")
 case "$u:$code" in
   *supabaseiff.duckdns.org/:401|*:200|*:301|*:302|*:303) : ;;
   *) echo "FAIL|endpoint|$u|$code" >&2; exit 1;;
 esac
done
echo 'PASS|cloudif-secure-release-gate'
