#!/usr/bin/env bash
set -euo pipefail

BASE=/srv/cloudif/proxy/npm
DB="$BASE/data/database.sqlite"
CONF_DIR="$BASE/data/nginx/proxy_host"
CONTAINER=cloudif-nginx-proxy-manager
PORTAL_ORIGIN=https://cloudiff.duckdns.org
KOMODO_DOMAIN=komodoiff.duckdns.org
AUTH_DOMAIN=authiff.duckdns.org
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="$BASE/backups/komodo-embed-$STAMP"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

[ -f "$DB" ] || { echo 'npm_database_missing' >&2; exit 2; }
cp -a "$DB" "$BACKUP_DIR/database.sqlite"
chmod 600 "$BACKUP_DIR/database.sqlite"

resolve_host_id() {
  python3 - "$DB" "$1" <<'PY'
import json,sqlite3,sys
p,domain=sys.argv[1:3]
c=sqlite3.connect(p);c.row_factory=sqlite3.Row
rows=[]
for r in c.execute('select id,domain_names from proxy_host where enabled=1 and is_deleted=0'):
    try:names=json.loads(r['domain_names'] or '[]')
    except Exception:names=[]
    if domain in names:rows.append(r)
if len(rows)!=1:raise SystemExit(f'proxy_host_not_unique:{domain}')
print(rows[0]['id']);c.close()
PY
}

KOMODO_HOST_ID=$(resolve_host_id "$KOMODO_DOMAIN")
AUTH_HOST_ID=$(resolve_host_id "$AUTH_DOMAIN")
KOMODO_CONF="$CONF_DIR/$KOMODO_HOST_ID.conf"
AUTH_CONF="$CONF_DIR/$AUTH_HOST_ID.conf"
for conf in "$KOMODO_CONF" "$AUTH_CONF"; do
  [ -f "$conf" ] || { echo "npm_generated_host_config_missing:$conf" >&2; exit 3; }
  cp -a "$conf" "$BACKUP_DIR/$(basename "$conf")"
done

patch_db_host() {
  local host_id="$1" marker="$2"
  python3 - "$DB" "$host_id" "$PORTAL_ORIGIN" "$marker" <<'PY'
import re,sqlite3,sys
p,host_id,portal,marker=sys.argv[1],int(sys.argv[2]),sys.argv[3],sys.argv[4]
begin=f'# CloudIF {marker} Portal Embed BEGIN';end=f'# CloudIF {marker} Portal Embed END'
block=f'''{begin}
more_clear_headers 'X-Frame-Options';
more_set_headers "Content-Security-Policy: frame-ancestors 'self' {portal}";
more_set_headers -t 'text/html' 'Cache-Control: no-store';
{end}'''
c=sqlite3.connect(p)
row=c.execute('select advanced_config from proxy_host where id=?',(host_id,)).fetchone()
if not row:raise SystemExit(f'proxy_host_missing:{host_id}')
advanced=(row[0] or '').replace('\r','').strip()
pattern=re.compile(re.escape(begin)+r'.*?'+re.escape(end),re.S)
advanced=pattern.sub(block,advanced) if pattern.search(advanced) else (advanced+'\n\n'+block).strip()
c.execute("update proxy_host set advanced_config=?, modified_on=datetime('now') where id=?",(advanced,host_id))
c.commit();c.close()
PY
}

patch_generated_conf() {
  local conf="$1" marker="$2" anchor="$3"
  python3 - "$conf" "$PORTAL_ORIGIN" "$marker" "$anchor" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);portal,marker,anchor=sys.argv[2:5];s=p.read_text()
begin=f'# CloudIF {marker} Portal Embed BEGIN';end=f'# CloudIF {marker} Portal Embed END'
block=f'''  {begin}
  more_clear_headers 'X-Frame-Options';
  more_set_headers "Content-Security-Policy: frame-ancestors 'self' {portal}";
  more_set_headers -t 'text/html' 'Cache-Control: no-store';
  {end}'''
pattern=re.compile(r'\s*'+re.escape(begin)+r'.*?'+re.escape(end)+r'\s*',re.S)
if pattern.search(s):s=pattern.sub('\n'+block+'\n',s,count=1)
else:
    if anchor not in s:raise SystemExit(f'proxy_anchor_missing:{p.name}')
    s=s.replace(anchor,anchor+'\n'+block+'\n',1)
p.write_text(s)
PY
}

patch_db_host "$KOMODO_HOST_ID" 'Komodo'
patch_db_host "$AUTH_HOST_ID" 'Authentik'
patch_generated_conf "$KOMODO_CONF" 'Komodo' $'client_max_body_size 200m;\n'
patch_generated_conf "$AUTH_CONF" 'Authentik' 'include conf.d/include/proxy.conf;'

rollback() {
  cp -a "$BACKUP_DIR/database.sqlite" "$DB"
  cp -a "$BACKUP_DIR/$KOMODO_HOST_ID.conf" "$KOMODO_CONF"
  cp -a "$BACKUP_DIR/$AUTH_HOST_ID.conf" "$AUTH_CONF"
  docker exec "$CONTAINER" nginx -t >/dev/null 2>&1 || true
  docker exec "$CONTAINER" nginx -s reload >/dev/null 2>&1 || true
}
trap 'rc=$?; if [ "$rc" -ne 0 ]; then rollback; fi; exit "$rc"' EXIT

docker exec "$CONTAINER" nginx -t
docker exec "$CONTAINER" nginx -s reload
sleep 1

verify_host() {
  local domain="$1" conf="$2" marker="$3" host_id="$4"
  grep -q "more_clear_headers 'X-Frame-Options';" "$conf"
  grep -Fq "frame-ancestors 'self' $PORTAL_ORIGIN" "$conf"
  grep -Fq 'Cache-Control: no-store' "$conf"
  python3 - "$DB" "$host_id" "$PORTAL_ORIGIN" "$marker" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);row=c.execute('select advanced_config from proxy_host where id=?',(int(sys.argv[2]),)).fetchone();c.close()
s=(row[0] or '') if row else '';marker=sys.argv[4]
assert f'# CloudIF {marker} Portal Embed BEGIN' in s
assert "more_clear_headers 'X-Frame-Options';" in s
assert f"frame-ancestors 'self' {sys.argv[3]}" in s
assert 'Cache-Control: no-store' in s
PY
  local headers
  headers=$(mktemp)
  curl -fsSI --max-time 15 "https://$domain/" >"$headers"
  if grep -qi '^x-frame-options:' "$headers"; then echo "${marker,,}_x_frame_options_still_present" >&2; rm -f "$headers"; return 1; fi
  grep -Fqi "content-security-policy: frame-ancestors 'self' $PORTAL_ORIGIN" "$headers" || { echo "${marker,,}_frame_ancestors_missing" >&2; rm -f "$headers"; return 1; }
  grep -Fqi 'cache-control: no-store' "$headers" || { echo "${marker,,}_html_no_store_missing" >&2; rm -f "$headers"; return 1; }
  rm -f "$headers"
}

verify_host "$KOMODO_DOMAIN" "$KOMODO_CONF" 'Komodo' "$KOMODO_HOST_ID"
verify_host "$AUTH_DOMAIN" "$AUTH_CONF" 'Authentik' "$AUTH_HOST_ID"

trap - EXIT
printf 'configured|komodo=%s|auth=%s|frame_ancestor=%s|backup=%s\n' "$KOMODO_DOMAIN" "$AUTH_DOMAIN" "$PORTAL_ORIGIN" "$BACKUP_DIR"
