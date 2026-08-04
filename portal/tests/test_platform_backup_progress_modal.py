from pathlib import Path
import unittest

class PlatformBackupProgressModalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_modal_context_is_dynamic(self):
  self.assertIn('backup-progress-kind',self.source)
  self.assertIn('progressKind.textContent=kind',self.source)
 def test_platform_uses_progress_modal(self):
  self.assertIn('async function runPlatformBackup(button)',self.source)
  self.assertIn("showProgress('Configuração central da CloudIFF','BACKUP DA PLATAFORMA')",self.source)
  self.assertIn("if(pb)pb.onclick=()=>runPlatformBackup(pb)",self.source)
 def test_platform_tracks_new_inventory_file(self):
  self.assertIn('async function platformState()',self.source)
  self.assertIn('Backup da plataforma criado com sucesso',self.source)
  self.assertIn('latest.filename!==before',self.source)
 def test_async_backups_do_not_reload_before_polling(self):
  self.assertIn("if(!['backup_now','platform_backup'].includes(op))await load()",self.source)
 def test_project_modal_context_is_preserved(self):
  self.assertIn("showProgress(slug,'BACKUP DO PROJETO')",self.source)

if __name__=='__main__': unittest.main()
