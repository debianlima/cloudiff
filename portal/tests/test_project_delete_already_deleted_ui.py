from pathlib import Path
import unittest

class ProjectDeleteAlreadyDeletedUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
 def test_preview_reports_already_deleted(self):
  for marker in ("'already_deleted':True",'Projeto já excluído; resíduos verificados.','Tenant preservado'):
   self.assertIn(marker,self.source)
 def test_already_deleted_has_no_new_wizard_token_or_form(self):
  self.assertIn("not selected_preview.get('already_deleted')",self.source)
 def test_stale_not_found_job_is_presented_as_success(self):
  self.assertIn("state.get('error')=='project_not_found'",self.source)
  self.assertIn("'status':'succeeded'",self.source)

if __name__=='__main__':unittest.main()
