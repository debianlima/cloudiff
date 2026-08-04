from pathlib import Path
import unittest
class RecreateOwnerAndInitialTerminalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.prov=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.authz=Path('components/runtime/usr/local/sbin/cloudif-komodo-project-authz.py').read_text()
 def test_provisioner_rejects_owner_mismatch(self):
  self.assertIn('forgejo_owner_mismatch',self.prov)
  self.assertIn('actual_owner != owner',self.prov)
 def test_komodo_reconciles_personal_origin(self):
  for m in ('def _cloudif_reconcile_local_repo_origin','repo_info[\'repo_path\']','local_repo_origin_reconcile_failed'):
   self.assertIn(m,self.agent)
 def test_initial_terminal_falls_back_to_container(self):
  self.assertIn('target_mode',self.agent)
  self.assertIn('"type":"Container"',self.agent)
  self.assertNotIn('stack_metadata_reconcile_failed","metadata":metadata',self.agent)
 def test_server_permission_is_specific_only(self):
  self.assertIn("type:'Server',id:p.server_id,level:'None'",self.authz)

if __name__=='__main__':unittest.main()
