#!/usr/bin/env bash
set -Eeuo pipefail
CONF="${1:-/srv/cloudif/router/conf.d/default.conf}"
BEGIN='# CloudIF academic project access v1 BEGIN'
END='# CloudIF academic project access v1 END'
test -f "$CONF" || { echo "missing config: $CONF" >&2; exit 2; }
BACKUP="$CONF.bkp-academic-access-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$CONF" "$BACKUP"
python3 - "$CONF" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
begin='# CloudIF academic project access v1 BEGIN';end='# CloudIF academic project access v1 END'
s=re.sub(re.escape(begin)+r'.*?'+re.escape(end)+r'\n?','',s,flags=re.S)
block='''# CloudIF academic project access v1 BEGIN
log_format cloudif_project_access escape=json '{"ts":"$time_iso8601","msec":"$msec","tenant":"$cloudif_effective_tenant","user":"$authentik_username","method":"$request_method","uri":"$uri","status":$status}';
map $request_method $cloudif_project_write_log {
    default 0;
    POST 1;
    PUT 1;
    PATCH 1;
    DELETE 1;
}
# CloudIF academic project access v1 END

'''
idx=s.find('server {')
if idx<0:raise SystemExit('server anchor missing')
s=s[:idx]+block+s[idx:]
lines=s.splitlines()
def inject(header,access_line):
    start=next((i for i,line in enumerate(lines) if line.strip()==header),None)
    if start is None:raise SystemExit('location missing: '+header)
    depth=0;end_i=None
    for i in range(start,len(lines)):
        # These target blocks have balanced inline if braces, so line counts are safe.
        depth+=lines[i].count('{')-lines[i].count('}')
        if i>start and depth==0:
            end_i=i;break
    if end_i is None:raise SystemExit('location unterminated: '+header)
    block_lines=lines[start:end_i+1]
    if any('cloudif_project_access.log' in x for x in block_lines):return
    marker=next((j for j in range(start,end_i) if 'auth_request_set $authentik_username ' in lines[j]),None)
    if marker is None:raise SystemExit('auth username marker missing: '+header)
    lines.insert(marker+1,'        '+access_line)
inject('location ^~ /project/ {','access_log /var/log/nginx/cloudif_project_access.log cloudif_project_access;')
inject('location ^~ /api/ {','access_log /var/log/nginx/cloudif_project_access.log cloudif_project_access if=$cloudif_project_write_log;')
p.write_text('\n'.join(lines)+'\n')
PY
if docker ps --format '{{.Names}}' | grep -qx cloudif-tenant-router; then
  if ! docker exec cloudif-tenant-router nginx -t; then
    cp -a "$BACKUP" "$CONF"
    docker exec cloudif-tenant-router nginx -t || true
    exit 3
  fi
  docker exec cloudif-tenant-router nginx -s reload
fi
echo 'OK: CloudIF academic project access logging active.'
