#!/usr/bin/env bash
set -Eeuo pipefail

ROUTER="${CLOUDIF_ROUTER_CONTAINER:-cloudif-tenant-router}"
NOFILE="${CLOUDIF_ROUTER_NOFILE:-262144}"
WORKER_CONNECTIONS="${CLOUDIF_ROUTER_WORKER_CONNECTIONS:-32768}"
STAMP="$(date +%F-%H%M%S)"

echo "------------------------------------------------------------"
echo " CloudIF Tune Router Nginx Limits v243"
echo "------------------------------------------------------------"
echo "ROUTER=$ROUTER"
echo "NOFILE=$NOFILE"
echo "WORKER_CONNECTIONS=$WORKER_CONNECTIONS"

docker exec "$ROUTER" sh -lc "cp -a /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bkp-cloudif-limits-v243-$STAMP"

docker exec "$ROUTER" sh -lc "
set -eu
CONF=/etc/nginx/nginx.conf

if grep -qE '^worker_processes[[:space:]]+' \"\$CONF\"; then
  sed -i 's/^worker_processes[[:space:]][[:space:]]*.*/worker_processes auto;/' \"\$CONF\"
else
  sed -i '1i worker_processes auto;' \"\$CONF\"
fi

if grep -qE '^worker_rlimit_nofile[[:space:]]+' \"\$CONF\"; then
  sed -i 's/^worker_rlimit_nofile[[:space:]][[:space:]]*.*/worker_rlimit_nofile ${NOFILE};/' \"\$CONF\"
else
  sed -i '/^worker_processes[[:space:]][[:space:]]*/a worker_rlimit_nofile ${NOFILE};' \"\$CONF\"
fi

if grep -qE 'worker_connections[[:space:]]+[0-9]+' \"\$CONF\"; then
  sed -i 's/worker_connections[[:space:]][[:space:]]*[0-9][0-9]*;/worker_connections ${WORKER_CONNECTIONS};/' \"\$CONF\"
else
  sed -i '/events[[:space:]]*{/a \    worker_connections ${WORKER_CONNECTIONS};' \"\$CONF\"
fi

if ! grep -q 'multi_accept on;' \"\$CONF\"; then
  sed -i '/events[[:space:]]*{/a \    multi_accept on;' \"\$CONF\"
fi
"

docker exec "$ROUTER" nginx -t
docker exec "$ROUTER" nginx -s reload

docker exec "$ROUTER" sh -lc "nginx -T 2>/dev/null | grep -nE 'worker_processes|worker_rlimit_nofile|worker_connections|multi_accept' | sed -n '1,120p'"
docker exec "$ROUTER" sh -lc '
for p in $(pgrep nginx || true); do
  echo "PID=$p CMD=$(tr "\0" " " < /proc/$p/cmdline)"
  cat /proc/$p/limits | grep -Ei "open files|max processes" || true
done
'

echo "OK: tuning v243 aplicado."
