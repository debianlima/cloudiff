from pathlib import Path
import unittest


class AdminDeleteCompleteResourceContractTest(unittest.TestCase):
    def test_agent_deletes_stack_and_repo_resources(self):
        source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn('komodo_call("write", "DeleteStack", {"id": stack_id})',source)
        self.assertIn('komodo_call("write", "DeleteRepo", {"id": repo_id})',source)
        self.assertIn('repo_verified_absent',source)
        self.assertIn('resolve_repo_resource(integration)',source)

    def test_new_panel_shows_deletion_stages(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        self.assertIn('def _result_stages(result):',source)
        self.assertIn('Publicação e aliases',source)
        self.assertIn('Stack e repositório Komodo',source)
        self.assertIn('Relatório técnico',source)


if __name__=='__main__':
    unittest.main()
