from __future__ import annotations
import base64,hashlib,importlib.util,socket,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
spec=importlib.util.spec_from_file_location('artifact_session_import_gateway',GATEWAY);M=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=M;spec.loader.exec_module(M)

class WorkspaceArtifactSessionImportTests(unittest.TestCase):
 def test_official_file_param_descriptor_is_complete(self):
  source=GATEWAY.read_text()
  start=source.index("'name':'workspace.artifact.import'");end=source.index("'name':'workspace.artifact.upload.ticket'",start);block=source[start:end]
  self.assertIn("'_meta':{'openai/fileParams':['file']}",block)
  for field in ('download_url','file_id','mime_type','file_name'):self.assertIn("'"+field+"'",block)
  self.assertIn("'required':['download_url','file_id']",block)
  self.assertIn("'required':['slug','file','filename','expected_size','expected_sha256']",block)

 def test_download_url_rejects_non_https_and_untrusted_hosts(self):
  for url,code in (
   ('http://files.oaiusercontent.com/x','session_file_download_url_invalid'),
   ('https://127.0.0.1/x','session_file_download_host_not_allowed'),
   ('https://example.com/x','session_file_download_host_not_allowed'),
   ('https://files.oaiusercontent.com/x'.replace('https://','https://user'+chr(58)+'pass'+chr(64)),'session_file_download_url_invalid'),
  ):
   with self.assertRaises(ValueError) as ctx:M._session_file_url_allowed(url)
   self.assertEqual(str(ctx.exception),code)

 def test_download_url_accepts_official_host_with_public_dns(self):
  answers=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('104.18.0.1',443))]
  with patch.object(M.socket,'getaddrinfo',return_value=answers):
   self.assertEqual(M._session_file_url_allowed('https://files.oaiusercontent.com/signed?token=x'),'https://files.oaiusercontent.com/signed?token=x')

 def test_download_url_rejects_private_dns_answer(self):
  answers=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.7',443))]
  with patch.object(M.socket,'getaddrinfo',return_value=answers):
   with self.assertRaises(ValueError) as ctx:M._session_file_url_allowed('https://files.oaiusercontent.com/signed')
  self.assertEqual(str(ctx.exception),'session_file_download_private_address')

 def test_session_resolver_accepts_actions_alias_shape(self):
  raw=b'alias-shape';digest=hashlib.sha256(raw).hexdigest()
  ref={'id':'file_0000000013bc820e9585c8554326a64d','download_link':'https://files.oaiusercontent.com/signed?sig=secret','name':'archive.zip','mime_type':'application/zip'}
  with patch.object(M,'_session_file_download',return_value=(raw,{})):
   loaded,meta=M.session_file_resolve(ref,len(raw),digest,'archive.zip')
  self.assertEqual(loaded,raw);self.assertEqual(meta['file_id'],ref['id']);self.assertEqual(meta['file_name'],'archive.zip')

 def test_url_rejection_logs_only_sanitized_shape(self):
  import contextlib,io,json
  secret='signed'+chr(45)+'token'+chr(45)+('x'*24)
  out=io.StringIO()
  with contextlib.redirect_stdout(out):
   with self.assertRaises(ValueError) as ctx:M._session_file_url_allowed('file-service://file_123?sig='+secret)
  self.assertEqual(str(ctx.exception),'session_file_download_url_invalid')
  log=out.getvalue();self.assertNotIn(secret,log);self.assertNotIn('file_123',log)
  event=json.loads(log.strip());self.assertEqual(event['event'],'session_file_url_rejected');self.assertEqual(event['url_shape']['scheme'],'file-service');self.assertEqual(event['url_shape']['host'],'');self.assertTrue(event['url_shape']['has_query'])

 def test_mcp_and_actions_file_ref_aliases_normalize_to_same_shape(self):
  mcp={'file_id':'file_123456','download_url':'https://files.oaiusercontent.com/x','file_name':'a.zip','mime_type':'application/zip'}
  action={'id':'file_123456','download_link':'https://files.oaiusercontent.com/x','name':'a.zip','mime_type':'application/zip'}
  self.assertEqual(M._normalize_session_file_ref(mcp),M._normalize_session_file_ref(action))

 def test_file_param_validates_id_filename_size_and_digest(self):
  raw=b'hello-session-file';digest=hashlib.sha256(raw).hexdigest();ref={'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_0000000012345678','mime_type':'application/zip','file_name':'archive.zip'}
  with patch.object(M,'_session_file_download',return_value=(raw,{})):
   loaded,meta=M.session_file_resolve(ref,len(raw),digest,'archive.zip')
  self.assertEqual(loaded,raw);self.assertEqual(meta['file_id'],ref['file_id']);self.assertEqual(meta['sha256'],digest);self.assertEqual(meta['size'],len(raw))

 def test_file_param_rejects_filename_and_digest_mismatch(self):
  raw=b'payload';ref={'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_123456','file_name':'wrong.zip'}
  with self.assertRaises(ValueError) as ctx:M.session_file_resolve(ref,len(raw),hashlib.sha256(raw).hexdigest(),'expected.zip')
  self.assertEqual(str(ctx.exception),'session_file_name_mismatch')
  ref['file_name']='expected.zip'
  with patch.object(M,'_session_file_download',return_value=(raw,{})):
   with self.assertRaises(ValueError) as ctx:M.session_file_resolve(ref,len(raw),'0'*64,'expected.zip')
  self.assertEqual(str(ctx.exception),'session_file_sha256_mismatch')

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
  self.assertEqual(bytes(state['raw']),raw);self.assertEqual(result['sha256'],digest);self.assertEqual(result['size'],size);self.assertLessEqual(state['batch_calls'],11);self.assertLessEqual(state['max_scalar'],11000)

 def test_gpt_actions_file_ref_normalizes_official_runtime_shape(self):
  ref={'name':'archive.zip','id':'file_0000000013bc820e9585c8554326a64d','mime_type':'application/zip','download_link':'https://files.oaiusercontent.com/signed'}
  normalized=M._normalize_action_file_ref(ref)
  self.assertEqual(normalized,{'download_url':ref['download_link'],'file_id':ref['id'],'mime_type':'application/zip','file_name':'archive.zip'})

 def test_gpt_actions_file_ref_rejects_id_without_download_link(self):
  with self.assertRaises(ValueError) as ctx:M._normalize_action_file_ref({'id':'file_0000000013bc820e9585c8554326a64d'})
  self.assertEqual(str(ctx.exception),'actions_file_download_link_missing')

 def test_dispatch_never_persists_download_url(self):
  source=GATEWAY.read_text();start=source.index("elif name=='workspace.artifact.import':");end=source.index("elif name in {'workspace.artifact.upload.start'",start);block=source[start:end]
  self.assertIn("content['download_url_persisted']=False",block);self.assertIn("content['source']='chatgpt_file_param'",block)
  self.assertNotIn("content['download_url']",block)

if __name__=='__main__':unittest.main()
