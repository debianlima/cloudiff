from pathlib import Path
import unittest

class CanonicalHelpVideosTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_videos_are_in_canonical_help(self):
  self.assertIn('Vídeos rápidos',self.source)
  self.assertIn('https://youtu.be/cxH3K8s1R9M',self.source)
  self.assertIn('https://youtu.be/pJ7mx3VZuWU',self.source)
 def test_video_links_are_safe(self):
  self.assertGreaterEqual(self.source.count('target="_blank" rel="noopener noreferrer"'),3)

if __name__=='__main__':unittest.main()
