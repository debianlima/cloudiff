from pathlib import Path
import unittest
class TenantAlwaysOnFinalHandlerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
 def test_final_handler_intercepts_only_always_on(self):
  self.assertIn('def _tenant_always_on_final_post',self.source)
  self.assertIn("op not in ('always_on','always_on_start')",self.source)
  self.assertIn('return _tenant_always_on_final_prev_post(self)',self.source)
 def test_policy_is_exclusive_and_clears_temporary_window(self):
  self.assertIn('always_alive=1,keepalive_until=NULL,max_hours=24',self.source)
 def test_stopped_tenant_is_started(self):
  self.assertIn('if not tenant_is_running(tenant):',self.source)
  self.assertIn('docker compose --env-file .env up -d',self.source)
 def test_action_is_audited(self):
  self.assertIn("log_action(user['username'],'always_on'",self.source)
if __name__=='__main__':unittest.main()
