from pathlib import Path
import unittest


class ProvisioningMetadataPersistenceContractTest(unittest.TestCase):
    def setUp(self):
        self.source=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text(encoding='utf-8')

    def test_extracts_repo_and_server_ids_from_komodo(self):
        self.assertIn('comp["repo_id"]',self.source)
        self.assertIn('comp["repo_name"]',self.source)
        self.assertIn('comp["server_name"]',self.source)

    def test_persists_webhook_and_komodo_resource_metadata(self):
        self.assertIn('forgejo_webhook_url',self.source)
        self.assertIn('komodo_repo_id',self.source)
        self.assertIn('komodo_repo_name',self.source)
        self.assertIn('COALESCE(NULLIF(excluded.komodo_repo_id',self.source)

    def test_does_not_replace_valid_metadata_with_empty_values(self):
        self.assertIn("COALESCE(NULLIF(excluded.forgejo_webhook_url,''),project_integrations.forgejo_webhook_url)",self.source)
        self.assertIn("repo_name=COALESCE(NULLIF(?,''),repo_name)",self.source)


if __name__=='__main__':
    unittest.main()
