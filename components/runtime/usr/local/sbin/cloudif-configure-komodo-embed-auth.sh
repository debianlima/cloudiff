#!/usr/bin/env bash
set -euo pipefail

BASE=/srv/cloudif/komodo
ENV_FILE="$BASE/compose.env"
OIDC_FILE="$BASE/docker-compose.cloudif-oidc-final.yml"
COMPOSE_FILES=(
  "$BASE/docker-compose.cloudif-stability.yml"
  "$BASE/mongo.compose.yaml"
  "$OIDC_FILE"
  "$BASE/docker-compose.override.yml"
)
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="$BASE/backups/embed-auth-$STAMP"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

for f in "$ENV_FILE" "${COMPOSE_FILES[@]}"; do
  [ -f "$f" ] || { echo "komodo_compose_file_missing:$f" >&2; exit 2; }
done
cp -a "$ENV_FILE" "$BACKUP_DIR/compose.env"
cp -a "$OIDC_FILE" "$BACKUP_DIR/docker-compose.cloudif-oidc-final.yml"

python3 - "$ENV_FILE" "$OIDC_FILE" <<'PY'
from pathlib import Path
import re,sys
env=Path(sys.argv[1]);oidc=Path(sys.argv[2])
s=env.read_text()
for key in ('KOMODO_OIDC_AUTO_REDIRECT','OIDC_AUTO_REDIRECT'):
    pattern=re.compile(rf'(?m)^{re.escape(key)}=.*$')
    if pattern.search(s):s=pattern.sub(f'{key}=true',s)
    else:s=s.rstrip()+f'\n{key}=true\n'
env.write_text(s)
y=oidc.read_text()
for key in ('KOMODO_OIDC_AUTO_REDIRECT','OIDC_AUTO_REDIRECT'):
    pattern=re.compile(rf'(?m)^(\s*{re.escape(key)}:\s*)["\']?(?:true|false)["\']?\s*$')
    if not pattern.search(y):raise SystemExit(f'oidc_compose_key_missing:{key}')
    y=pattern.sub(r'\1"true"',y)
oidc.write_text(y)
PY

compose() {
  docker compose --env-file "$ENV_FILE" \
    -f "${COMPOSE_FILES[0]}" \
    -f "${COMPOSE_FILES[1]}" \
    -f "${COMPOSE_FILES[2]}" \
    -f "${COMPOSE_FILES[3]}" "$@"
}

rollback() {
  cp -a "$BACKUP_DIR/compose.env" "$ENV_FILE"
  cp -a "$BACKUP_DIR/docker-compose.cloudif-oidc-final.yml" "$OIDC_FILE"
  compose up -d core >/dev/null 2>&1 || true
}
trap 'rc=$?; if [ "$rc" -ne 0 ]; then rollback; fi; exit "$rc"' EXIT

compose config >/dev/null
compose up -d core

for _ in $(seq 1 30); do
  if docker inspect komodo-core-1 --format '{{.State.Status}}' 2>/dev/null | grep -qx running \
    && curl -fsS --max-time 5 http://127.0.0.1:9120/ >/dev/null; then
    break
  fi
  sleep 1
done

docker inspect komodo-core-1 --format '{{range .Config.Env}}{{println .}}{{end}}' >"$BACKUP_DIR/core.env.after"
grep -qx 'KOMODO_OIDC_AUTO_REDIRECT=true' "$BACKUP_DIR/core.env.after"
grep -qx 'OIDC_AUTO_REDIRECT=true' "$BACKUP_DIR/core.env.after"
curl -fsS --max-time 10 http://127.0.0.1:9120/ >/dev/null

trap - EXIT
printf 'configured|auto_redirect=true|backup=%s\n' "$BACKUP_DIR"
