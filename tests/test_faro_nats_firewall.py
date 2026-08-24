#!/usr/bin/env python3
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
x=json.load(open(root/'config/faro-node-reservation.json'))
script=(root/'deploy/apply_faro_nats_firewall.sh').read_text()
unit=(root/'deploy/systemd/cloudiff-v2-faro-nats-firewall.service').read_text()
socket=(root/'deploy/systemd/cloudiff-v2-nats-source-allowlist.socket').read_text()
assert x['identity']['address']=='10.62.91.5'
assert x['nats']['hostFirewall'].startswith('Hospedagem INPUT exact match 10.62.92.7:14222/TCP')
for src in x['nats']['sourceAllowlist']:
    assert src in socket
assert 'CHAIN=CLOUDIFF_V2_NATS_INPUT' in script;assert '/etc/cloudiff-v2/faro-node-reservation.json' in script
assert 'DEST=10.62.92.7' in script and 'PORT=14222' in script
assert 'iptables -I INPUT 1' in script
assert 'iptables -A "$CHAIN" -j DROP' in script
assert 'iptables -X "$CHAIN"' in script
assert 'cloudif-input-firewall.service' in unit
assert 'cloudiff-v2-nats-source-allowlist.socket' in unit
assert 'ExecStart=/usr/local/sbin/cloudiff-v2-faro-nats-firewall apply' in unit
assert 'ExecStop=/usr/local/sbin/cloudiff-v2-faro-nats-firewall rollback' in unit
print('FARO_NATS_FIREWALL_MODEL=PASS')
