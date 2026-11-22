import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
class LegacyPublicationDeleteContractTests(unittest.TestCase):
    def test_delete_route_and_guards_exist(self):
        self.assertIn('/komodo/publication/release/delete',RUNTIME)
        self.assertIn('def cloudif_publication_release_delete(handler):',RUNTIME)
        self.assertIn("active_production_cannot_be_deleted",RUNTIME)
        self.assertIn("production_container_identity_invalid",RUNTIME)
        self.assertIn("production_container_labels_invalid",RUNTIME)
        self.assertIn("active_alias_present",RUNTIME)
    def test_delete_preserves_image_and_marks_runtime_deleted(self):
        self.assertIn("['docker','rm','-f',target]",RUNTIME)
        self.assertIn("set status='deleted',is_active=0",RUNTIME)
        self.assertIn("'imagePreserved':image_preserved",RUNTIME)
        self.assertIn("'canRehydrate':False",RUNTIME)
if __name__=='__main__':unittest.main()
