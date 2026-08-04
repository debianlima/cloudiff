from pathlib import Path
import unittest

class SharedUserRelatedStacksTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.helper=Path('components/runtime/usr/local/sbin/cloudif-komodo-project-authz.py').read_text()
 def test_terminal_targets_stack_not_server_container(self):
  self.assertIn('target={"type":"Stack"',self.agent)
  self.assertIn('/stacks/{audit[\'resolved_stack_id\']}/service/',self.agent)
 def test_related_publication_and_tenant_stacks_are_discovered(self):
  for marker in ('def _cloudif_related_stack_ids','cloudif-p','cloudif-tenant-','Hospedagem-Supabase','files_on_host','/srv/cloudif/tenants/'):
   self.assertIn(marker,self.agent)
 def test_acl_applies_to_all_related_stacks(self):
  self.assertIn("stack_ids=[str(x).strip()",self.helper)
  self.assertIn("(p.stack_ids||[]).map",self.helper)
  self.assertNotIn("[{type:'Stack',id:p.stack_id}",self.helper)

if __name__=='__main__':unittest.main()
