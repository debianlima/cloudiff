#!/usr/bin/env bash
set -u
OUT=/var/log/cloudif-npm-healthcheck.log
NOW=$(date -Is)
status=0
check(){ name=$1; shift; if "$@" >/dev/null 2>&1; then echo "$NOW $name=ok" >>"$OUT"; else echo "$NOW $name=fail" >>"$OUT"; status=1; fi; }
check container docker inspect -f '{{.State.Running}}' cloudif-nginx-proxy-manager
check nginx docker exec cloudif-nginx-proxy-manager nginx -t
for host in authiff.duckdns.org cloudiff.duckdns.org; do
  code=$(curl -skS -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 15 "https://$host/" || echo 000)
  echo "$NOW host=$host code=$code" >>"$OUT"
  case "$host:$code" in
    authiff.duckdns.org:200|authiff.duckdns.org:302|cloudiff.duckdns.org:200|cloudiff.duckdns.org:302) ;;
    *) status=1;;
  esac
  expiry=$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2-)
  if [ -n "$expiry" ]; then
    exp_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo 0); now=$(date +%s); days=$(( (exp_epoch-now)/86400 ));
    echo "$NOW cert=$host days_remaining=$days" >>"$OUT"
    [ "$days" -ge 14 ] || status=1
  else
    echo "$NOW cert=$host fail" >>"$OUT"; status=1
  fi
done
latest=$(find /srv/cloudif/proxy/managed-backups -maxdepth 1 -type f -name 'npm-*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f1)
now=$(date +%s); ts=${latest%.*}; age=$((now-${ts:-0}))
echo "$NOW backup_age_seconds=$age" >>"$OUT"
[ "${ts:-0}" -gt 0 ] && [ "$age" -lt 129600 ] || status=1
exit "$status"
