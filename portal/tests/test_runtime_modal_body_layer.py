from pathlib import Path
import unittest

class RuntimeModalBodyLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_publication_does_not_mount_runtime_modal(self):
        self.assertNotIn('document.body.appendChild(modal)',self.source)
        self.assertNotIn('const runtimeLinks=[...root.querySelectorAll',self.source)
    def test_links_open_isolated_documents(self):
        self.assertIn('target="_blank" rel="noopener"',self.source)
    def test_overlay_is_fixed_and_scroll_is_locked(self):
        self.assertIn('.runtime-modal-backdrop{position:fixed;inset:0;z-index:1700',self.base)
        self.assertIn('.runtime-modal-open{overflow:hidden}',self.base)

if __name__=='__main__':unittest.main()
