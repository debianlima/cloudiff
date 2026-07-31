#!/usr/bin/env bash
set -euo pipefail
. /etc/cloudif/project-backup-remote.env
[ "${REMOTE_ENABLED:-0}" = 1 ] || exit 0
[ "${REMOTE_READY:-0}" = 1 ] || { echo "remote backup pending: destination not ready"; exit 0; }
timeout 5 bash -c "</dev/tcp/${REMOTE_HOST}/${REMOTE_PORT}" || { echo "remote backup pending: server unavailable"; exit 0; }
find /srv/cloudif/managed-backups/projects -mindepth 2 -maxdepth 2 -type f -print0 | while IFS= read -r -d '' f; do
  rel=${f#/srv/cloudif/managed-backups/projects/}
  project=${rel%%/*}
  ok=0
  for attempt in 1 2 3 4; do
    if rsync -a --mkpath -e "ssh -i $REMOTE_KEY -p $REMOTE_PORT -o BatchMode=yes -o StrictHostKeyChecking=yes" "$f" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/$project/"; then
      ok=1
      break
    fi
    sleep $((attempt * 2))
  done
  [ "$ok" = 1 ] || { echo "remote sync failed: $rel" >&2; exit 1; }
  sleep 1
done
