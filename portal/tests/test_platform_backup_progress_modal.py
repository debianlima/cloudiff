from pathlib import Path
import unittest

class PlatformBackupProgressModalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_platform_button_uses_progress_runner(self):
  self.assertIn("if(pb)pb.onclick=()=>runPlatformBackup(pb)",self.source)
  self.assertNotIn("if(pb)pb.onclick=async()=>{pb.disabled=true;try{await action('', 'platform_backup')",self.source)
 def test_platform_runner_tracks_real_inventory(self):
  self.assertIn('async function platformState()',self.source)
  self.assertIn('async function runPlatformBackup(button)',self.source)
  self.assertIn("latest.filename!==before",self.source)
  self.assertIn("d.platform||{items:[]}",self.source)
 def test_modal_identifies_platform_backup(self):
  self.assertIn("'BACKUP DA PLATAFORMA'",self.source)
  self.assertIn('backup-progress-kind',self.source)
  self.assertIn('Configuração central da CloudIFF',self.source)
 def test_platform_feedback_is_specific(self):
  self.assertIn('Backup da plataforma criado com sucesso',self.source)
  self.assertIn('Falha inesperada no backup da plataforma',self.source)
 def test_duplicate_clicks_are_blocked(self):
  self.assertIn('async function runPlatformBackup(button){button.disabled=true',self.source)
  self.assertIn('finally{button.disabled=false}',self.source)

if __name__=='__main__': unittest.main()
