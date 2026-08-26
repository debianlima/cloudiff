#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
schema_path = root / 'contratos/portal-shadow.schema.json'
contract_path = root / 'config/faro-portal-shadow-contract.json'
verifier_path = root / 'scripts/verify_faro_portal_shadow.sh'
profile_path = root / 'config/faro-node-profile.json'

for path in (schema_path, contract_path, verifier_path, profile_path):
    assert path.is_file(), path

schema = json.loads(schema_path.read_text())
contract = json.loads(contract_path.read_text())
profile = json.loads(profile_path.read_text())
verifier = verifier_path.read_text()

# Schema-level fail-closed semantics are intentional and regression-protected.
props = schema['properties']
assert props['contract_version']['const'] == 1
assert props['node']['const'] == 'faro'
assert props['mode']['const'] == 'portal-shadow'
assert props['probe']['properties']['method']['const'] == 'GET'
assert props['probe']['properties']['path']['const'] == '/'
assert props['probe']['properties']['read_only']['const'] is True
safety_schema = props['safety']['properties']
assert safety_schema['automatic_migration']['const'] is False
assert safety_schema['cutover_authorized']['const'] is False
assert safety_schema['contract_only_may_approve_live']['const'] is False

assert contract['contract_version'] == 1
assert contract['node'] == 'faro'
assert contract['mode'] == 'portal-shadow'
assert contract['contract_state'] == 'HOMOLOGADO_CI'
assert contract['live_state'] == 'NAO_VERIFICADO'
assert contract['probe'] == {'method': 'GET', 'path': '/', 'read_only': True}
assert contract['endpoint_sources'] == {
    'authoritative': 'CLOUDIFF_PORTAL_AUTHORITATIVE_URL',
    'shadow': 'CLOUDIFF_PORTAL_SHADOW_URL',
}

safety = contract['safety']
assert safety == {
    'parallel_only': True,
    'dedicated_non_authoritative_endpoint': True,
    'authoritative_untouched': True,
    'automatic_migration': False,
    'cutover_authorized': False,
    'contract_only_may_approve_live': False,
}

expected_evidence = {
    'frozen_surfaces': 'portal/FROZEN_SURFACES.md',
    'real_page_proof': 'docs/portal-v2/REAL-PAGE-PROOF.json',
    'quality_baseline': 'config/portal-quality-baseline.json',
    'faro_profile': 'config/faro-node-profile.json',
}
assert contract['evidence'] == expected_evidence
for rel in expected_evidence.values():
    assert (root / rel).is_file(), rel

required_live = {
    'endpoint-separation',
    'authoritative-before-after-unchanged',
    'shadow-readonly-root-probe',
    'frozen-surface-equivalence',
    'backend-navigation-and-actions',
    'telemetry-observed',
    'no-route-dns-lb-takeover',
    'explicit-cutover-authorization',
}
assert required_live == set(contract['live_gates'])

assert profile['hostname'] == 'faro'
assert 'portal-host' in profile['capabilities']
assert profile['portal']['desired_host'] is True
assert profile['portal']['cutover'] == 'after-faro-onboarding-and-portal-shadow-gates'

# The verifier may observe with GET/curl, but it must not perform operational
# mutation or sneak a cutover into the shadow validation path.
for forbidden in (
    'systemctl restart',
    'systemctl stop',
    'systemctl disable',
    'service cloudiff',
    'docker restart',
    'docker stop',
    'docker rm',
    'docker compose down',
    'pkill ',
    'killall ',
    'iptables ',
    'nft ',
    'nmcli ',
    'ip route add',
    'ip route del',
    'resolvectl ',
    'cloudflare',
):
    assert forbidden not in verifier, forbidden

assert 'curl --fail-with-body --silent --show-error --location' in verifier
assert 'PORTAL_SHADOW_CONTRACT=PASS LIVE=NAO_VERIFICADO CUTOVER=false' in verifier
assert 'PORTAL_SHADOW_PRECHECK=PASS' in verifier
assert 'LIVE=NAO_VERIFICADO CUTOVER=false' in verifier
assert 'endpoint-not-separated' in verifier

result = subprocess.run(
    ['bash', str(verifier_path), '--contract-only'],
    cwd=root,
    text=True,
    capture_output=True,
    check=True,
)
assert result.stdout.strip() == 'PORTAL_SHADOW_CONTRACT=PASS LIVE=NAO_VERIFICADO CUTOVER=false', result.stdout
assert 'LIVE=APROVADO' not in result.stdout

print('FARO_PORTAL_SHADOW_CONTRACT=PASS contract=ci-only live=NAO_VERIFICADO cutover=false probe=GET:/ safety=fail-closed')
