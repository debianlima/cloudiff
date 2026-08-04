from pathlib import Path
import unittest

class BackupConsoleJsonAndSectionsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_browser_uses_public_cloudiff_prefix(self):
  self.assertIn("request('/cloudiff/portal/action/project-backup'",self.source)
  self.assertNotIn("request('/cloudif/portal/action/project-backup'",self.source)
 def test_project_backup_route_returns_json(self):
  self.assertIn('parsed.path.endswith("/action/project-backup")',self.source)
  self.assertIn('return send_json(self,code,{"ok":True,"result":result})',self.source)
  self.assertIn("'/usr/local/sbin/cloudif-project-backup.py','backup','--slug',slug",self.source)
 def test_three_backup_sections_are_explicit(self):
  for title in ('Backup da plataforma','Backup dos projetos','Backup dos bancos e tenants'):
   self.assertIn(title,self.source)
  for number in ('>1</span>','>2</span>','>3</span>'):
   self.assertIn(number,self.source)
 def test_tenant_archives_are_in_inventory(self):
  self.assertIn('TENANT_BACKUP_ROOT',self.source)
  self.assertIn('def _tenant_backup_items()',self.source)
  self.assertIn('if len(parts)>2',self.source)
  self.assertIn('"tenants": {"items": _tenant_backup_items()',self.source)
 def test_project_download_uses_public_cloudiff_prefix(self):
  self.assertIn('/cloudiff/portal/download/project-backup',self.source)
  self.assertNotIn('/cloudif/portal/download/project-backup',self.source)
 def test_tenant_download_is_admin_protected(self):
  self.assertIn('/download/tenant-backup',self.source)
  self.assertIn("if not user.get(\"admin\")",self.source)
 def test_existing_controls_are_preserved(self):
  self.assertIn('data-op="backup_now"',self.source)
  self.assertIn('data-platform-backup',self.source)
  self.assertIn('set_auto',self.source)

if __name__=='__main__': unittest.main()
