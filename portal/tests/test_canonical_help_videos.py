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
 def test_admin_cta_is_only_rendered_for_tenant_admin(self):
  self.assertIn('def help_body(show_admin_link: bool = False)',self.source)
  self.assertIn("return body if show_admin_link else body.replace(admin_cta, '')",self.source)
  self.assertIn('help_body(tenant_admin_allowed(self))',self.source)
  self.assertIn('Abrir Administração',self.source)

if __name__=='__main__':unittest.main()
