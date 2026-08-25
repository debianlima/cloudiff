#!/usr/bin/env python3
from pathlib import Path
import json,re,uuid,jsonschema
root=Path(__file__).resolve().parents[1]
schema=json.load(open(root/'contratos/faro-node-preparation.schema.json'));jsonschema.Draft202012Validator.check_schema(schema)
x=json.load(open(root/'config/faro-node-reservation.json'));jsonschema.validate(x,schema)
assert x['version']==2;assert x['identity']['address']=='10.62.91.5';uuid.UUID(x['identity']['nodeId']);assert x['nats']['username']==x['identity']['nodeId'];assert x['identity']['formFactor']=='virtual-machine-kvm'
assert x['runtime']['criticalPath']==['faro','hospedagem'];assert x['runtime']['forjaInCriticalPath'] is False and x['runtime']['mauricioInCriticalPath'] is False
assert x['bootstrap']['initialChannel'].startswith('SSH') and x['bootstrap']['privateKeyGeneration']=='on Faro only after SSH access' and x['bootstrap']['bundleContainsSecrets'] is False
assert '10.62.91.5/32' in x['nats']['sourceAllowlist'];assert x['nats']['externalIngress'].startswith('systemd socket proxy');assert x['verification']['nodeOperational'] is True and x['verification']['sshAvailable'] is True;assert x['verification']['csrSigned'] is True and x['verification']['heartbeatE2E'] is True;assert x['verification']['natsPath']=='reachable';assert x['nats']['clientCertificate']['status']=='signed';assert x['resources']['gates']=={'vcpu':'gap-observed-2-required-4','ram':'pass','disk':'pass'}
prep=(root/'deploy/prepare_faro_control_plane.sh').read_text();fw=(root/'deploy/apply_nats_source_allowlist.sh').read_text();bundle=(root/'deploy/build_faro_bootstrap_bundle.sh').read_text();unit=(root/'deploy/systemd/cloudiff-v2-nats-source-allowlist.service').read_text()
assert 'cloudiff.v2.node.observed' in prep and 'subscribe: { deny: [\">\"] }' in prep and 'openssl rand -hex 32' in prep
assert 'systemd-socket-proxyd 127.0.0.1:14222' in (root/'deploy/systemd/cloudiff-v2-nats-source-allowlist.service').read_text();assert '10.62.91.5/32' in (root/'deploy/systemd/cloudiff-v2-nats-source-allowlist.socket').read_text();assert '10.62.92.7:14222:4222' not in (root/'deploy/compose.yaml').read_text()
assert 'After=docker.service network-online.target' in unit
assert 'Gerar chave privada e CSR no Faro' in bundle and 'Este bundle não contém senha NATS, chave privada nem certificado cliente' in bundle
assert 'install -m 0644 /var/lib/cloudiff-v2/tls/client-ca/ca-chain.pem' in bundle
# No literal runtime secrets/private keys in source.
for p in [root/'config/faro-node-reservation.json',root/'deploy/prepare_faro_control_plane.sh',root/'deploy/apply_nats_source_allowlist.sh',root/'deploy/build_faro_bootstrap_bundle.sh']:
    text=p.read_text()
    assert ('-----BEGIN ' + 'PRIVATE KEY-----') not in text
    assert not re.search(r'(?i)(password|secret)\s*[:=]\s*["\'][A-Za-z0-9+/=_-]{24,}["\']',text)
# Existing model pins address/bootstrap but leaves role/capabilities unresolved.
d=json.load(open(root/'config/faro-validation-01-discovery.json'));dec={v['name']:v for v in d['decisions']}
assert dec['network_address']['status']=='fixed' and dec['network_address']['allowed_values']==['10.62.91.5'];assert dec['role']['status']=='fixed' and dec['role']['allowed_values']==['edge'];assert dec['capabilities']['status']=='derived';assert set(dec['capabilities']['allowed_values'])=={'inventory','health','telemetry-host','agent-auto-update'};assert dec['form_factor']['status']=='fixed' and dec['form_factor']['allowed_values']==['virtual-machine-kvm']
a=json.load(open(root/'config/faro-validation-04-agent-heartbeat.json'));b={v['name']:v for v in a['decisions']}
assert b['bootstrap_method']['status']=='fixed' and b['bootstrap_method']['allowed_values'][0].startswith('SSH')
print('FARO_NODE_PREPARATION=PASS')
