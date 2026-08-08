from __future__ import annotations
import importlib.util,io,json,hashlib,sys,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_artifact_upload.py'
spec=importlib.util.spec_from_file_location('portal_artifact_upload',MODULE);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class Response:
 def __init__(self,raw):self.raw=raw
 def read(self,n=-1):return self.raw.read(n)
class Handler:
 def __init__(self,raw):self.headers={'Content-Length':str(len(raw)),'Content-Type':'application/octet-stream'};self.rfile=Response(io.BytesIO(raw))

class PortalArtifactUploadBridgeTests(unittest.TestCase):
 def test_page_uses_fragment_ticket_session_storage_and_no_ticket_placeholder(self):
  page=M.render_page('csrf-token').decode()
  self.assertIn("location.hash",page);self.assertIn("sessionStorage.setItem",page);self.assertIn("history.replaceState",page)
  self.assertIn('/cloudiff/portal/api/artifact-upload/status',page);self.assertIn('/cloudiff/portal/api/artifact-upload/content',page)
  self.assertNotIn('upt_111111111111111111111111_',page)
  self.assertIn('csrf-token',page)
 def test_safe_metadata_never_returns_ticket_hash_or_requester(self):
  meta={'artifact_id':'art_'+'1'*24,'project_slug':'demo','filename':'x.zip','expected_size':9,'expected_sha256':'a'*64,'upload_ticket':{'sha256':'secret'},'requested_by':'client'}
  safe=M.safe_metadata(meta);self.assertNotIn('upload_ticket',safe);self.assertNotIn('requested_by',safe);self.assertEqual(safe['filename'],'x.zip')
 def test_forward_upload_rejects_wrong_size_before_proxy(self):
  h=Handler(b'abc')
  with self.assertRaises(ValueError) as ctx:M.forward_upload(h,'upt_'+('1'*24)+'_'+('2'*48),4)
  self.assertEqual(str(ctx.exception),'artifact_size_mismatch')

if __name__=='__main__':unittest.main()
