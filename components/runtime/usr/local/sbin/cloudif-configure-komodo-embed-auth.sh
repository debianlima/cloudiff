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
settings={
    'KOMODO_OIDC_AUTO_REDIRECT':'true',
    'OIDC_AUTO_REDIRECT':'true',
    'KOMODO_OIDC_REDIRECT_HOST':'https://authiff.duckdns.org',
    'OIDC_REDIRECT_HOST':'https://authiff.duckdns.org',
    'KOMODO_SESSION_ALLOW_CROSS_SITE':'true',
    'KOMODO_X_FRAME_OPTIONS':'',
    'KOMODO_CONTENT_SECURITY_POLICY':"frame-ancestors 'self' https://cloudiff.duckdns.org",
}
s=env.read_text()
for key,value in settings.items():
    pattern=re.compile(rf'(?m)^{re.escape(key)}=.*$')
    line=f'{key}={value}'
    if pattern.search(s):s=pattern.sub(line,s)
    else:s=s.rstrip()+f'\n{line}\n'
env.write_text(s)
y=oidc.read_text()
compose_values={
    'KOMODO_OIDC_AUTO_REDIRECT':'true',
    'OIDC_AUTO_REDIRECT':'true',
    'KOMODO_OIDC_REDIRECT_HOST':'https://authiff.duckdns.org',
    'OIDC_REDIRECT_HOST':'https://authiff.duckdns.org',
    'KOMODO_SESSION_ALLOW_CROSS_SITE':'true',
    'KOMODO_X_FRAME_OPTIONS':'',
    'KOMODO_CONTENT_SECURITY_POLICY':"frame-ancestors 'self' https://cloudiff.duckdns.org",
}
for key,value in compose_values.items():
    pattern=re.compile(rf'(?m)^(\s*{re.escape(key)}:\s*).*$')
    rendered='"'+value.replace('\\','\\\\').replace('\"','\\"')+'"'
    if pattern.search(y):
        y=pattern.sub(lambda m:m.group(1)+rendered,y)
    else:
        marker='    environment:\n'
        if marker not in y:raise SystemExit('oidc_compose_environment_missing')
        y=y.replace(marker,marker+f'      {key}: {rendered}\n',1)
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
grep -qx 'KOMODO_OIDC_REDIRECT_HOST=https://authiff.duckdns.org' "$BACKUP_DIR/core.env.after"
grep -qx 'OIDC_REDIRECT_HOST=https://authiff.duckdns.org' "$BACKUP_DIR/core.env.after"
grep -qx 'KOMODO_SESSION_ALLOW_CROSS_SITE=true' "$BACKUP_DIR/core.env.after"
grep -qx 'KOMODO_X_FRAME_OPTIONS=' "$BACKUP_DIR/core.env.after"
grep -Fxq "KOMODO_CONTENT_SECURITY_POLICY=frame-ancestors 'self' https://cloudiff.duckdns.org" "$BACKUP_DIR/core.env.after"

headers=$(mktemp)
curl -fsS -D "$headers" -o /dev/null --max-time 10 http://127.0.0.1:9120/auth/oidc/login
grep -Eqi '^location: https://authiff\.duckdns\.org/application/o/authorize/' "$headers"
grep -Eqi '^set-cookie: id=.*SameSite=None;.*Secure' "$headers"
if grep -Eqi '^x-frame-options:' "$headers"; then echo 'komodo_native_x_frame_options_present' >&2; rm -f "$headers"; exit 3; fi
grep -Fqi "content-security-policy: frame-ancestors 'self' https://cloudiff.duckdns.org" "$headers"
rm -f "$headers"
curl -fsS --max-time 10 http://127.0.0.1:9120/ >/dev/null

trap - EXIT
printf 'configured|auto_redirect=true|cross_site_session=true|native_frame_policy=portal-only|oidc_redirect=authiff|backup=%s\n' "$BACKUP_DIR"
