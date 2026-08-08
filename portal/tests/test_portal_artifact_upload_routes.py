from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
COEX=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()

class PortalArtifactUploadRoutesTests(unittest.TestCase):
 def test_modern_upload_routes_are_wired_before_legacy_fallback(self):
  for marker in ('cloudif_portal_artifact_upload','artifact-upload/(art_[a-f0-9]{24})','/cloudiff/portal/api/artifact-upload/status','/cloudiff/portal/api/artifact-upload/content','artifact_forward_upload_by_id','artifact_upload_status','artifact_project_allowed'):
   self.assertIn(marker,COEX)
  self.assertLess(COEX.index('artifact_upload_match='),COEX.index('base_workspace_match'))
 def test_upload_content_requires_csrf_project_access_and_artifact_id(self):
  block=COEX[COEX.index("'/cloudiff/portal/api/artifact-upload/content'"):COEX.index('release_flow_match =',COEX.index("'/cloudiff/portal/api/artifact-upload/content'"))]
  for marker in ('_prod_csrf_equal','artifact_project_allowed','artifact_forward_upload_by_id','X-CloudIF-Artifact-Id'):
   self.assertIn(marker,block)
 def test_legacy_ticket_route_remains_supported(self):
  self.assertIn('artifact_ticket_status',COEX);self.assertIn('artifact_forward_upload(self,ticket,expected)',COEX)

if __name__=='__main__':unittest.main()
