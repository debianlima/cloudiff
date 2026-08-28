import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/cpp-live-binary-provenance-v61.json'
R58=ROOT/'docs/reconciliation/runtime-executor-whp-parity-v58.json'
R60=ROOT/'docs/reconciliation/artifact-executor-cpp-authority-v60.json'
R57=ROOT/'docs/reconciliation/npm-publisher-runtime-parity-v57.json'
MAIN=ROOT/'src/agent/main.cpp'

class CppLiveBinaryProvenanceEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text())
  cls.r58=json.loads(R58.read_text())
  cls.r60=json.loads(R60.read_text())
  cls.r57=json.loads(R57.read_text())
  cls.main=MAIN.read_text()

 def test_all_four_runtime_identities_are_cryptographically_pinned(self):
  expected={
   'npm_publisher_0_10':('d75a583ec66e0431236b56070878a01a5f733d24c1375c3b159971a4fedf695b','0a8d7c52217de4757a18d4c020f558723e92ee20'),
   'runtime_planner_0_17':('917fe9cba09321ba0e6f408ca3c8903cd0d131bd1af7b09a2e883735628f4c6e','0c60cb0c62e2750b309f57a76831471100f79f81'),
   'runtime_canary_0_24':('4ebaaadf69df5074a4e6088b36b73c0279f9ef3c69d4626ff980048e11a3688b','582b2ad9954f09001c2aa108051656b7d86ab38e'),
   'artifact_engine_0_27':('46e409246c9bf8feef34e36c5261a3c2cf07e1e9ec35f760af63102a9e19ea4d','f3935c5b120602b3f7fec11e45348ad170c32f08')}
  self.assertEqual(set(self.e['targets']),set(expected))
  for k,(sha,bid) in expected.items():
   x=self.e['targets'][k]
   self.assertEqual(x['sha256'],sha); self.assertEqual(x['gnu_build_id'],bid)
   self.assertTrue(x['release_path'].startswith('/opt/cloudiff-v2/releases/'))
   self.assertEqual(x['compiler_comment']['clang'],'Ubuntu clang version 21.1.8 (6ubuntu1)')

 def test_exact_source_commit_remains_undeclared_for_every_old_binary(self):
  for x in self.e['targets'].values():
   self.assertEqual(x['exact_source_commit'],'NAO DECLARADO')
   self.assertFalse(x['source_commit_proven'])
   self.assertFalse(x['release_directory_contains_source_manifest'])
  h=self.e['git_history']
  self.assertEqual(h['earliest_cpp_source_commit'],'2e869b7a5216a33bfb88875b97d710392d325ed0')
  self.assertTrue(h['earliest_cpp_source_postdates_all_target_installs'])
  self.assertEqual(h['artifact_v27_post_build_reference']['classification'],'post_build_reference_not_build_provenance')

 def test_previous_audits_and_current_source_are_consistent(self):
  self.assertEqual(self.r58['runtime_executor']['planner']['binary_sha256'],self.e['targets']['runtime_planner_0_17']['sha256'])
  self.assertEqual(self.r58['runtime_executor']['canary']['binary_sha256'],self.e['targets']['runtime_canary_0_24']['sha256'])
  self.assertEqual(self.r60['artifact_cpp']['binary_sha256'],self.e['targets']['artifact_engine_0_27']['sha256'])
  self.assertEqual(self.r57['runtime']['live']['binary_sha256'],self.e['targets']['npm_publisher_0_10']['sha256'])
  self.assertIn('cloudiff-agent 0.36.0-shadow',self.main)
  self.assertFalse(self.e['conclusions']['current_repo_source_can_be_claimed_as_source_of_old_live_binaries'])

 def test_future_release_provenance_gate_is_explicit(self):
  req=set(self.e['future_release_provenance_gate']['required_fields'])
  self.assertTrue({'source_commit','source_tree','binary_sha256','gnu_build_id','compiler','build_command_digest','built_at'}.issubset(req))
  self.assertEqual(self.e['future_release_provenance_gate']['manifest_name'],'release-manifest.json')
  self.assertTrue(self.e['conclusions']['old_live_binaries_are_runtime_identified'])
  self.assertFalse(self.e['conclusions']['old_live_binaries_are_source_commit_attributed'])

if __name__=='__main__': unittest.main()
