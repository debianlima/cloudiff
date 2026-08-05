from pathlib import Path
import unittest


class RuntimeInfoActivePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(
            'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
        ).read_text()
        start = cls.source.index('def cloudif_project_runtime_info')
        end = cls.source.index('\ndef _cloudif_active_publication_stack', start)
        cls.route = cls.source[start:end]

    def test_diagnostic_uses_active_version_container(self):
        for marker in (
            '_cloudif_active_publication_stack(project,base_stack_id)',
            'active.get("container")',
            '["docker","inspect",candidate]',
            '["docker","exec",container',
        ):
            self.assertIn(marker, self.route)

    def test_terminal_health_does_not_block_read_only_diagnostic(self):
        self.assertNotIn('if not audit.get("healthy")', self.route)
        self.assertIn('active_container_not_running', self.route)
        self.assertIn('bool(state.get("Running"))', self.route)

    def test_only_fixed_runtime_queries_remain(self):
        self.assertIn('kind not in {"php","node"}', self.route)
        self.assertIn('php --ini', self.route)
        self.assertIn('php -m', self.route)
        self.assertIn('process.versions', self.route)
        self.assertNotIn('payload.get("command")', self.route)


if __name__ == '__main__':
    unittest.main()
