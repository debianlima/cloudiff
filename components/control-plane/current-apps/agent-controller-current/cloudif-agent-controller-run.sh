#!/bin/bash
set -euo pipefail
mkdir -p /run/cloudif
exec 8>/run/cloudif/agent-controller.lock
flock -n 8 || exit 0
STAMP=/run/cloudif/agent-controller.last
NOW=$(date +%s)
LAST=0
[ ! -f "$STAMP" ] || LAST=$(cat "$STAMP" 2>/dev/null || echo 0)
if [ $((NOW-LAST)) -lt 5 ];then exit 0;fi
printf '%s\n' "$NOW" >"$STAMP"
exec /usr/bin/python3 /srv/cloudif/app-pointers/agent-controller-current/cloudif-agent-controller.py
