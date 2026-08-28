import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/reconciliation/runtime-executor-whp-parity-v58.json'
CONTRACT=ROOT/'contratos/runtime-executor.schema.json'
CPP=ROOT/'src/agent/runtime_executor.cpp'
MAIN=ROOT/'src/agent/main.cpp'
CANARY_UNIT=ROOT/'deploy/systemd/cloudiff-v2-runtime-executor-canary.service'
H=ROOT/'components/runtime/current-apps/production-homologation-executor-current/cloudif-production-homologation-executor.py'
C=ROOT/'components/runtime/current-apps/production-canary-executor-current/cloudif-production-canary-executor.py'
P=ROOT/'components/runtime/current-apps/production-public-executor-current/cloudif-production-public-executor.py'

class RuntimeExecutorWhpParityEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(EVIDENCE.read_text())
  cls.contract=json.loads(CONTRACT.read_text())
  cls.cpp=CPP.read_text(); cls.main=MAIN.read_text(); cls.unit=CANARY_UNIT.read_text()
  cls.legacy={"HOMOLOGATION":H.read_text(),"CANARY":C.read_text(),"PRODUCTION":P.read_text()}

 def test_contract_limits_effect_canary_to_test_preview(self):
  canary=self.contract['properties']['canary']['properties']
  self.assertEqual(canary['profiles']['const'],['TEST','PREVIEW'])
  self.assertTrue(canary['effectsEnabled']['const'])
  self.assertIn('TEST/PREVIEW canary (manual)',self.unit)
  self.assertIn('*profile!=RuntimeProfile::TEST&&*profile!=RuntimeProfile::PREVIEW',self.cpp)

 def test_whp_policies_exist_but_effect_paths_remain_legacy(self):
  profiles=self.contract['properties']['profiles']['properties']
  for name in ('HOMOLOGATION','CANARY','PRODUCTION'):
   self.assertIn(name,profiles)
   src=self.legacy[name]
   for route in ("'/v1/deploy'","'/v1/rollback'","'/v1/status'"):
    self.assertIn(route,src,name)
  self.assertTrue(profiles['PRODUCTION']['const']['externalHealthMatch'])
  self.assertEqual(profiles['PRODUCTION']['const']['networkAlias'],'cloudif-production-active')
  self.assertIn('cloudif-production-active',self.cpp)

 def test_live_evidence_does_not_overclaim_cpp_whp_migration(self):
  e=self.e
  self.assertEqual(e['schema_version'],1)
  self.assertEqual(e['host']['ip'],'10.62.91.2')
  self.assertEqual(e['runtime_executor']['planner']['binary_version'],'0.17.0-shadow')
  self.assertEqual(e['runtime_executor']['canary']['binary_version'],'0.24.0-shadow')
  self.assertFalse(e['runtime_executor']['canary']['active'])
  self.assertEqual(e['source_snapshot']['repo_agent_version'],'0.36.0-shadow')
  self.assertFalse(e['conclusions']['current_repo_binary_is_live'])
  self.assertFalse(e['conclusions']['whp_effect_execution_cpp_migrated'])
  for name in ('HOMOLOGATION','PRODUCTION'):
   plan=e['observed_plans'][name]
   self.assertTrue(plan['ok']); self.assertTrue(plan['side_effect_free']); self.assertFalse(plan['effects_enabled'])
   execute=e['observed_execute'][name]
   self.assertEqual(execute['status'],409); self.assertEqual(execute['error'],'effects_not_enabled_v17')
  self.assertEqual(e['docker_inventory_hash_before'],e['docker_inventory_hash_after'])

 def test_legacy_whp_services_are_observed_active(self):
  services=self.e['legacy_effect_services']
  self.assertEqual(services['HOMOLOGATION']['port'],18217)
  self.assertEqual(services['CANARY']['port'],18219)
  self.assertEqual(services['PRODUCTION']['port'],18220)
  for x in services.values(): self.assertTrue(x['active']); self.assertEqual(x['health_status'],200)

if __name__=='__main__': unittest.main()
