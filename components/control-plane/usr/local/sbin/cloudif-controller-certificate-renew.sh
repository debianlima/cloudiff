#!/usr/bin/env bash
set -euo pipefail
set -a
. /etc/cloudif/machine-controller-db.env
set +a
export PYTHONPATH=/srv/cloudif/lib
FORCE=0; [ "${1:-}" = --force ] && FORCE=1
PKI=/var/lib/cloudif-agent-pki
ROUTER=/srv/cloudif/router/mtls
CERT=$PKI/issued/controller-server.pem
CHAIN=$PKI/issued/controller-server-chain.pem
KEY=$PKI/issued/controller-server.key
LOCK=/run/cloudif-controller-certificate-renew.lock
exec 9>"$LOCK"; flock -n 9 || { echo renewal_already_running; exit 0; }
if [ "$FORCE" -eq 0 ] && openssl x509 -checkend $((45*86400)) -noout -in "$CERT" >/dev/null 2>&1; then echo renewal=not_due; exit 0; fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ); WORK=$(mktemp -d /root/cloudif-controller-cert-renew.XXXXXX)
cleanup(){ rm -rf "$WORK"; }; trap cleanup EXIT
OLD_SERIAL=$(openssl x509 -in "$CERT" -noout -serial | cut -d= -f2)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$WORK/server.key" >/dev/null 2>&1
chmod 0600 "$WORK/server.key"
openssl req -new -sha256 -key "$WORK/server.key" -out "$WORK/server.csr" -subj '/O=IFF CloudIF/OU=Machine Administration/CN=cloudif-machine-controller'
cat >"$WORK/server.ext" <<'EOF'
[ server_cert ]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName = DNS:cloudif-machine-controller,DNS:hospedagem,IP:10.62.92.7
EOF
openssl ca -batch -config "$PKI/issuing/openssl.cnf" -extensions server_cert -extfile "$WORK/server.ext" -in "$WORK/server.csr" -out "$WORK/server.pem" >/dev/null 2>&1
cat "$WORK/server.pem" "$PKI/issuing/certs/issuing-ca.pem" > "$WORK/server-chain.pem"
chmod 0644 "$WORK/server.pem" "$WORK/server-chain.pem"
openssl verify -purpose sslserver -CAfile "$PKI/issuing/certs/ca-chain.pem" "$WORK/server.pem"
NEW_SERIAL=$(openssl x509 -in "$WORK/server.pem" -noout -serial | cut -d= -f2)
BACK=$PKI/issued/server-backups/$STAMP; install -d -m 0700 "$BACK"
cp -a "$CERT" "$CHAIN" "$KEY" "$BACK/"
cp -a "$ROUTER/controller-server-chain.pem" "$ROUTER/controller-server.key" "$BACK/router-" 2>/dev/null || true
install -m 0600 "$WORK/server.key" "$KEY.new"
install -m 0644 "$WORK/server.pem" "$CERT.new"
install -m 0644 "$WORK/server-chain.pem" "$CHAIN.new"
install -m 0600 "$WORK/server.key" "$ROUTER/controller-server.key.new"
install -m 0644 "$WORK/server-chain.pem" "$ROUTER/controller-server-chain.pem.new"
mv "$KEY.new" "$KEY"; mv "$CERT.new" "$CERT"; mv "$CHAIN.new" "$CHAIN"
mv "$ROUTER/controller-server.key.new" "$ROUTER/controller-server.key"; mv "$ROUTER/controller-server-chain.pem.new" "$ROUTER/controller-server-chain.pem"
if ! docker exec cloudif-tenant-router nginx -t; then
 cp -a "$BACK/controller-server.key" "$KEY"; cp -a "$BACK/controller-server.pem" "$CERT"; cp -a "$BACK/controller-server-chain.pem" "$CHAIN"
 install -m 0600 "$KEY" "$ROUTER/controller-server.key"; install -m 0644 "$CHAIN" "$ROUTER/controller-server-chain.pem"
 exit 1
fi
docker exec cloudif-tenant-router nginx -s reload
sleep 3
curl -sS --max-time 15 --cacert "$PKI/issuing/certs/ca-chain.pem" --cert "$PKI/issued/hospedagem.pem" --key "$PKI/issued/hospedagem.key" https://10.62.92.7:18111/health | grep -q '"ok"'
/usr/local/sbin/cloudif-agent-pki.py revoke-serial --serial "$OLD_SERIAL" --machine-id controller --hostname hospedagem --actor system:controller-cert-renew --reason superseded >/dev/null
logger -t cloudif-controller-cert-renew "old_serial=$OLD_SERIAL new_serial=$NEW_SERIAL status=completed"
echo "renewal=completed old_serial=$OLD_SERIAL new_serial=$NEW_SERIAL backup=$BACK"
