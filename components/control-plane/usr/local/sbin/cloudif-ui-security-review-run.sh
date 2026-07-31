#!/usr/bin/env bash
set -euo pipefail
D=/srv/cloudif/documentacao/security-reviews
mkdir -p "$D"
O="$D/review-$(date +%Y%m%d-%H%M%S).log"
{
 echo "timestamp=$(date -Is)"
 /usr/local/sbin/cloudif-secure-release-gate.sh
 systemctl show cloudif-admin-portal.service -p ActiveState -p Result -p ExecMainStatus
 df -h /
} >"$O" 2>&1
find "$D" -type f -name 'review-*.log' -mtime +90 -delete
ln -sfn "$O" "$D/latest.log"
