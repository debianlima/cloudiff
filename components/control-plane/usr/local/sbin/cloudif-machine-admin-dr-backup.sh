#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/machine-admin-dr
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
WORK=$(mktemp -d /var/tmp/cloudif-machine-admin-dr.XXXXXX)
STAGE=$WORK/rootfs
ARCHIVE=$BASE/cloudif-machine-admin-dr-$STAMP.tar.zst
MANIFEST=$BASE/cloudif-machine-admin-dr-$STAMP.manifest.json
cleanup(){ rm -rf "$WORK"; }
trap cleanup EXIT
install -d -m 0700 "$BASE" "$STAGE"
copy_path(){
  src=$1
  [ -e "$src" ] || return 0
  dst=$STAGE$src
  install -d -m 0700 "$(dirname "$dst")"
  cp -a --preserve=all "$src" "$dst"
}
# Administrative control plane and PKI only. No tenant directories or portal DB.
for p in \
  /var/lib/cloudif-agent-pki \
  /etc/cloudif/machine-controller-db.env \
  /etc/cloudif/machine-admin-security.env \
  /etc/cloudif/machine-policy-signing.key \
  /etc/cloudif/machine-policy-signing.pub \
  /etc/cloudif/certificate-alerting.env \
  /etc/cloudif/certificate-monitoring.json \
  /etc/cloudif/machine-agent.env \
  /etc/cloudif/machine-agent \
  /usr/local/sbin/cloudif-machine-controller.py \
  /usr/local/sbin/cloudif-machine-harvester.py \
  /usr/local/sbin/cloudif-machine-guardian.py \
  /usr/local/sbin/cloudif-machine-executor.py \
  /usr/local/sbin/cloudif-agent-pki.py \
  /usr/local/sbin/cloudif-machine-admin-db-backup.sh \
  /usr/local/sbin/cloudif-controller-certificate-renew.sh \
  /usr/local/sbin/cloudif-healthcheck.sh \
  /usr/local/sbin/cloudif-certificate-alert-dispatcher.py \
  /srv/cloudif/lib \
  /srv/cloudif/router/conf.d/default.conf \
  /srv/cloudif/router/docker-compose.yml \
  /srv/cloudif/router/mtls \
  /srv/cloudif/machine-admin/docker-compose.yml \
  /srv/cloudif/documentacao \
  /etc/rsyslog.d/50-cloudif-certificate-alerts.conf \
  /etc/logrotate.d/cloudif-certificate-alerts; do
  copy_path "$p"
done
for p in /etc/systemd/system/cloudif-machine-* /etc/systemd/system/cloudif-agent-pki-* /etc/systemd/system/cloudif-controller-certificate-* /etc/systemd/system/cloudif-certificate-alert-* /etc/systemd/system/cloudif-healthcheck.*; do
  [ -e "$p" ] && copy_path "$p"
done
# Remote agent private keys are not needed for DR and are excluded from the package.
rm -f "$STAGE/var/lib/cloudif-agent-pki/issued/forja.key" "$STAGE/var/lib/cloudif-agent-pki/issued/mauricio.key"
rm -rf "$STAGE/var/lib/cloudif-agent-pki/issued/server-backups"
# Inventory of included paths and integrity manifest. Values from env files are never printed.
(cd "$STAGE" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$WORK/SHA256SUMS.txt"
(cd "$STAGE" && find . -printf '%P|%y|%m|%u:%g|%s\n' | sort) > "$WORK/FILELIST.txt"
latest_db=$(find /srv/cloudif/managed-backups/machine-admin-postgres -maxdepth 4 -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
latest_db_sha=''
[ -n "$latest_db" ] && [ -f "$latest_db.sha256" ] && latest_db_sha=$(awk '{print $1}' "$latest_db.sha256")
python3 - "$MANIFEST" "$STAMP" "$latest_db" "$latest_db_sha" "$WORK/FILELIST.txt" <<'PY'
import json,sys,datetime as dt
out,stamp,db,dbsha,filelist=sys.argv[1:]
count=sum(1 for _ in open(filelist,errors='ignore'))
data={'schema':1,'created_at':dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'archive_stamp':stamp,'scope':'machine-admin-control-plane-and-pki','excludes':['portal database','tenant directories','user data'],'file_entries':count,'latest_postgres_backup':db,'latest_postgres_sha256':dbsha}
open(out,'w').write(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
PY
install -m 0600 "$WORK/SHA256SUMS.txt" "$STAGE/SHA256SUMS.txt"
install -m 0600 "$WORK/FILELIST.txt" "$STAGE/FILELIST.txt"
tar --numeric-owner --acls --xattrs -C "$STAGE" -I 'zstd -T0 -9' -cf "$ARCHIVE" .
chmod 0600 "$ARCHIVE" "$MANIFEST"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
chmod 0600 "$ARCHIVE.sha256"
# Daily retention 30 days; retain first backup of each month for 400 days.
MONTHLY=$BASE/monthly
install -d -m 0700 "$MONTHLY"
if [ "$(date -u +%d)" -le 7 ]; then
  cp -a "$ARCHIVE" "$ARCHIVE.sha256" "$MANIFEST" "$MONTHLY/"
fi
find "$BASE" -maxdepth 1 -type f \( -name '*.tar.zst' -o -name '*.sha256' -o -name '*.manifest.json' \) -mtime +30 -delete
find "$MONTHLY" -maxdepth 1 -type f -mtime +400 -delete
printf '%s archive=%s size=%s files=%s\n' "$(date -Is)" "$ARCHIVE" "$(stat -c %s "$ARCHIVE")" "$(wc -l < "$WORK/FILELIST.txt")"
