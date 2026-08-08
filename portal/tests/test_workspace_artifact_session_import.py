from __future__ import annotations
import base64,hashlib,importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
spec=importlib.util.spec_from_file_location('artifact_session_import_gateway',GATEWAY);M=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=M;spec.loader.exec_module(M)

class FakeResponse:
 def __init__(self,raw,file_id):
  self.raw=raw;self.headers={'Content-Length':str(len(raw)),'X-CloudIF-File-Id':file_id,'X-CloudIF-File-Sha256':hashlib.sha256(raw).hexdigest()}
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,n=-1):return self.raw if n<0 else self.raw[:n]

class WorkspaceArtifactSessionImportTests(unittest.TestCase):
 def test_import_fails_closed_without_resolver(self):
  with patch.object(M,'SESSION_FILE_RESOLVER_URL',''),patch.object(M,'SESSION_FILE_RESOLVER_TOKEN',''):
   with self.assertRaises(ValueError) as ctx:M.session_file_resolve('file_123456',1,hashlib.sha256(b'x').hexdigest(),'trace')
  self.assertIn('workspace.artifact.upload.batch',str(ctx.exception))

 def test_resolver_rejects_plain_http_non_loopback(self):
  raw=b'x';digest=hashlib.sha256(raw).hexdigest()
  with patch.object(M,'SESSION_FILE_RESOLVER_URL','http://10.0.0.5/files'),patch.object(M,'SESSION_FILE_RESOLVER_TOKEN','token'):
   with self.assertRaises(ValueError) as ctx:M.session_file_resolve('file_123456',1,digest,'trace')
  self.assertEqual(str(ctx.exception),'session_file_resolver_invalid')

 def test_resolver_validates_file_id_size_and_digest(self):
  raw=b'hello-session-file';digest=hashlib.sha256(raw).hexdigest();fid='file_1234567890'
  with patch.object(M,'SESSION_FILE_RESOLVER_URL','https://resolver.invalid/v1/files/content'),patch.object(M,'SESSION_FILE_RESOLVER_TOKEN','token'),patch.object(M.urllib.request,'urlopen',return_value=FakeResponse(raw,fid)):
   loaded=M.session_file_resolve(fid,len(raw),digest,'trace')
  self.assertEqual(loaded,raw)

 def test_exact_problem_size_import_uses_small_internal_batches(self):
  size=1_390_970;raw=(bytes(range(256))*((size//256)+1))[:size];digest=hashlib.sha256(raw).hexdigest();state={'raw':bytearray(),'next':0,'batch_calls':0,'max_scalar':0}
  def broker(path,payload,timeout=0):
   if path=='/v1/artifact/start':return 200,{'ok':True,'result':{'artifact_id':'art_'+'1'*24}}
   if path=='/v1/artifact/batch':
    state['batch_calls']+=1
    for item in payload['chunks']:
     self.assertEqual(item['chunk_index'],state['next']);state['next']+=1;state['max_scalar']=max(state['max_scalar'],len(item['content_base64']))
     part=base64.b64decode(item['content_base64'],validate=True);self.assertEqual(hashlib.sha256(part).hexdigest(),item['chunk_sha256']);state['raw'].extend(part)
    return 200,{'ok':True,'result':{'artifact_id':'art_'+'1'*24,'next_chunk':state['next']}}
   if path=='/v1/artifact/complete':
    final=bytes(state['raw']);return 200,{'ok':True,'result':{'artifact_id':'art_'+'1'*24,'status':'sealed','size':len(final),'sha256':hashlib.sha256(final).hexdigest()}}
   self.fail(path)
  with patch.object(M,'workspace_broker_post',side_effect=broker):result=M.workspace_artifact_import_bytes('demo','archive.zip',raw,digest,3600,'trace')
  self.assertEqual(bytes(state['raw']),raw);self.assertEqual(result['sha256'],digest);self.assertEqual(result['size'],size);self.assertLessEqual(state['batch_calls'],11);self.assertLessEqual(state['max_scalar'],11000);self.assertEqual(result['transport'],'session_file_resolver')

if __name__=='__main__':unittest.main()
