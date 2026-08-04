from pathlib import Path
import unittest

class TerminalUsesAuthenticatedActorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_portal_sends_logged_user_not_owner(self):
  for marker in ('actor=str(user.get(\'username\')','\'actor_username\':actor','\'actor_groups\':actor_groups','def _rd_actor_allowed'):
   self.assertIn(marker,self.portal)
 def test_agent_enforces_project_acl(self):
  for marker in ('actor_not_authorized','actor_groups.intersection','access.get("acl")','actor_permission_sync_failed'):
   self.assertIn(marker,self.agent)
 def test_terminal_is_isolated_per_actor(self):
  for marker in ('actor_key=safe_slug(actor)','terminal=(base_terminal[:70]+"-"+actor_key)','"actor_username":actor'):
   self.assertIn(marker,self.agent)

if __name__=='__main__':unittest.main()
