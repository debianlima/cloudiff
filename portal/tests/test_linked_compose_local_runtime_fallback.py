from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
K=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
P=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
class LinkedComposeLocalRuntimeFallbackTests(unittest.TestCase):
    def test_status_uses_exact_compose_project_label_when_komodo_inventory_empty(self):
        block=K[K.index('def _cloudif_v132_status_from_payload'):K.index('def cloudif_v132_project_status')]
        self.assertIn('label=com.docker.compose.project=',block)
        self.assertIn('labels.get("com.docker.compose.project")',block)
        self.assertIn('local_compose_fallback',block)
        self.assertIn('runtime_services = local_services',block)
    def test_homologation_does_not_treat_short_komodo_config_hash_as_git_commit(self):
        block=P[P.index('def _create_linked_compose_homologation_candidate'):P.index('def _preview_runtime_snapshot')]
        self.assertIn("re.fullmatch(r'[a-f0-9]{40,64}',preview_head)",block)
        self.assertIn('hmac.compare_digest',block)
if __name__=='__main__':unittest.main()
