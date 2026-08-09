#!/usr/bin/env bash
set -euo pipefail

BASE=/srv/cloudif/proxy/npm
DB="$BASE/data/database.sqlite"
CONF_DIR="$BASE/data/nginx/proxy_host"
CONTAINER=cloudif-nginx-proxy-manager
DOMAIN=cloudiff.duckdns.org
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="$BASE/backups/artifact-upload-$STAMP"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

[ -f "$DB" ] || { echo 'npm_database_missing' >&2; exit 2; }
cp -a "$DB" "$BACKUP_DIR/database.sqlite"
chmod 600 "$BACKUP_DIR/database.sqlite"

readarray -t INFO < <(python3 - "$DB" "$DOMAIN" <<'PY'
import json,sqlite3,sys
p,domain=sys.argv[1:3]
c=sqlite3.connect(p);c.row_factory=sqlite3.Row
rows=[]
for r in c.execute('select id,domain_names,advanced_config from proxy_host where enabled=1 and is_deleted=0'):
    try:names=json.loads(r['domain_names'] or '[]')
    except Exception:names=[]
    if domain in names:rows.append(r)
if len(rows)!=1:raise SystemExit('main_proxy_host_not_unique')
r=rows[0]
print(r['id'])
print((r['advanced_config'] or '').replace('\r',''))
c.close()
PY
)
HOST_ID="${INFO[0]}"
HOST_CONF="$CONF_DIR/$HOST_ID.conf"
[ -f "$HOST_CONF" ] || { echo 'npm_generated_host_config_missing' >&2; exit 3; }
cp -a "$HOST_CONF" "$BACKUP_DIR/$HOST_ID.conf"

python3 - "$DB" "$HOST_ID" <<'PY'
import re,sqlite3,sys
p,host_id=sys.argv[1],int(sys.argv[2])
begin='# CloudIF artifact upload 1GiB BEGIN'
end='# CloudIF artifact upload 1GiB END'
block='''# CloudIF artifact upload 1GiB BEGIN
location = /cloudiff/portal/api/artifact-upload/content {
    client_max_body_size 1024m;
    client_body_timeout 7200s;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Host $host;
    proxy_request_buffering off;
    proxy_buffering off;
    proxy_connect_timeout 15s;
    proxy_read_timeout 7200s;
    proxy_send_timeout 7200s;
    proxy_pass http://10.62.92.7:8099;
}
# CloudIF artifact upload 1GiB END'''
c=sqlite3.connect(p)
row=c.execute('select advanced_config from proxy_host where id=?',(host_id,)).fetchone()
if not row:raise SystemExit('main_proxy_host_missing')
advanced=(row[0] or '').replace('\r','').strip()
pattern=re.compile(re.escape(begin)+r'.*?'+re.escape(end),re.S)
if pattern.search(advanced):advanced=pattern.sub(block,advanced)
else:advanced=(advanced+'\n\n'+block).strip()
c.execute("update proxy_host set advanced_config=?, modified_on=datetime('now') where id=?",(advanced,host_id))
c.commit();c.close()
PY

python3 - "$HOST_CONF" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
begin='# CloudIF artifact upload 1GiB BEGIN';end='# CloudIF artifact upload 1GiB END'
block='''  # CloudIF artifact upload 1GiB BEGIN
  location = /cloudiff/portal/api/artifact-upload/content {
    client_max_body_size 1024m;
    client_body_timeout 7200s;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Host $host;
    proxy_request_buffering off;
    proxy_buffering off;
    proxy_connect_timeout 15s;
    proxy_read_timeout 7200s;
    proxy_send_timeout 7200s;
    proxy_pass http://10.62.92.7:8099;
  }
  # CloudIF artifact upload 1GiB END'''
pattern=re.compile(r'\s*'+re.escape(begin)+r'.*?'+re.escape(end)+r'\s*',re.S)
if pattern.search(s):s=pattern.sub('\n'+block+'\n',s,count=1)
else:
    anchor='  # CloudIFF legacy prefix\n'
    if anchor not in s:raise SystemExit('main_proxy_anchor_missing')
    s=s.replace(anchor,block+'\n\n'+anchor,1)
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

grep -q 'location = /cloudiff/portal/api/artifact-upload/content' "$HOST_CONF"
grep -q 'client_max_body_size 1024m;' "$HOST_CONF"
python3 - "$DB" "$HOST_ID" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);row=c.execute('select advanced_config from proxy_host where id=?',(int(sys.argv[2]),)).fetchone();c.close()
s=(row[0] or '') if row else ''
assert '# CloudIF artifact upload 1GiB BEGIN' in s
assert 'client_max_body_size 1024m;' in s
assert 'proxy_request_buffering off;' in s
PY
trap - EXIT
printf 'configured|domain=%s|proxy_host_id=%s|limit=1024m|backup=%s\n' "$DOMAIN" "$HOST_ID" "$BACKUP_DIR"
