import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/mcp-upload-cpp-authority-v62.json'
CONTRACT=ROOT/'contratos/mcp-upload.schema.json'
CPP=ROOT/'src/agent/mcp_upload.cpp'
MAIN=ROOT/'src/agent/main.cpp'
UNIT=ROOT/'deploy/systemd/cloudiff-v2-mcp-upload-shadow.service'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'

class McpUploadCppAuthorityEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text())
  cls.contract=json.loads(CONTRACT.read_text())
  cls.cpp=CPP.read_text(); cls.main=MAIN.read_text(); cls.unit=UNIT.read_text(); cls.gateway=GATEWAY.read_text()

 def test_cpp_contract_is_shadow_plan_only_and_side_effect_free(self):
  shadow=self.contract['properties']['shadow']['properties']
  self.assertEqual(shadow['bind']['const'],'127.0.0.1')
  self.assertEqual(shadow['port']['const'],18234)
  self.assertEqual(shadow['routes']['const'],['GET /health','POST /v1/plan'])
  sec=self.contract['properties']['security']['properties']
  for k in ('sideEffectFree','externalNetwork','workspaceMutation','secretsExposed'):
   self.assertIn('const',sec[k])
  self.assertTrue(sec['sideEffectFree']['const'])
  self.assertFalse(sec['externalNetwork']['const']); self.assertFalse(sec['workspaceMutation']['const']); self.assertFalse(sec['secretsExposed']['const'])
  self.assertIn('shadow-plan-only',self.cpp)
  self.assertIn('filesystem_access_attempted",false',self.cpp)
  self.assertIn('external_network_attempted",false',self.cpp)

 def test_gateway_exposes_upload_tools_but_has_no_cpp_planner_wiring(self):
  for tool in ('workspace.artifact.import','workspace.artifact.upload.file','workspace.artifact.upload.file.select','workspace.artifact.upload.file.resolve','workspace.artifact.upload.start'):
   self.assertIn(tool,self.gateway)
  self.assertNotIn('CLOUDIFF_MCP_UPLOAD',self.gateway)
  self.assertNotIn('18234',self.gateway)
  self.assertIn('host_file_param_not_hydrated',self.gateway)
  self.assertIn('workspace.artifact.upload.start',self.gateway)
  self.assertIn('workspace_artifact_import_https',self.gateway)
  self.assertIn('workspace_artifact_upload_existing_https',self.gateway)

 def test_live_shadow_probe_is_safe_and_does_not_leak_local_path(self):
  e=self.e
  self.assertEqual(e['schema_version'],1)
  self.assertEqual(e['host']['ip'],'10.62.92.7')
  p=e['cpp_planner']
  self.assertTrue(p['service_active']); self.assertEqual(p['binary_version'],'0.20.0-shadow')
  self.assertEqual(p['bind'],'127.0.0.1:18234'); self.assertEqual(p['health_mode'],'shadow-plan-only')
  probe=e['safe_probe']
  self.assertEqual(probe['bad_auth_status'],401); self.assertEqual(probe['valid_plan_status'],200)
  self.assertTrue(probe['side_effect_free']); self.assertFalse(probe['filesystem_access_attempted']); self.assertFalse(probe['external_network_attempted']); self.assertFalse(probe['workspace_mutation'])
  self.assertEqual(probe['effective_tool'],'workspace.artifact.upload.start')
  self.assertFalse(probe['raw_path_leaked'])

 def test_authority_and_provenance_are_not_overclaimed(self):
  e=self.e
  g=e['python_gateway']
  self.assertTrue(g['service_active']); self.assertEqual(g['planner_reference_count'],0)
  self.assertEqual(g['tool_count'],152)
  self.assertTrue(all(g['upload_tools_present'].values()))
  self.assertEqual(g['live_sha256'],'f332023a009c80e831eadfebb1ef11b36084f36ed0bd4ce5255cead9bef86df8')
  self.assertTrue(g['source_lineage']['lineage_proven_by_repo_scripts_and_tests'])
  self.assertEqual(g['source_lineage']['repo_base_sha256'],'948e071ab08e45cd6a0683375669217aaaa76af5b8cc07bbd0092a7e1e71c846')
  self.assertFalse(e['conclusions']['cpp_planner_is_consumed_by_live_gateway'])
  self.assertFalse(e['conclusions']['mcp_upload_effect_migrated_to_cpp'])
  self.assertTrue(e['conclusions']['python_gateway_authoritative'])
  self.assertEqual(e['source_snapshot']['live_exact_source_commit'],'NAO DECLARADO')
  self.assertFalse(e['source_snapshot']['release_manifest_present'])
  self.assertEqual(e['source_snapshot']['repo_agent_version'],'0.36.0-shadow')
  self.assertFalse(e['source_snapshot']['current_repo_binary_is_live'])

if __name__=='__main__': unittest.main()
