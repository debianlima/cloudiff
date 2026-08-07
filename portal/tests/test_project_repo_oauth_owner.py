from pathlib import Path
import unittest
class ProjectRepoOauthOwnerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.onboarding=Path('components/control-plane/srv/cloudif/lib/cloudif_onboarding_v2.py').read_text()
  cls.pages=Path('components/control-plane/srv/cloudif/lib/cloudif_ui_pages.py').read_text()
 def test_wrapper_accepts_personal_owner(self):
  self.assertIn('/git/(?!user/)[^/',self.portal)
  self.assertNotIn('/git/cloudif/[^',self.portal)
 def test_onboarding_redirect_uses_owner(self):
  self.assertIn('repo_web = f"https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}"',self.onboarding)
  self.assertNotIn('%2Fgit%2Fcloudif%2F',self.onboarding)
 def test_ui_fallback_uses_project_owner(self):
  self.assertIn("p.get('owner')",self.pages)
  self.assertNotIn('git/cloudif/{repo}',self.pages)
if __name__=='__main__':unittest.main()
