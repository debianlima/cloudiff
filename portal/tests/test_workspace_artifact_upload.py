import base64,hashlib,importlib.util,tempfile,time,unittest,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BROKER=(ROOT/'components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py').read_text()
UNIT=(ROOT/'components/control-plane/etc/systemd/system/cloudif-workspace-broker.service').read_text()
PATH=ROOT/'components/control-plane/current-apps/workspace-broker-current/cloudif_workspace_artifact.py'
spec=importlib.util.spec_from_file_location('artifact',PATH);A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

class WorkspaceArtifactUploadTests(unittest.TestCase):
 def test_binary_chunk_upload_is_sealed_and_idempotent(self):
  raw=(b'PK\x03\x04\x00binary-document\x00'*12000)[:310000];digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   started=A.start_artifact(td,'demo','acervo.zip',len(raw),digest,900);aid=started['artifact_id']
   chunks=[raw[i:i+120000] for i in range(0,len(raw),120000)]
   for i,chunk in enumerate(chunks):
    encoded=base64.b64encode(chunk).decode();sha=hashlib.sha256(chunk).hexdigest();r=A.append_chunk(td,'demo',aid,i,encoded,sha)
    if i==0:
     again=A.append_chunk(td,'demo',aid,i,encoded,sha);self.assertTrue(again['idempotent'])
   sealed=A.complete_artifact(td,'demo',aid);self.assertEqual(sealed['status'],'sealed');self.assertEqual(sealed['sha256'],digest);self.assertEqual(sealed['size'],len(raw))
   meta,loaded=A.read_artifact(td,'demo',aid,digest,len(raw));self.assertEqual(loaded,raw);self.assertEqual(meta['project_slug'],'demo')
 def test_project_scope_digest_order_and_size_are_enforced(self):
  raw=b'abc';digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','x.bin',3,digest,900)['artifact_id'];enc=base64.b64encode(raw).decode();sha=hashlib.sha256(raw).hexdigest()
   with self.assertRaises(A.ArtifactError):A.append_chunk(td,'other',aid,0,enc,sha)
   with self.assertRaises(A.ArtifactError):A.append_chunk(td,'demo',aid,1,enc,sha)
   with self.assertRaises(A.ArtifactError):A.append_chunk(td,'demo',aid,0,enc,'0'*64)
   A.append_chunk(td,'demo',aid,0,enc,sha);A.complete_artifact(td,'demo',aid)
   with self.assertRaises(A.ArtifactError):A.read_artifact(td,'demo',aid,'0'*64,3)
 def test_hold_extends_sealed_artifact_ttl(self):
  raw=b'x';digest=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','x.bin',1,digest,300)['artifact_id'];A.append_chunk(td,'demo',aid,0,base64.b64encode(raw).decode(),digest);A.complete_artifact(td,'demo',aid)
   before=A.resolve_artifact(td,'demo',aid)['expires_at'];future=int(time.time())+1200;after=A.resolve_artifact(td,'demo',aid,hold_until=future)['expires_at'];self.assertGreater(after,before);self.assertGreaterEqual(after,future)


 def test_archive_size_that_broke_inline_transport_uploads_in_safe_chunks(self):
  size=1_390_970;raw=(bytes(range(256))*((size//256)+1))[:size];digest=hashlib.sha256(raw).hexdigest()
  self.assertGreater(len(base64.b64encode(raw)),349528)
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','documentos-anonimizados.zip',size,digest,3600)['artifact_id'];index=0
   for offset in range(0,size,A.MAX_CHUNK_BYTES):
    chunk=raw[offset:offset+A.MAX_CHUNK_BYTES];encoded=base64.b64encode(chunk).decode();self.assertLessEqual(len(encoded),262144)
    A.append_chunk(td,'demo',aid,index,encoded,hashlib.sha256(chunk).hexdigest());index+=1
   sealed=A.complete_artifact(td,'demo',aid);self.assertEqual(sealed['size'],size);self.assertEqual(sealed['sha256'],digest);self.assertGreater(index,1)


 def test_concurrent_retry_of_same_chunk_does_not_duplicate_bytes(self):
  raw=b'x'*120000;digest=hashlib.sha256(raw).hexdigest();encoded=base64.b64encode(raw).decode()
  with tempfile.TemporaryDirectory() as td:
   aid=A.start_artifact(td,'demo','race.bin',len(raw),digest,900)['artifact_id'];barrier=threading.Barrier(3);results=[];errors=[]
   def worker():
    try:barrier.wait();results.append(A.append_chunk(td,'demo',aid,0,encoded,digest))
    except Exception as exc:errors.append(exc)
   threads=[threading.Thread(target=worker) for _ in range(2)]
   [t.start() for t in threads];barrier.wait();[t.join() for t in threads]
   self.assertFalse(errors);self.assertEqual(len(results),2);self.assertEqual(sorted(bool(x.get('idempotent')) for x in results),[False,True])
   sealed=A.complete_artifact(td,'demo',aid);self.assertEqual(sealed['size'],len(raw));self.assertEqual(sealed['sha256'],digest)


 def test_artifact_store_is_outside_ephemeral_workspace_root(self):
  self.assertIn("ARTIFACT_ROOT = os.environ.get('CLOUDIF_WORKSPACE_ARTIFACT_ROOT', '/var/lib/cloudif/workspace-artifacts')",BROKER)
  self.assertIn('ReadWritePaths=/var/lib/cloudif/workspaces /var/lib/cloudif/workspace-artifacts /var/lib/cloudif/workspace-change-sets',UNIT)
  self.assertIn("CHANGESET_ROOT = os.environ.get('CLOUDIF_WORKSPACE_CHANGESET_ROOT', '/var/lib/cloudif/workspace-change-sets')",BROKER)
  self.assertNotIn("Path(artifact_root) / '.artifacts'",PATH.read_text())

if __name__=='__main__':unittest.main()
