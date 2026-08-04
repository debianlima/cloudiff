from pathlib import Path
import unittest

class KomodoLocalHealthReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_health_uses_compose_labels_not_env_file(self):
        helper=self.source[self.source.index('def _cloudif_v132_local_web_health'):self.source.index('def cloudif_v132_project_deploy_full')]
        self.assertIn('com.docker.compose.project.config_files',helper)
        self.assertIn('com.docker.compose.service',helper)
        self.assertIn('expected_compose',helper)
        self.assertNotIn('CLOUDIF_PUBLIC_NUMBER',helper)
    def test_health_waits_for_healthy_container(self):
        self.assertIn('while time.time() < deadline',self.source)
        self.assertIn('running and health in ("healthy","")',self.source)
    def test_force_rebuild_does_not_run_second_deploy_stack(self):
        self.assertIn('if force_rebuild:\n        local_after_rebuild',self.source)
        self.assertIn('elif deploy:\n        deploy_stack',self.source)
    def test_local_health_is_final_source_of_truth(self):
        self.assertIn('"deploy_status":"completed"',self.source)
        self.assertIn('"local_reconciled":True',self.source)
        self.assertIn('local_web_health_failed',self.source)

if __name__=='__main__':unittest.main()
