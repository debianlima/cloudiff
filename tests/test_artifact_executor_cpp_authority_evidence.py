import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/reconciliation/artifact-executor-cpp-authority-v60.json'
CONTRACT=ROOT/'contratos/artifact-executor.schema.json'
WORKER_CONTRACT=ROOT/'contratos/build-worker.schema.json'
INGRESS=ROOT/'config/classic-artifact-ingress.json'
ENGINE=ROOT/'src/agent/artifact_engine.cpp'
WORKER=ROOT/'src/worker/main.cpp'
GENERIC_UNIT=ROOT/'deploy/systemd/cloudiff-v2-worker.service'
CANARY_UNIT=ROOT/'deploy/systemd/cloudiff-v2-build-worker-canary.service'
LEGACY=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py'

class ArtifactExecutorCppAuthorityEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(EVIDENCE.read_text())
  cls.contract=json.loads(CONTRACT.read_text())
  cls.worker_contract=json.loads(WORKER_CONTRACT.read_text())
  cls.ingress=json.loads(INGRESS.read_text())
  cls.engine=ENGINE.read_text(); cls.worker=WORKER.read_text()
  cls.generic=GENERIC_UNIT.read_text(); cls.canary=CANARY_UNIT.read_text(); cls.legacy=LEGACY.read_text()

 def test_contract_preserves_legacy_and_scopes_cpp_ingress(self):
  legacy=self.contract['properties']['legacy']['properties']
  self.assertEqual(legacy['port']['const'],18216)
  self.assertEqual(legacy['service']['const'],'cloudif-artifact-executor.service')
  self.assertTrue(legacy['fallback_preserved']['const'])
  self.assertEqual(self.ingress['legacyContinuity']['authority'],'Python artifact executor remains unchanged')
  self.assertEqual(self.ingress['npm']['serverName'],'cloudif-artifact-executor-v2.internal')
  self.assertEqual(self.ingress['npm']['backend'],'http://10.62.91.2:18228')
  self.assertEqual(self.ingress['npm']['allowedRoute'],'POST /v1/build')
  self.assertEqual(self.ingress['socketProxy']['target'],'127.0.0.1:18226')

 def test_source_enforces_classic_token_scope_and_side_effect_free_validation(self):
  self.assertIn('constant_time_equal(authorization,expected)',self.engine)
  self.assertIn('classic_token_required',self.engine)
  self.assertIn('artifact_token_scope',self.engine)
  self.assertIn('sideEffectFree",true',self.engine)
  self.assertIn('"imagesCreated",0',self.engine)
  self.assertIn('"containersChanged",false',self.engine)

 def test_worker_activation_is_canary_not_general_authority(self):
  self.assertIn('cloudiff.v2.build.classic',self.worker)
  self.assertIn('CLOUDIFF_WORKER_ALLOWED_KINDS=cloudiff.v2.noop,cloudiff.v2.fail_once',self.generic)
  self.assertIn('CLOUDIFF_WORKER_ALLOWED_KINDS=cloudiff.v2.build.classic',self.canary)
  self.assertIn('Type=oneshot',self.canary)
  self.assertEqual(self.worker_contract['properties']['canary']['properties']['mode']['const'],'manual oneshot')
  self.assertEqual(self.worker_contract['properties']['canary']['properties']['externalAuthority']['const'],'Python BuildBroker remains authoritative in v16')

 def test_live_evidence_proves_partial_cpp_authority_without_overclaim(self):
  e=self.e
  self.assertEqual(e['schema_version'],1)
  self.assertEqual(e['forja']['ip'],'10.62.91.2')
  self.assertEqual(e['artifact_cpp']['binary_version'],'0.27.0-shadow')
  self.assertTrue(e['artifact_cpp']['service_active'])
  self.assertEqual(e['artifact_cpp']['bind'],'127.0.0.1:18226')
  self.assertTrue(e['legacy_python']['service_active'])
  self.assertEqual(e['legacy_python']['port'],18216)
  self.assertEqual(e['safe_validation']['status'],200)
  self.assertTrue(e['safe_validation']['side_effect_free'])
  self.assertTrue(e['safe_validation']['images_unchanged'])
  self.assertTrue(e['safe_validation']['containers_unchanged'])
  self.assertTrue(e['safe_validation']['persistent_results_unchanged'])
  self.assertEqual(e['dedicated_ingress']['get_health_status'],404)
  self.assertEqual(e['dedicated_ingress']['wrong_profile_status'],403)
  self.assertEqual(e['dedicated_ingress']['pre_effect_invalid_status'],400)
  self.assertEqual(e['classic_worker']['active_classic_jobs'],0)
  self.assertFalse(e['classic_worker']['canary_active'])
  self.assertFalse(e['conclusions']['artifact_cpp_general_authority'])
  self.assertFalse(e['conclusions']['classic_build_migrated_to_continuous_cpp_worker'])
  self.assertTrue(e['conclusions']['cpp_classic_canary_path_ready'])
  self.assertFalse(e['conclusions']['current_repo_binary_is_live'])

if __name__=='__main__': unittest.main()
