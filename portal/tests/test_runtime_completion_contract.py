from pathlib import Path
import unittest


class RuntimeCompletionContractTest(unittest.TestCase):
    def test_komodo_completed_requires_running_container(self):
        source = Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn('runtime_running = bool(running_container)', source)
        self.assertIn('elif runtime_running:', source)
        self.assertIn('"running": runtime_running', source)
        self.assertIn('ListStackServices', source)

    def test_initial_publish_requires_runtime_running(self):
        source = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text(encoding='utf-8')
        self.assertIn("runtime=final.get('runtime') or {}", source)
        self.assertIn("runtime_confirmed=runtime.get('running') is True", source)


if __name__ == '__main__':
    unittest.main()
