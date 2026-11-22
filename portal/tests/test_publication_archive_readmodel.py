import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
UI=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_ui_publications.py').read_text()
JS=(ROOT/'portal/design/publication-release.js').read_text()
class PublicationArchiveReadModelTests(unittest.TestCase):
    def test_delete_archives_operational_history_but_preserves_audit_row(self):
        self.assertIn("set detail_json=?,status='archived',is_active=0",PUB)
        self.assertIn("set status='archived',is_active=0 where project_slug=? and publication_number=?",PUB)
        self.assertIn("'historyRemoved':True",PUB)
        self.assertIn("'canRehydrate':False",PUB)
    def test_release_flow_lists_only_operational_published_releases(self):
        self.assertIn("production_releases where project_slug=? and status='published'",PUB)
        self.assertIn("r.status='published'",UI)
    def test_delete_action_reloads_dynamic_model(self):
        self.assertIn("await post(operation, payload);",JS)
        self.assertIn("await load();",JS)
        self.assertIn("production-history-delete",JS)
        self.assertIn("operation.startsWith('production/history/')",JS)
        self.assertIn("status: 'succeeded'",JS)
        self.assertIn('deixará de aparecer nas listas',JS)
        self.assertIn("${deleteAllowed?`<button",JS)
        self.assertNotIn('Snapshot completo indisponível para reconstrução segura.',JS)
if __name__=='__main__':unittest.main()
