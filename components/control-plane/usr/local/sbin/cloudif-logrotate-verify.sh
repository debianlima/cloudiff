#!/usr/bin/env bash
set -euo pipefail
LOG=/var/log/cloudif-logrotate-verify.log
NOW=$(date -Is)
status=0
svc_result=$(systemctl show logrotate.service -p Result --value 2>/dev/null || true)
svc_exit=$(systemctl show logrotate.service -p ExecMainStatus --value 2>/dev/null || true)
last_exit=$(systemctl show logrotate.service -p ExecMainExitTimestampMonotonic --value 2>/dev/null || echo 0)
now_mono=$(awk '{printf "%.0f", $1*1000000}' /proc/uptime)
age_sec=$(( (now_mono - ${last_exit:-0}) / 1000000 ))
[ "$svc_result" = success ] || status=1
[ "${svc_exit:-1}" = 0 ] || status=1
[ "$age_sec" -le 129600 ] || status=1
for f in /var/log/cloudif-healthcheck.log /var/log/cloudif-restore-test.log; do
  [ -e "$f" ] || continue
  owner=$(stat -c '%U:%G' "$f")
  mode=$(stat -c '%a' "$f")
  [ "$owner" = root:adm ] || status=1
  [ "$mode" = 640 ] || status=1
done
printf '%s result=%s service_result=%s exit=%s age_sec=%s\n' "$NOW" "$([ "$status" -eq 0 ] && echo ok || echo fail)" "$svc_result" "$svc_exit" "$age_sec" >>"$LOG"
exit "$status"
