#!/usr/bin/env bash
set -euo pipefail
BASE=/srv/cloudif/managed-backups/machine-admin-dr
LATEST=$(find "$BASE" -maxdepth 1 -type f -name '*.tar.zst' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
test -n "$LATEST"
sha256sum -c "$LATEST.sha256"
RESTORE=$(mktemp -d /var/tmp/cloudif-machine-admin-dr-restore.XXXXXX)
cleanup(){ rm -rf "$RESTORE"; }
trap cleanup EXIT
tar -I zstd -xf "$LATEST" -C "$RESTORE"
cd "$RESTORE"
sha256sum -c SHA256SUMS.txt >/tmp/cloudif-dr-internal-sha.log
INTERNAL_OK=$(grep -c ': OK$' /tmp/cloudif-dr-internal-sha.log)
PKI=./var/lib/cloudif-agent-pki
openssl verify -CAfile "$PKI/root/certs/root-ca.pem" "$PKI/issuing/certs/issuing-ca.pem"
openssl verify -purpose sslserver -CAfile "$PKI/issuing/certs/ca-chain.pem" "$PKI/issued/controller-server.pem"
openssl verify -purpose sslclient -crl_check_all -CAfile "$PKI/issuing/certs/ca-chain.pem" -CRLfile "$PKI/issuing/certs/ca-chain.crl.pem" "$PKI/issued/hospedagem.pem"
openssl verify -purpose sslclient -crl_check_all -CAfile "$PKI/issuing/certs/ca-chain.pem" -CRLfile "$PKI/issuing/certs/ca-chain.crl.pem" "$PKI/issuing/newcerts/1005.pem" "$PKI/issuing/newcerts/1007.pem"
set +e
openssl verify -purpose sslclient -crl_check_all -CAfile "$PKI/issuing/certs/ca-chain.pem" -CRLfile "$PKI/issuing/certs/ca-chain.crl.pem" "$PKI/issued/forja.pem" >/tmp/cloudif-dr-old-forja.log 2>&1; RF=$?
openssl verify -purpose sslclient -crl_check_all -CAfile "$PKI/issuing/certs/ca-chain.pem" -CRLfile "$PKI/issuing/certs/ca-chain.crl.pem" "$PKI/issued/mauricio.pem" >/tmp/cloudif-dr-old-mauricio.log 2>&1; RM=$?
set -e
test "$RF" -ne 0; test "$RM" -ne 0
grep -qi 'certificate revoked' /tmp/cloudif-dr-old-forja.log
grep -qi 'certificate revoked' /tmp/cloudif-dr-old-mauricio.log
test ! -e "$PKI/issued/forja.key"
test ! -e "$PKI/issued/mauricio.key"
test ! -e "$PKI/issued/server-backups"
python3 - <<'PY'
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
priv=open('./etc/cloudif/machine-policy-signing.key','rb').read()
pub=base64.b64decode(open('./etc/cloudif/machine-policy-signing.pub').read().strip())
assert Ed25519PrivateKey.from_private_bytes(priv).public_key().public_bytes_raw()==pub
print('policy_signing_keypair=valid')
PY
python3 -m py_compile \
 ./usr/local/sbin/cloudif-machine-controller.py \
 ./usr/local/sbin/cloudif-machine-harvester.py \
 ./usr/local/sbin/cloudif-machine-guardian.py \
 ./usr/local/sbin/cloudif-machine-executor.py \
 ./usr/local/sbin/cloudif-agent-pki.py \
 ./usr/local/sbin/cloudif-certificate-alert-dispatcher.py
for f in ./usr/local/sbin/*.sh; do bash -n "$f"; done
! find . -type f -name 'cloudif-portal.db' | grep -q .
! find . -path '*/tenants/*' | grep -q .
MANIFEST=${LATEST%.tar.zst}.manifest.json
python3 - "$LATEST" "$MANIFEST" "$INTERNAL_OK" <<'PY'
import json,sys,os,hashlib,datetime as dt
archive,manifest,internal=sys.argv[1:]
d=json.load(open(manifest))
assert d['scope']=='machine-admin-control-plane-and-pki'
assert set(['portal database','tenant directories','user data']) <= set(d['excludes'])
assert d['file_entries']>20 and d['latest_postgres_backup'] and d['latest_postgres_sha256']
sha=hashlib.sha256(open(archive,'rb').read()).hexdigest()
result={
 'validated_at':dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
 'archive':archive,
 'archive_sha256':sha,
 'archive_size':os.path.getsize(archive),
 'internal_checksums_ok':int(internal),
 'scope':d['scope'],
 'postgres_reference':d['latest_postgres_backup'],
 'postgres_sha256_present':bool(d['latest_postgres_sha256']),
 'pki_chain':'ok',
 'current_agent_certificates':'ok',
 'old_agent_certificates':'revoked',
 'remote_private_keys':'excluded',
 'policy_signing_keypair':'ok',
 'code_syntax':'ok',
 'excluded_user_data':'ok',
 'result':'success'
}
marker='/srv/cloudif/managed-backups/machine-admin-dr/LAST_RESTORE_VALIDATION.json'
open(marker,'w').write(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
os.chmod(marker,0o600)
print(json.dumps(result,ensure_ascii=False))
PY
