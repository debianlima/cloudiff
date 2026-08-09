from __future__ import annotations
import base64,hashlib,importlib.util,socket,sys,unittest,io
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
  self.assertNotIn("'file_url'",block)
  self.assertIn("'maximum':1073741824",block)
  self.assertIn("'maximum':7200",source[source.index("'name':'workspace.artifact.upload.ticket'"):source.index("'name':'workspace.artifact.upload.status'")])

 def test_existing_artifact_file_upload_descriptor_is_oauth_mcp_only(self):
  source=GATEWAY.read_text();start=source.index("'name':'workspace.artifact.upload.file'");end=source.index("'name':'workspace.artifact.upload.ticket'",start);block=source[start:end]
  self.assertIn("'openai/fileParams':['file']",block)
  self.assertIn("'ui':{'resourceUri':ARTIFACT_UPLOAD_WIDGET_URI}",block)
  self.assertIn("'openai/outputTemplate':ARTIFACT_UPLOAD_WIDGET_URI",block)
  self.assertIn("'required':['slug','artifact_id','file']",block)
  self.assertIn("'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'}",block)
  self.assertIn('sem cookie do Portal',block)
  self.assertNotIn('expected_size',block)
  self.assertNotIn('expected_sha256',block)

 def test_upload_file_path_like_input_falls_back_to_chatgpt_file_picker(self):
  source=GATEWAY.read_text();start=source.index("raw_args=params.get('arguments') or {}") ;end=source.index("validate_tool_arguments(tool,args)",start);block=source[start:end]
  self.assertIn("tool=='workspace.artifact.upload.file'",block)
  self.assertIn("payload.get('code')=='host_file_param_not_hydrated'",block)
  self.assertIn("tool='workspace.artifact.upload.file.select'",block)
  self.assertIn("artifact_file_picker_fallback=True",block)
  self.assertIn("args={'slug':args['slug'],'artifact_id':args['artifact_id']}",block)
  self.assertNotIn("open('/mnt/data",block)
  self.assertNotIn("Path('/mnt/data",block)

 def test_file_picker_widget_uses_host_native_file_apis(self):
  html=M.ARTIFACT_UPLOAD_WIDGET_HTML
  for marker in ('window.openai.selectFiles','window.openai.uploadFile','window.openai.getFileDownloadUrl',"window.openai.callTool('workspace.artifact.upload.file.resolve'",'fileId','downloadUrl'):
   self.assertIn(marker,html)
  self.assertNotIn('/mnt/data',html)
  self.assertNotIn('Authorization: Bearer',html)
  self.assertNotIn('document.cookie',html)

 def test_file_picker_resource_is_mcp_apps_html_and_helper_is_app_only(self):
  source=GATEWAY.read_text()
  self.assertIn("ARTIFACT_UPLOAD_WIDGET_URI='ui://cloudiff/artifact-upload-v1.html'",source)
  self.assertIn("'mimeType':'text/html;profile=mcp-app'",source)
  self.assertIn("'ui':{'visibility':['app']}",source)
  self.assertIn("'openai/widgetAccessible':True",source)
  self.assertIn("'openai/visibility':'private'",source)

 def test_picker_select_tool_is_side_effect_free_and_resolve_reuses_streaming_validator(self):
  source=GATEWAY.read_text()
  readonly=source[source.index('READ_ONLY_TOOLS='):source.index('DESTRUCTIVE_TOOLS=')]
  self.assertIn("'workspace.artifact.upload.file.select'",readonly)
  start=source.index("elif name=='workspace.artifact.upload.file.resolve':");end=source.index("elif name in {'workspace.artifact.upload.start'",start);block=source[start:end]
  self.assertIn('workspace_artifact_upload_existing_https(',block)
  self.assertIn("content['file_resolution']='window.openai.getFileDownloadUrl'",block)
  self.assertIn("content['download_url_persisted']=False",block)
  self.assertIn("content['secrets_exposed']=False",block)

 def test_every_openai_file_param_descriptor_is_scan_tools_compliant(self):
  file_tools=[tool for tool in M.TOOLS if (tool.get('_meta') or {}).get('openai/fileParams')]
  self.assertGreaterEqual(len(file_tools),1)
  for tool in file_tools:
   schema=tool.get('inputSchema') or {};required=set(schema.get('required') or []);props=schema.get('properties') or {}
   for field in tool['_meta']['openai/fileParams']:
    self.assertIn(field,props,tool['name']);self.assertIn(field,required,tool['name'])
    file_schema=props[field]
    self.assertEqual(file_schema.get('type'),'object',tool['name'])
    self.assertNotIn('$ref',file_schema,tool['name'])
    self.assertEqual(set((file_schema.get('properties') or {}).keys()),{'download_url','file_id','mime_type','file_name'},tool['name'])
    self.assertEqual(file_schema.get('required'),['download_url','file_id'],tool['name'])
    self.assertFalse(file_schema.get('additionalProperties',True),tool['name'])

 def test_prevalidation_reports_unhydrated_local_path_before_json_schema(self):
  args={'slug':'laboratorio-de-hardware','file':'/mnt/data/archive.zip','filename':'archive.zip','expected_size':1,'expected_sha256':'a'*64}
  with self.assertRaises(M.ToolInputError) as ctx:M._prepare_openai_file_param('workspace.artifact.import',args)
  self.assertEqual(ctx.exception.payload['code'],'host_file_param_not_hydrated')
  self.assertEqual(ctx.exception.payload['field'],'file')
  self.assertEqual(ctx.exception.payload['fileShape']['classification'],'path_like')
  self.assertTrue(ctx.exception.payload['hostHydrationRequired'])
  self.assertNotIn('/mnt/data/archive.zip',str(ctx.exception.payload))

 def test_rpc_dispatcher_converts_prevalidation_path_signal_into_upload_start(self):
  source=GATEWAY.read_text();start=source.index("raw_args=params.get('arguments') or {}") ;end=source.index("if method=='resources/read':",start);block=source[start:end]
  self.assertIn("requested_tool=params.get('name')",block)
  self.assertIn("payload.get('code')=='host_file_param_not_hydrated'",block)
  self.assertIn("args={k:v for k,v in args.items() if k!='file'}",block)
  self.assertIn("tool='workspace.artifact.upload.start'",block)
  self.assertIn("validate_tool_arguments(tool,args)",block)

 def test_prevalidation_accepts_json_stringified_openai_file_object(self):
  import json
  args={'file':json.dumps({'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_123456','mime_type':'application/zip','file_name':'archive.zip'})}
  prepared=M._prepare_openai_file_param('workspace.artifact.import',args)
  self.assertIsInstance(prepared['file'],dict)
  self.assertEqual(prepared['file']['file_id'],'file_123456')
  self.assertEqual(prepared['file']['file_name'],'archive.zip')
  M.validate_tool_arguments('workspace.artifact.import',{'slug':'laboratorio-de-hardware',**prepared,'filename':'archive.zip','expected_size':1,'expected_sha256':'a'*64})

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

 def test_scalar_and_wrapper_file_refs_are_compatibly_normalized(self):
  url='https://files.oaiusercontent.com/signed?token=secret'
  scalar=M._normalize_session_file_ref(url)
  self.assertEqual(scalar['download_url'],url);self.assertTrue(scalar['file_id'].startswith('compat_'));self.assertEqual(scalar['reference_mode'],'scalar_https')
  wrapped=M._normalize_session_file_ref([{'file_id':'file_123456','download_url':url}])
  self.assertEqual(wrapped['download_url'],url);self.assertEqual(wrapped['reference_mode'],'single_item_array')
  encoded=M._normalize_session_file_ref('{"file_id":"file_123456","download_url":"https://files.oaiusercontent.com/signed"}')
  self.assertEqual(encoded['file_id'],'file_123456');self.assertEqual(encoded['reference_mode'],'json_string')

 def test_scalar_file_id_and_local_path_fail_actionably(self):
  for value,code in (('file_1234567890','session_file_download_url_missing'),('/mnt/data/archive.zip','host_file_path_not_resolved'),('sandbox:/mnt/data/archive.zip','host_file_path_not_resolved')):
   with self.assertRaises(ValueError) as ctx:M._normalize_session_file_ref(value)
   self.assertEqual(str(ctx.exception),code)

 def test_file_shape_telemetry_never_contains_scalar_value(self):
  url='https://files.oaiusercontent.com/signed?token='+'x'*32
  shape=M._session_file_ref_shape(url)
  self.assertEqual(shape['classification'],'https_url');self.assertEqual(shape['value_type'],'str');self.assertEqual(shape['length'],len(url));self.assertNotIn(url,str(shape));self.assertNotIn('token=',str(shape))

 def test_mcp_and_actions_file_ref_aliases_normalize_to_same_shape(self):
  mcp={'file_id':'file_123456','download_url':'https://files.oaiusercontent.com/x','file_name':'a.zip','mime_type':'application/zip'}
  action={'id':'file_123456','download_link':'https://files.oaiusercontent.com/x','name':'a.zip','mime_type':'application/zip'}
  nm=M._normalize_session_file_ref(mcp);na=M._normalize_session_file_ref(action)
  for key in ('file_id','download_url','file_name','mime_type'):self.assertEqual(nm[key],na[key])
  self.assertEqual(nm['reference_mode'],'mcp_object');self.assertEqual(na['reference_mode'],'actions_object')

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

 def test_public_import_dispatch_uses_https_streaming_path(self):
  source=GATEWAY.read_text();start=source.index("elif name=='workspace.artifact.import':");end=source.index("elif name in {'workspace.artifact.upload.start'",start);block=source[start:end]
  self.assertIn('workspace_artifact_import_https(',block)
  self.assertNotIn('workspace_artifact_import_bytes(',block)
  self.assertNotIn('session_file_resolve(',block)

 def test_stream_transport_rejects_trailing_bytes_by_contract(self):
  source=GATEWAY.read_text();start=source.index('def _workspace_direct_upload_stream');end=source.index('def workspace_artifact_import_https',start);block=source[start:end]
  self.assertIn("if source.read(1):raise ValueError('session_file_size_mismatch')",block)

 def test_existing_artifact_file_upload_reuses_recorded_integrity_and_streams(self):
  raw=b'existing-artifact-upload';digest=hashlib.sha256(raw).hexdigest();aid='art_'+'2'*24
  artifact={'artifact_id':aid,'project_slug':'demo','filename':'archive.zip','status':'uploading','expected_size':len(raw),'expected_sha256':digest,'received_bytes':0}
  calls=[]
  def broker(path,payload,timeout=0):
   calls.append((path,payload,timeout))
   if path=='/v1/artifact/upload/status':return 200,{'ok':True,'result':artifact}
   self.fail(path)
  result={'artifact_id':aid,'project_slug':'demo','filename':'archive.zip','status':'sealed','size':len(raw),'sha256':digest,'received_bytes':len(raw)}
  ref={'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_123456','file_name':'archive.zip','mime_type':'application/zip'}
  with patch.object(M,'workspace_broker_post',side_effect=broker),patch.object(M,'_session_file_open',return_value=io.BytesIO(raw)),patch.object(M,'_workspace_direct_upload_stream',return_value=result) as stream:
   uploaded,meta=M.workspace_artifact_upload_existing_https('demo',aid,ref,'trace')
  self.assertTrue(uploaded['uploaded']);self.assertTrue(uploaded['ready_for_change_set']);self.assertEqual(uploaded['transport'],'mcp_oauth_file_stream');self.assertEqual(uploaded['next_tool'],'workspace.artifact.commit.plan')
  self.assertEqual(meta['sha256'],digest);self.assertEqual(meta['size'],len(raw));self.assertEqual(meta['file_id'],'file_123456')
  self.assertEqual([x[0] for x in calls],['/v1/artifact/upload/status']);stream.assert_called_once_with(aid,unittest.mock.ANY,len(raw),digest)

 def test_upload_file_response_reports_mcp_auth_context_without_exposing_secret(self):
  source=GATEWAY.read_text();start=source.index("elif name=='workspace.artifact.upload.file':");end=source.index("elif name in {'workspace.artifact.upload.start'",start);block=source[start:end]
  self.assertIn("content['mcp_identity_reused']=True",block)
  self.assertIn("content['oauth_identity_reused']=bool(getattr(self,'_oauth',None))",block)
  self.assertIn("content['authentication_context']='oauth_mcp'",block)
  self.assertIn("content['portal_cookie_required']=False",block)
  self.assertIn("content['secrets_exposed']=False",block)
  self.assertNotIn("content['token']",block)
  self.assertNotIn("content['cookie']",block)

 def test_existing_artifact_file_upload_rejects_project_mismatch_before_download(self):
  aid='art_'+'3'*24;ref={'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_123456'}
  status={'artifact_id':aid,'project_slug':'other','filename':'archive.zip','status':'uploading','expected_size':1,'expected_sha256':'a'*64}
  with patch.object(M,'workspace_broker_post',return_value=(200,{'ok':True,'result':status})),patch.object(M,'_session_file_open') as opener:
   with self.assertRaises(PermissionError):M.workspace_artifact_upload_existing_https('demo',aid,ref,'trace')
  opener.assert_not_called()

 def test_https_import_starts_ticket_and_streams_without_materializing_file(self):
  raw=b'https-stream-payload';digest=hashlib.sha256(raw).hexdigest();aid='art_'+'1'*24
  calls=[]
  def broker(path,payload,timeout=0):
   calls.append((path,payload,timeout))
   if path=='/v1/artifact/start':return 200,{'ok':True,'result':{'artifact_id':aid}}
   if path=='/v1/artifact/ticket':return 200,{'ok':True,'result':{'artifact_id':aid}}
   self.fail(path)
  result={'artifact_id':aid,'status':'sealed','size':len(raw),'sha256':digest}
  ref={'download_url':'https://files.oaiusercontent.com/signed','file_id':'file_123456','file_name':'archive.zip'}
  with patch.object(M,'_session_file_open',return_value=io.BytesIO(raw)),patch.object(M,'workspace_broker_post',side_effect=broker),patch.object(M,'_workspace_direct_upload_stream',return_value=result) as stream:
   imported,meta=M.workspace_artifact_import_https('demo','archive.zip',ref,len(raw),digest,7200,'trace')
  self.assertEqual(imported['transport'],'https_stream');self.assertEqual(imported['size'],len(raw));self.assertEqual(meta['file_id'],'file_123456')
  self.assertEqual([x[0] for x in calls],['/v1/artifact/start','/v1/artifact/ticket']);stream.assert_called_once()

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
