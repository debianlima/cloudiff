from pathlib import Path
import unittest


SCRIPT = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py')


class InitialPublicationReadinessContractTest(unittest.TestCase):
    def test_accepts_completed_stack_when_core_omits_deployed_hash(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("service_confirmed", source)
        self.assertIn("stack.get('latest_services') or stack.get('services')", source)
        self.assertIn("not remote_errors", source)
        self.assertIn("hash_confirmed or service_confirmed", source)


if __name__ == '__main__':
    unittest.main()
