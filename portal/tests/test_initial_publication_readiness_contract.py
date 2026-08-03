from pathlib import Path
import unittest


SCRIPT = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py')


class InitialPublicationReadinessContractTest(unittest.TestCase):
    def test_requires_completed_idle_stack_with_running_runtime(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("completed=final.get('ok') is True and final.get('deploy_status')=='completed'", source)
        self.assertIn("runtime=final.get('runtime') or {}", source)
        self.assertIn("runtime_confirmed=runtime.get('running') is True", source)
        self.assertIn("not remote_errors", source)
        self.assertIn("public_health_status_", source)


if __name__ == '__main__':
    unittest.main()
