from pathlib import Path
import unittest

class BackupProgressModalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_modal_is_present(self):
  for marker in ('backup-progress-layer','backup-progress-modal','backup-progress-steps','backup-progress-result'):
   self.assertIn(marker,self.source)
 def test_project_backup_uses_progress_flow(self):
  self.assertIn('async function runProjectBackup(button)',self.source)
  self.assertIn("if(b.dataset.op==='backup_now')return runProjectBackup(b)",self.source)
  self.assertIn('button.disabled=true',self.source)
 def test_progress_tracks_real_inventory(self):
  self.assertIn('async function projectState(slug)',self.source)
  self.assertIn("latest.filename!==before",self.source)
  self.assertIn("await request('/cloudiff/portal/api/backup-overview'",self.source)
 def test_user_gets_success_or_error_feedback(self):
  self.assertIn("progressTitle.textContent='Backup concluído'",self.source)
  self.assertIn("progressTitle.textContent='Não foi possível concluir'",self.source)
  self.assertIn('progressClose.hidden=false',self.source)
 def test_backend_acceptance_precedes_confirmation(self):
  accepted=self.source.index("await action(slug,'backup_now')")
  confirmed=self.source.index("setProgress(0,18,'Solicitação enviada'")
  self.assertLess(accepted,confirmed)

if __name__=='__main__': unittest.main()
