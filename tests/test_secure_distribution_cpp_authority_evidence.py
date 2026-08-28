import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/secure-distribution-cpp-authority-v63.json'
CONTRACT=ROOT/'contratos/secure-distribution.schema.json'
CPP=ROOT/'src/agent/secure_distribution.cpp'
UNIT=ROOT/'deploy/systemd/cloudiff-v2-secure-distribution.service'
ROUTE=ROOT/'deploy/install_secure_distribution_route.sh'
SYNC=ROOT/'deploy/sync_nats_server_cert.sh'
SYNC_UNIT=ROOT/'deploy/systemd/cloudiff-v2-cert-sync.service'
CONFIG=ROOT/'config/secure-distribution-v1.json'

class SecureDistributionCppAuthorityEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text())
  cls.contract=json.loads(CONTRACT.read_text())
  cls.cpp=CPP.read_text(); cls.unit=UNIT.read_text(); cls.route=ROUTE.read_text(); cls.sync=SYNC.read_text(); cls.sync_unit=SYNC_UNIT.read_text(); cls.config=json.loads(CONFIG.read_text())

 def test_contract_and_source_enforce_capability_generation_and_get_only(self):
  r=self.contract['properties']['route']['properties']
  self.assertEqual(r['methods']['const'],['GET'])
  self.assertEqual(r['sourceAllow']['const'],['10.62.92.7'])
  self.assertEqual(r['otherHosts']['const'],'404')
  cap=self.contract['properties']['capability']['properties']
  self.assertEqual(cap['transport']['const'],'Authorization: Bearer')
  self.assertTrue(cap['expiryRequired']['const']); self.assertTrue(cap['collectionScopeRequired']['const']); self.assertFalse(cap['queryTokenAllowed']['const'])
  integ=self.contract['properties']['integrity']['properties']
  self.assertEqual(integ['memberDigest']['const'],'sha256')
  self.assertIn('X-CloudIFF-Expected-Generation',integ['objectPrecondition']['const'])
  self.assertIn('query_not_allowed',self.cpp); self.assertIn('expected_generation_required',self.cpp); self.assertIn('generation_changed',self.cpp)
  self.assertIn('CRYPTO_memcmp',self.cpp)

 def test_route_and_consumer_preserve_network_and_secret_boundaries(self):
  self.assertIn('allow 10.62.92.7;',self.route); self.assertIn('deny all;',self.route)
  self.assertIn('if ($request_method != GET) { return 405; }',self.route)
  self.assertIn('add_header Cache-Control "no-store" always;',self.route)
  self.assertIn('tr -d',self.sync); self.assertIn('X-CloudIFF-Audience',self.sync); self.assertIn('X-CloudIFF-Expected-Generation',self.sync)
  self.assertIn('openssl pkey -in "$tmp/privkey.pem" -noout',self.sync)
  self.assertIn('certificate_private_key_mismatch',self.sync)
  self.assertIn('ReadOnlyPaths=/etc/cloudiff-v2/secure-distribution-nats.token',self.sync_unit)
  self.assertIn('ProtectSystem=strict',self.unit)

 def test_live_provider_and_consumer_are_authoritative_for_this_collection(self):
  e=self.e
  self.assertEqual(e['schema_version'],1)
  p=e['provider']
  self.assertTrue(p['service_active']); self.assertEqual(p['binary_version'],'0.22.0-shadow'); self.assertEqual(p['bind'],'10.62.91.3:18240')
  self.assertEqual(p['health_status'],200); self.assertFalse(p['health_secrets_exposed'])
  c=e['capability']
  self.assertEqual(c['count'],1); self.assertEqual(c['collection'],'nats-server-cert'); self.assertFalse(c['expired']); self.assertEqual(c['file_mode'],'0600')
  route=e['network_route']; self.assertEqual(route['unauthorized_source_status'],403); self.assertTrue(route['source_allow_10_62_92_7'])
  cons=e['consumer']; self.assertTrue(cons['timer_active']); self.assertEqual(cons['last_sync_exit_status'],0); self.assertTrue(cons['last_sync_certificate_unchanged'])
  self.assertTrue(e['conclusions']['cpp_provider_authoritative_for_nats_server_cert'])
  self.assertTrue(e['conclusions']['cert_sync_consumer_authoritative_for_local_install'])

 def test_live_read_only_probe_validates_generation_without_private_key_fetch(self):
  p=self.e['safe_probe']
  self.assertEqual(p['bad_auth_status'],403); self.assertEqual(p['query_token_status'],400); self.assertEqual(p['no_generation_status'],428)
  self.assertEqual(p['manifest_status'],200); self.assertEqual(p['collection'],'nats-server-cert')
  self.assertEqual(sorted(p['member_ids']),['fullchain.pem','privkey.pem'])
  self.assertRegex(p['generation'],r'^[a-f0-9]{64}$')
  self.assertEqual(p['fullchain_generation'],p['generation'])
  self.assertEqual(p['fullchain_header_sha256'],p['fullchain_body_sha256'])
  self.assertEqual(p['fullchain_remote_fingerprint'],p['fullchain_local_fingerprint'])
  self.assertFalse(p['privkey_requested'])
  self.assertFalse(p['secrets_exposed_in_error_responses'])
  self.assertEqual(self.e['source_snapshot']['live_exact_source_commit'],'NAO DECLARADO')
  self.assertFalse(self.e['source_snapshot']['release_manifest_present'])
  self.assertFalse(self.e['source_snapshot']['current_repo_binary_is_live'])

if __name__=='__main__': unittest.main()
