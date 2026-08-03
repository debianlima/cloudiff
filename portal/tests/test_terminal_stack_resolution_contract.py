from pathlib import Path
import unittest


class TerminalStackResolutionContractTest(unittest.TestCase):
    def test_terminal_resolves_stack_from_project_integration(self):
        source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn("if project and not stack_id:",source)
        self.assertIn("integration=find_integration(project) or {}",source)
        self.assertIn("stack_id=normalize_resource_id(integration.get('stack_id'))",source)


if __name__=='__main__':
    unittest.main()
