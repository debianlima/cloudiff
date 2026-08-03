from pathlib import Path
import unittest


class ForgejoWebhookAutomationContractTest(unittest.TestCase):
    def setUp(self):
        self.source=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text(encoding='utf-8')

    def test_webhook_requires_hmac_signature(self):
        self.assertIn('def _cloudif_forgejo_signature_ok',self.source)
        self.assertIn('X-Forgejo-Signature',self.source)
        self.assertIn('hmac.compare_digest',self.source)
        self.assertIn('invalid_webhook_signature',self.source)

    def test_main_push_queues_async_komodo_deploy(self):
        self.assertIn('refs/heads/main',self.source)
        self.assertIn('threading.Thread(target=_cloudif_forgejo_push_worker',self.source)
        self.assertIn('/komodo/stack/pull',self.source)
        self.assertIn('/komodo/stack/deploy',self.source)
        self.assertIn('/komodo/project/status',self.source)

    def test_worker_requires_healthy_runtime_and_matching_commit(self):
        self.assertIn('runtime.get("running") is True',self.source)
        self.assertIn('deployed == after[:7]',self.source)
        self.assertIn('last_forgejo_automation_status',self.source)


if __name__=='__main__':
    unittest.main()
