from pathlib import Path
import unittest

class ProjectDeleteIdempotentCleanupTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.delete=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_missing_portal_record_runs_residue_cleanup(self):
  for marker in ('def _cleanup_already_deleted','already_deleted','Projeto já excluído; resíduos verificados','_destroy_runtime(slug,tenant)'):
   self.assertIn(marker,self.delete)
 def test_compose_labels_find_orphan_web_container(self):
  for marker in ('com.docker.compose.project.config_files','com.docker.compose.service','expected_root = str((Path("/etc/komodo/stacks")'):
   self.assertIn(marker,self.agent)
 def test_database_containers_remain_preserved(self):
  self.assertIn('if item.get("database")',self.agent)

if __name__=='__main__':unittest.main()
