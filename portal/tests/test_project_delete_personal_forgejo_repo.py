from pathlib import Path
import unittest

class ProjectDeletePersonalForgejoRepoTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.portal=Path('components/control-plane/srv/cloudif/lib/cloudif_delete_git_komodo_action.py').read_text()
  cls.agent=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
 def test_portal_sends_canonical_repo_identity(self):
  for marker in ('def _project_repo_identity','forgejo_repo_url','"owner": identity.get("owner")','"repo_url": identity.get("repo_url")'):
   self.assertIn(marker,self.portal)
 def test_agent_honors_explicit_personal_owner(self):
  fn=self.agent[self.agent.index('def cloudif_v117_project_rollback'):self.agent.index('# CloudIF v118')]
  for marker in ('payload.get("owner")','payload.get("repo")','payload.get("repo_url")','owner_kind'):
   self.assertIn(marker,fn)
 def test_absent_repo_remains_idempotent(self):
  self.assertIn('if st == 404:',self.agent)
  self.assertIn('already_absent',self.agent)

if __name__=='__main__':unittest.main()
