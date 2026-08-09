#!/usr/bin/env bash
set -euo pipefail

BASE=/srv/cloudif/proxy/npm
DB="$BASE/data/database.sqlite"
CONF_DIR="$BASE/data/nginx/proxy_host"
CONTAINER=cloudif-nginx-proxy-manager
DOMAIN=komodoiff.duckdns.org
PORTAL_ORIGIN=https://cloudiff.duckdns.org
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="$BASE/backups/komodo-embed-$STAMP"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

[ -f "$DB" ] || { echo 'npm_database_missing' >&2; exit 2; }
cp -a "$DB" "$BACKUP_DIR/database.sqlite"
chmod 600 "$BACKUP_DIR/database.sqlite"

HOST_ID=$(python3 - "$DB" "$DOMAIN" <<'PY'
import json,sqlite3,sys
p,domain=sys.argv[1:3]
c=sqlite3.connect(p);c.row_factory=sqlite3.Row
rows=[]
for r in c.execute('select id,domain_names from proxy_host where enabled=1 and is_deleted=0'):
    try:names=json.loads(r['domain_names'] or '[]')
    except Exception:names=[]
    if domain in names:rows.append(r)
if len(rows)!=1:raise SystemExit('komodo_proxy_host_not_unique')
print(rows[0]['id']);c.close()
PY
)
HOST_CONF="$CONF_DIR/$HOST_ID.conf"
[ -f "$HOST_CONF" ] || { echo 'npm_generated_host_config_missing' >&2; exit 3; }
cp -a "$HOST_CONF" "$BACKUP_DIR/$HOST_ID.conf"

python3 - "$DB" "$HOST_ID" "$PORTAL_ORIGIN" <<'PY'
import re,sqlite3,sys
p,host_id,portal=sys.argv[1],int(sys.argv[2]),sys.argv[3]
begin='# CloudIF Komodo Portal Embed BEGIN';end='# CloudIF Komodo Portal Embed END'
block=f'''# CloudIF Komodo Portal Embed BEGIN
more_clear_headers 'X-Frame-Options';
more_set_headers "Content-Security-Policy: frame-ancestors 'self' {portal}";
# CloudIF Komodo Portal Embed END'''
c=sqlite3.connect(p)
row=c.execute('select advanced_config from proxy_host where id=?',(host_id,)).fetchone()
if not row:raise SystemExit('komodo_proxy_host_missing')
advanced=(row[0] or '').replace('\r','').strip()
pattern=re.compile(re.escape(begin)+r'.*?'+re.escape(end),re.S)
advanced=pattern.sub(block,advanced) if pattern.search(advanced) else (advanced+'\n\n'+block).strip()
c.execute("update proxy_host set advanced_config=?, modified_on=datetime('now') where id=?",(advanced,host_id))
c.commit();c.close()
PY

python3 - "$HOST_CONF" "$PORTAL_ORIGIN" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);portal=sys.argv[2];s=p.read_text()
begin='# CloudIF Komodo Portal Embed BEGIN';end='# CloudIF Komodo Portal Embed END'
block=f'''  # CloudIF Komodo Portal Embed BEGIN
  more_clear_headers 'X-Frame-Options';
  more_set_headers "Content-Security-Policy: frame-ancestors 'self' {portal}";
  # CloudIF Komodo Portal Embed END'''
pattern=re.compile(r'\s*'+re.escape(begin)+r'.*?'+re.escape(end)+r'\s*',re.S)
if pattern.search(s):s=pattern.sub('\n'+block+'\n',s,count=1)
else:
    anchor='client_max_body_size 200m;\n'
    if anchor not in s:raise SystemExit('komodo_proxy_anchor_missing')
    s=s.replace(anchor,anchor+'\n'+block+'\n',1)
p.write_text(s)
PY

rollback(){
  cp -a "$BACKUP_DIR/database.sqlite" "$DB"
  cp -a "$BACKUP_DIR/$HOST_ID.conf" "$HOST_CONF"
  docker exec "$CONTAINER" nginx -t >/dev/null 2>&1 || true
  docker exec "$CONTAINER" nginx -s reload >/dev/null 2>&1 || true
}
trap 'rc=$?; if [ "$rc" -ne 0 ]; then rollback; fi; exit "$rc"' EXIT

docker exec "$CONTAINER" nginx -t
docker exec "$CONTAINER" nginx -s reload
sleep 1

grep -q "more_clear_headers 'X-Frame-Options';" "$HOST_CONF"
grep -Fq "frame-ancestors 'self' $PORTAL_ORIGIN" "$HOST_CONF"
python3 - "$DB" "$HOST_ID" "$PORTAL_ORIGIN" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);row=c.execute('select advanced_config from proxy_host where id=?',(int(sys.argv[2]),)).fetchone();c.close()
s=(row[0] or '') if row else ''
assert '# CloudIF Komodo Portal Embed BEGIN' in s
assert "more_clear_headers 'X-Frame-Options';" in s
assert f"frame-ancestors 'self' {sys.argv[3]}" in s
PY

headers=$(mktemp)
curl -fsSI --max-time 15 "https://$DOMAIN/" >"$headers"
if grep -qi '^x-frame-options:' "$headers"; then echo 'komodo_x_frame_options_still_present' >&2; exit 4; fi
grep -Fqi "content-security-policy: frame-ancestors 'self' $PORTAL_ORIGIN" "$headers" || { echo 'komodo_frame_ancestors_missing' >&2; exit 5; }
rm -f "$headers"
trap - EXIT
printf 'configured|domain=%s|proxy_host_id=%s|frame_ancestor=%s|backup=%s\n' "$DOMAIN" "$HOST_ID" "$PORTAL_ORIGIN" "$BACKUP_DIR"
