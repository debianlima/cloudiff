#!/usr/bin/env bash
set -euo pipefail
python3 -m py_compile /usr/local/sbin/cloudif-admin-portal.py /usr/local/sbin/cloudif-project-template-apply.py
/srv/cloudif/tests/cloudif-ui-security-smoke.sh
/usr/local/sbin/cloudif-control-plane-integrity.py check
systemctl is-active --quiet cloudif-admin-portal.service
curl -fsS --max-time 15 https://1006.cloudiff.duckdns.org/ >/dev/null
curl -fsS --max-time 15 https://1006-d5.cloudiff.duckdns.org/ >/dev/null
echo 'PASS|secure_release_gate'
