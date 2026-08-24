#!/usr/bin/env bash
set -euo pipefail
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CFG="$ROOT/config/faro-node-reservation.json"
STATE=/var/lib/cloudiff-v2/faro-node-reservation
OUT="$STATE/bootstrap"
AGENT=${CLOUDIFF_FARO_AGENT_BINARY:-/var/lib/cloudiff-v2/build-v27-release/cloudiff-agent}
[ -x "$AGENT" ]
install -d -m 0700 "$OUT"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
install -m 0755 "$AGENT" "$tmp/cloudiff-agent"
install -m 0644 "$ROOT/deploy/systemd/cloudiff-v2-agent.service" "$tmp/cloudiff-v2-agent.service"
install -m 0644 /var/lib/cloudiff-v2/tls/client-ca/ca-chain.pem "$tmp/nats-client-ca-chain.pem"
python3 - "$CFG" "$tmp" <<'PY'
import json,sys
from pathlib import Path
x=json.load(open(sys.argv[1]));d=Path(sys.argv[2]);nid=x['identity']['nodeId']
(d/'node-id').write_text(nid+'\n')
lines=[
 'CLOUDIFF_NODE_ID_FILE=/etc/cloudiff-v2/node-id',
 'CLOUDIFF_NATS_URL=nats://10.62.92.7:14222',
 'CLOUDIFF_NATS_USER='+nid,
 'CLOUDIFF_NATS_PASSWORD=<install-from-root-only-reservation>',
 'CLOUDIFF_NATS_TLS_ENABLED=1',
 'CLOUDIFF_NATS_TLS_CA=/etc/cloudiff-v2/tls/ca-chain.pem',
 'CLOUDIFF_NATS_TLS_CERT=/etc/cloudiff-v2/tls/client-chain.pem',
 'CLOUDIFF_NATS_TLS_KEY=/etc/cloudiff-v2/tls/client.key',
 'CLOUDIFF_NATS_TLS_EXPECTED_HOSTNAME=nats.cloudiff.duckdns.org',
 'CLOUDIFF_NODE_ROLE=<resolve-after-discovery>'
]
(d/'agent.env.template').write_text('\n'.join(lines)+'\n')
(d/'BOOTSTRAP.txt').write_text('Faro 10.62.91.5; SSH autorizado quando fornecido. Gerar chave privada e CSR no Faro. Este bundle não contém senha NATS, chave privada nem certificado cliente.\n')
PY
chmod 0644 "$tmp/node-id" "$tmp/agent.env.template" "$tmp/BOOTSTRAP.txt"
(cd "$tmp" && sha256sum cloudiff-agent cloudiff-v2-agent.service nats-client-ca-chain.pem node-id agent.env.template BOOTSTRAP.txt > SHA256SUMS)
tar -C "$tmp" -czf "$OUT/cloudiff-faro-bootstrap.tar.gz" .
chmod 0600 "$OUT/cloudiff-faro-bootstrap.tar.gz"
sha256sum "$OUT/cloudiff-faro-bootstrap.tar.gz" > "$OUT/cloudiff-faro-bootstrap.tar.gz.sha256"
chmod 0600 "$OUT/cloudiff-faro-bootstrap.tar.gz.sha256"
echo FARO_BOOTSTRAP_BUNDLE=PASS
