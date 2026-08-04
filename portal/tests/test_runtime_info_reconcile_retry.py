from pathlib import Path
import unittest

class RuntimeInfoReconcileRetryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
 def test_runtime_info_retries_after_audit(self):
  for marker in ('def _rd_runtime_info_with_reconcile','/komodo/project/audit','audit.get(\'running\')','time.sleep(1)','resolved_stack_id'):
   self.assertIn(marker,self.source)
 def test_both_runtime_routes_use_retry_helper(self):
  self.assertGreaterEqual(self.source.count('_rd_runtime_info_with_reconcile('),3)

if __name__=='__main__':unittest.main()
