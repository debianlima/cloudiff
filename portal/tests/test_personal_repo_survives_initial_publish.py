from pathlib import Path
import unittest
class PersonalRepoSurvivesInitialPublishTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.initial=Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text()
  cls.onboarding=Path('components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()
  cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
 def test_initial_publish_uses_confirmed_integration_url(self):
  self.assertIn('def canonical_repo_url',self.initial)
  self.assertIn('select forgejo_repo_url,repo_url from project_integrations',self.initial)
  self.assertNotIn("git/cloudif/cloudif-{slug}",self.initial)
 def test_onboarding_uses_actual_owner(self):
  self.assertIn("'forgejo_owner':owner",self.onboarding)
  self.assertNotIn("'forgejo_owner':'cloudif'",self.onboarding)
 def test_repair_route_preserves_personal_owner(self):
  self.assertIn('select owner,repo_url from projects',self.portal)
  self.assertIn("'forgejo_owner':_rd_project_access(slug).get('owner')",self.portal)
  self.assertNotIn("return name,'https://cloudiff.duckdns.org/git/cloudif/'+name",self.portal)
if __name__=='__main__':unittest.main()
