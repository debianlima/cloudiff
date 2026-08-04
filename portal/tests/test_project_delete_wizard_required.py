from pathlib import Path
import unittest

class ProjectDeleteWizardRequiredTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.mod=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
  cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.legacy=Path('components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py').read_text()
 def test_wizard_issues_single_use_token(self):
  for marker in ('def issue_wizard_token','def consume_wizard_token','expires_at','wizard_token'):
   self.assertIn(marker,self.mod)
 def test_post_cannot_call_execute_directly(self):
  route=self.base[self.base.index('def _admin_project_delete_post'):self.base.index('Portal.do_GET=_admin_project_delete_get')]
  self.assertNotIn('_admin_project_delete.execute(',route)
  self.assertIn('_admin_project_delete.start_job(',route)
  self.assertIn('wizard_required',route)
 def test_legacy_delete_opens_wizard(self):
  self.assertIn('tab=admin-excluir-projeto&amp;slug=',self.legacy)
  self.assertNotIn('name="op" value="delete_git_komodo"',self.legacy)

if __name__=='__main__':unittest.main()
