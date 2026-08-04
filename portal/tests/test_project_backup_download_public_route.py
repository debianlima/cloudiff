from pathlib import Path
import unittest
class ProjectBackupDownloadPublicRouteTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
 def test_public_cloudiff_route_is_handled(self):
  self.assertIn("'/cloudiff/portal/download/project-backup'",self.source)
 def test_download_is_attachment(self):
  self.assertIn("self.send_header('Content-Type','application/gzip')",self.source)
  self.assertIn("self.send_header('Content-Disposition','attachment; filename=",self.source)
 def test_file_is_validated_inside_project_root(self):
  self.assertIn("fn!=_pb_Path(fn).name",self.source)
  self.assertIn("managed-backups/projects",self.source)
if __name__=='__main__':unittest.main()
