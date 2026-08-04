from pathlib import Path
import unittest

class TerminalUsesActivePublicationStackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_active_version_is_resolved_from_network_alias(self):
  for marker in ('def _cloudif_active_publication_stack','-active-web','com.docker.compose.project','active_version_stack_not_found'):
   self.assertIn(marker,self.source)
 def test_terminal_audits_active_stack(self):
  for marker in ('active=_cloudif_active_publication_stack','audit_payload["stack_id"]','"active_publication":active'):
   self.assertIn(marker,self.source)

if __name__=='__main__':unittest.main()
