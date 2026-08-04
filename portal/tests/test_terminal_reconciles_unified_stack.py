from pathlib import Path
import unittest

class TerminalReconcilesUnifiedStackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_unified_stack_metadata_is_reconciled_without_deploy(self):
  for marker in ('def _cloudif_reconcile_unified_stack_metadata','project_name\':\'cloudif','file_paths\':[\'.cloudif/docker-compose.yml\']','RefreshStackCache','ListStackServices'):
   self.assertIn(marker,self.source)
 def test_terminal_requires_successful_reconciliation(self):
  self.assertIn('stack_metadata_reconcile_failed',self.source)
  self.assertIn('CLOUDIF_PUBLIC_NUMBER={public_number}',self.source)
  self.assertIn('CLOUDIF_DEPLOY_NUMBER={deploy_number}',self.source)
  self.assertIn(r"^cloudif-p(\d+)-d(\d+)-web$",self.source)
  self.assertIn('_cloudif_reconcile_unified_stack_metadata(payload.get("project")',self.source)

if __name__=='__main__':unittest.main()
