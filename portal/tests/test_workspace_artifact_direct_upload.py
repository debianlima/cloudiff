from __future__ import annotations
import hashlib,importlib.util,io,tempfile,time,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'components/control-plane/current-apps/workspace-broker-current/cloudif_workspace_artifact.py'
spec=importlib.util.spec_from_file_location('artifact_direct',PATH);A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

class WorkspaceArtifactDirectUploadTests(unittest.TestCase):
 def test_ticket_hash_is_stored_but_plain_ticket_is_not(self):
  raw=b'zip-data';digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','archive.zip',len(raw),digest,900)['artifact_id'];ticket=A.create_upload_ticket(td,'demo',aid,'client-a',300)
   token=ticket['upload_ticket'];meta=(Path(td)/aid/'metadata.json').read_text()
   self.assertNotIn(token,meta);self.assertIn(hashlib.sha256(token.encode()).hexdigest(),meta)
   status=A.inspect_upload_ticket(td,token);self.assertEqual(status['upload_ticket_status'],'pending');self.assertEqual(status['artifact_id'],aid)
 def test_direct_upload_atomically_replaces_partial_payload_and_seals(self):
  raw=b'PK\x03\x04'+bytes(range(128))*9000;digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','archive.zip',len(raw),digest,900)['artifact_id']
   partial=b'partial';p=Path(td)/aid/'payload.bin';p.write_bytes(partial)
   token=A.create_upload_ticket(td,'demo',aid,'client-a',300)['upload_ticket']
   result=A.direct_upload_artifact(td,token,io.BytesIO(raw),len(raw));self.assertEqual(result['status'],'sealed');self.assertEqual(result['sha256'],digest);self.assertEqual(result['size'],len(raw));self.assertEqual(result['upload_transport'],'browser_direct');self.assertEqual(p.read_bytes(),raw)
   status=A.inspect_upload_ticket(td,token);self.assertEqual(status['upload_ticket_status'],'used')
   with self.assertRaises(A.ArtifactError) as ctx:A.direct_upload_artifact(td,token,io.BytesIO(raw),len(raw))
   self.assertEqual(ctx.exception.code,'upload_ticket_used')
 def test_failed_digest_keeps_previous_payload_and_ticket_retryable(self):
  expected=b'expected';bad=b'wrong---';digest=hashlib.sha256(expected).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','x.bin',len(expected),digest,900)['artifact_id'];p=Path(td)/aid/'payload.bin';p.write_bytes(b'old')
   token=A.create_upload_ticket(td,'demo',aid,'client-a',300)['upload_ticket']
   with self.assertRaises(A.ArtifactError) as ctx:A.direct_upload_artifact(td,token,io.BytesIO(bad),len(bad))
   self.assertEqual(ctx.exception.code,'artifact_sha256_mismatch');self.assertEqual(p.read_bytes(),b'old');self.assertEqual(A.inspect_upload_ticket(td,token)['upload_ticket_status'],'pending')
 def test_ticket_is_project_scoped_and_short_lived(self):
  raw=b'x';digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','x.bin',1,digest,900)['artifact_id']
   with self.assertRaises(A.ArtifactError):A.create_upload_ticket(td,'other',aid,'client',300)
   with self.assertRaises(A.ArtifactError):A.create_upload_ticket(td,'demo',aid,'client',1801)

if __name__=='__main__':unittest.main()
