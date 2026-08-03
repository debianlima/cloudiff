from pathlib import Path
import unittest


class AdminDeleteAgentIntegrationContractTest(unittest.TestCase):
    def test_komodo_normalizes_serialized_mongo_ids(self):
        source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn('def normalize_resource_id(value):',source)
        self.assertIn('json.loads(text)',source)
        self.assertIn('stack_id = normalize_resource_id',source)

    def test_destroy_is_idempotent_when_stack_is_absent(self):
        source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text(encoding='utf-8')
        self.assertIn('already_absent=(action=="destroy"',source)
        self.assertIn('idempotent_absent',source)

    def test_admin_delete_preserves_agent_http_error_body(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        self.assertIn('except urllib.error.HTTPError as exc:',source)
        self.assertIn("'data':data",source)


if __name__=='__main__':
    unittest.main()
