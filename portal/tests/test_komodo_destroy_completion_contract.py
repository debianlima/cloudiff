from pathlib import Path
import unittest


class KomodoDestroyCompletionContractTest(unittest.TestCase):
    def test_destroy_waits_and_verifies_absence(self):
        source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn('def stack_absent(stack_id, stack_name):',source)
        self.assertIn('_cloudif_pub_wait_operation(operation_id, timeout=180)',source)
        self.assertIn('operation_final.get("success") is True',source)
        self.assertIn('verified_absent, absence_check = stack_absent',source)
        self.assertIn('"verified_absent": verified_absent',source)


if __name__=='__main__':
    unittest.main()
