from pathlib import Path
import unittest

class BackupRoleVisibilityPolicyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.ui=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_professor_has_all_project_backups(self):
  self.assertIn('def _pb_is_platform_admin(user):',self.base)
  self.assertIn('def _pb_is_professor(user):',self.base)
  self.assertIn('def _pb_all_projects(user):',self.base)
  self.assertIn("if not (_pb_is_platform_admin(user) or _pb_is_professor(user))",self.base)
  self.assertIn('for project in getattr(owner, "_pb_all_projects")(user):',self.ui)
 def test_platform_and_global_database_inventory_are_admin_only(self):
  self.assertIn('if is_admin:',self.ui)
  self.assertIn('payload["platform"]',self.ui)
  self.assertIn('payload["tenants"]',self.ui)
  self.assertIn("${d.platform?`",self.ui)
  self.assertIn("${d.tenants?`",self.ui)
 def test_project_backup_contains_application_and_database_types(self):
  self.assertIn("x.type==='database'?'Banco de dados':'Aplicação e containers'",self.ui)
  self.assertIn('aplicação e banco vinculado',self.ui)
 def test_download_backend_revalidates_project_access(self):
  self.assertIn("if not _pb_project(user,slug)",self.base)
  self.assertIn('project_access = bool(getattr(owner,"_pb_project")(user,slug))',self.ui)
 def test_platform_download_remains_admin_only(self):
  self.assertIn("if not _pb_is_platform_admin(user)",self.base)
  self.assertIn('_pb_is_platform_admin',self.ui)

if __name__=='__main__':unittest.main()
