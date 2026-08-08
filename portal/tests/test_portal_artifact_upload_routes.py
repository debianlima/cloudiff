from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
COEX=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()

class PortalArtifactUploadRoutesTests(unittest.TestCase):
 def test_modern_upload_routes_are_wired_before_legacy_fallback(self):
  for marker in ('cloudif_portal_artifact_upload','/cloudiff/portal/artifact-upload','/cloudiff/portal/api/artifact-upload/status','/cloudiff/portal/api/artifact-upload/content','artifact_forward_upload','artifact_project_allowed'):
   self.assertIn(marker,COEX)
  self.assertLess(COEX.index("'/cloudiff/portal/artifact-upload'"),COEX.index('base_workspace_match'))
 def test_upload_content_requires_csrf_and_project_access(self):
  block=COEX[COEX.index("'/cloudiff/portal/api/artifact-upload/content'"):COEX.index('release_flow_match =',COEX.index("'/cloudiff/portal/api/artifact-upload/content'"))]
  self.assertIn('_prod_csrf_equal',block);self.assertIn('artifact_project_allowed',block);self.assertIn('artifact_forward_upload',block)

if __name__=='__main__':unittest.main()
