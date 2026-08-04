from pathlib import Path
import unittest

class HelpYoutubeVideosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/current-apps/portal-current/cloudif_portal_sections98.py').read_text()+Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_both_videos_are_present(self):
        self.assertIn('https://youtu.be/cxH3K8s1R9M',self.source)
        self.assertIn('https://youtu.be/pJ7mx3VZuWU',self.source)
    def test_links_open_safely_in_new_tab(self):
        self.assertGreaterEqual(self.source.count('target="_blank" rel="noopener noreferrer"'),3)
    def test_help_keeps_github_reference(self):
        self.assertIn('https://github.com/debianlima/cloudiff',self.source)

if __name__=='__main__':unittest.main()
