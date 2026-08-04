from pathlib import Path
import unittest

class ProjectDeleteCleansDerivedKomodoResourcesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.portal=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
 def test_portal_sends_public_number_to_destroy(self):
  self.assertIn("'public_number':int(public_number or 0)",self.portal)
  self.assertIn("_destroy_runtime(slug, plan.get('tenant_preserved') or '', public_number)",self.portal)
 def test_delete_scans_terminals_stacks_builds_images_and_paths(self):
  for marker in ('def _cloudif_delete_related_resources','ListTerminals','DeleteTerminal','ListBuilds','DeleteBuild','DestroyStack','DeleteStack','docker\',\'image\',\'rm','/srv/cloudif/publications'):
   self.assertIn(marker,self.agent)
 def test_user_terminal_prefix_is_removed(self):
  self.assertIn("terminal_prefix=base_name+'-'",self.agent)
  self.assertIn("name.startswith(terminal_prefix)",self.agent)
 def test_tenant_stack_is_preserved(self):
  self.assertIn("'tenant_stack_preserved':'cloudif-tenant-'",self.agent)
  self.assertNotIn("DeleteStack',{'id':tenant",self.agent)
 def test_destroy_requires_derived_cleanup_success(self):
  self.assertIn("repo_final_ok and derived_cleanup.get('ok')",self.agent)
  self.assertIn('"derived_cleanup": derived_cleanup',self.agent)

if __name__=='__main__':unittest.main()
