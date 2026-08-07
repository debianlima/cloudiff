from pathlib import Path
import unittest

class KomodoUnifiedLayoutEnsureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
        cls.worker=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
    def test_runtime_layout_is_only_used_by_stack_helper(self):
        repo=self.source[self.source.index('def create_or_update_repo'):self.source.index('def create_or_update_stack')]
        stack=self.source[self.source.index('def create_or_update_stack'):self.source.index('def ensure_project')]
        self.assertNotIn('runtime_layout',repo)
        self.assertIn('compose_file = ".cloudif/docker-compose.yml" if runtime_layout == "unified-v1"',stack)
        self.assertIn('"file_paths": [compose_file]',stack)
    def test_ensure_passes_layout_to_stack(self):
        self.assertIn('create_or_update_stack(project, repo_info, server_id, str(payload.get("runtime_layout") or "legacy"))',self.source)
    def test_worker_surfaces_component_failure(self):
        self.assertIn("provision-report.json",self.worker)
        self.assertIn("failures.append(name + ': ' +",self.worker)

if __name__=='__main__': unittest.main()
