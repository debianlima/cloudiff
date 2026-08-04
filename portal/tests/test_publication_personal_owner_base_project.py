from pathlib import Path
import unittest

class PublicationPersonalOwnerBaseProjectTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_healthy_local_base_survives_stale_komodo_status(self):
  for marker in ('local_base = _cloudif_v132_local_web_health','status["local_reconciled"] = True','base_project_not_found'):
   self.assertIn(marker,self.source)
 def test_stack_lookup_is_owner_independent(self):
  self.assertIn('expected_repo_suffix = "/cloudif-" + project',self.source)
  self.assertNotIn('expected_repo = f"cloudif/{project}"',self.source)

if __name__=='__main__':unittest.main()
