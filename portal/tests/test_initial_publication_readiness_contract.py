from pathlib import Path
import unittest


SCRIPT = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py')


class InitialPublicationReadinessContractTest(unittest.TestCase):
    def test_accepts_completed_stack_when_core_omits_deployed_hash(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("identified=bool(stack.get('id') or stack.get('name'))", source)
        self.assertIn("hashes_consistent=(not deployed) or (not latest) or deployed==latest", source)
        self.assertIn("not remote_errors", source)
        self.assertIn("completed and idle and identified", source)
        self.assertNotIn("bool(deployed) and deployed == latest", source)


if __name__ == '__main__':
    unittest.main()
