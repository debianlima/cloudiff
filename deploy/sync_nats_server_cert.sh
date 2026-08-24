#!/usr/bin/env bash
set -euo pipefail
ORIGIN=${CLOUDIFF_DISTRIBUTION_ORIGIN:-https://cloudiff.duckdns.org/__cloudif_distribution}
CONNECT_IP=${CLOUDIFF_DISTRIBUTION_CONNECT_IP:-10.62.91.3}
AUDIENCE=${CLOUDIFF_DISTRIBUTION_AUDIENCE:?CLOUDIFF_DISTRIBUTION_AUDIENCE required}
TOKEN_FILE=${CLOUDIFF_DISTRIBUTION_TOKEN_FILE:-/etc/cloudiff-v2/secure-distribution-nats.token}
COLLECTION=${CLOUDIFF_DISTRIBUTION_COLLECTION:-nats-server-cert}
DEST=${CLOUDIFF_NATS_CERT_DEST:-/var/lib/cloudiff-v2/tls/server}
BACKUP_ROOT=${CLOUDIFF_NATS_CERT_BACKUP_ROOT:-/var/lib/cloudiff-v2/backups/nats-cert}
EXPECTED=${CLOUDIFF_NATS_TLS_EXPECTED_HOSTNAME:-nats.cloudiff.duckdns.org}
MIN_SECONDS=${CLOUDIFF_NATS_CERT_MIN_SECONDS:-1209600}
[ -s "$TOKEN_FILE" ]
case "$ORIGIN" in https://cloudiff.duckdns.org/*) ;; *) echo invalid_distribution_origin >&2; exit 2;; esac
[[ "$CONNECT_IP" =~ ^[0-9a-fA-F:.]+$ ]] || { echo invalid_connect_ip >&2; exit 2; }
[[ "$AUDIENCE" =~ ^[A-Za-z0-9._:-]{1,128}$ ]] || { echo invalid_audience >&2; exit 2; }
[[ "$COLLECTION" =~ ^[a-z0-9][a-z0-9._-]{0,63}$ ]] || { echo invalid_collection >&2; exit 2; }
install -d -m 0700 "$DEST" "$BACKUP_ROOT"
tmp=$(mktemp -d "$DEST/.https-sync.XXXXXX");trap 'rm -rf "$tmp"' EXIT
umask 077
{ printf 'Authorization: Bearer '; tr -d '\r\n' < "$TOKEN_FILE"; printf '\nX-CloudIFF-Audience: %s\n' "$AUDIENCE"; } > "$tmp/headers"
chmod 0600 "$tmp/headers"
CURL=(curl --fail-with-body --silent --show-error --max-time 30 --proto '=https' --tlsv1.2 --resolve "cloudiff.duckdns.org:443:$CONNECT_IP" --header "@$tmp/headers")
"${CURL[@]}" "$ORIGIN/v1/collections/$COLLECTION/manifest" -o "$tmp/manifest.json"
python3 - "$tmp/manifest.json" "$COLLECTION" "$AUDIENCE" "$tmp/meta" <<'PY'
import json,re,sys
src,collection,audience,out=sys.argv[1:]
x=json.load(open(src));assert x.get('ok') is True;assert x.get('collection')==collection;assert x.get('audience')==audience
g=x.get('generation','');assert re.fullmatch(r'[a-f0-9]{64}',g)
rows={m['id']:m for m in x.get('members',[]) if isinstance(m,dict)}
assert set(rows)=={'fullchain.pem','privkey.pem'}
with open(out,'w') as f:
 f.write('generation='+g+'\n')
 for name in ('fullchain.pem','privkey.pem'):
  m=rows[name];sha=m.get('sha256','');size=m.get('size')
  assert re.fullmatch(r'[a-f0-9]{64}',sha) and isinstance(size,int) and 0<size<=65536
  key=name.replace('.','_');f.write(key+'_sha='+sha+'\n');f.write(key+'_size='+str(size)+'\n')
PY
# meta contains only digests/sizes and is safe to source.
. "$tmp/meta"
for name in fullchain.pem privkey.pem; do
  eval expected_sha="\${${name//./_}_sha}"
  eval expected_size="\${${name//./_}_size}"
  "${CURL[@]}" -H "X-CloudIFF-Expected-Generation: $generation" "$ORIGIN/v1/collections/$COLLECTION/objects/$name" -o "$tmp/$name"
  [ "$(wc -c < "$tmp/$name")" = "$expected_size" ]
  [ "$(sha256sum "$tmp/$name" | awk '{print $1}')" = "$expected_sha" ]
done
openssl x509 -in "$tmp/fullchain.pem" -noout >/dev/null
openssl pkey -in "$tmp/privkey.pem" -noout >/dev/null
openssl x509 -in "$tmp/fullchain.pem" -noout -checkhost "$EXPECTED" >/dev/null
openssl x509 -in "$tmp/fullchain.pem" -noout -checkend "$MIN_SECONDS" >/dev/null
cert_pub=$(openssl x509 -in "$tmp/fullchain.pem" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
key_pub=$(openssl pkey -in "$tmp/privkey.pem" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
[ "$cert_pub" = "$key_pub" ] || { echo certificate_private_key_mismatch >&2; exit 3; }
new_fp=$(openssl x509 -in "$tmp/fullchain.pem" -noout -fingerprint -sha256 | cut -d= -f2)
old_fp='';if [ -s "$DEST/fullchain.pem" ]; then old_fp=$(openssl x509 -in "$DEST/fullchain.pem" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 || true);fi
if [ "$new_fp" = "$old_fp" ]; then echo "certificate_unchanged generation=$generation fingerprint=$new_fp";exit 0;fi
ts=$(date -u +%Y%m%dT%H%M%SZ);backup="$BACKUP_ROOT/$ts";install -d -m 0700 "$backup"
[ ! -s "$DEST/fullchain.pem" ] || cp -p "$DEST/fullchain.pem" "$backup/fullchain.pem"
[ ! -s "$DEST/privkey.pem" ] || cp -p "$DEST/privkey.pem" "$backup/privkey.pem"
install -m 0644 -o root -g root "$tmp/fullchain.pem" "$DEST/fullchain.pem.new"
install -m 0600 -o root -g root "$tmp/privkey.pem" "$DEST/privkey.pem.new"
mv -f "$DEST/fullchain.pem.new" "$DEST/fullchain.pem"
mv -f "$DEST/privkey.pem.new" "$DEST/privkey.pem"
echo "certificate_updated generation=$generation fingerprint=$new_fp"
if docker ps --format '{{.Names}}' | grep -qx cloudiff-v2-nats; then docker kill --signal HUP cloudiff-v2-nats >/dev/null || docker restart cloudiff-v2-nats >/dev/null;fi
