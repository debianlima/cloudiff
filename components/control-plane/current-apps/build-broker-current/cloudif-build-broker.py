#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,sys,time,urllib.request,urllib.error,urllib.parse,uuid,hmac,secrets,threading,importlib.util
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
try:
 from cloudif_toolchain_policy import validate_toolchain,load_catalog,digest as toolchain_policy_digest
except ModuleNotFoundError:
 _policy_path=Path(__file__).with_name('cloudif_toolchain_policy.py');_policy_spec=importlib.util.spec_from_file_location('cloudif_toolchain_policy',_policy_path);_policy_module=importlib.util.module_from_spec(_policy_spec);assert _policy_spec.loader;_policy_spec.loader.exec_module(_policy_module)
 validate_toolchain=_policy_module.validate_toolchain;load_catalog=_policy_module.load_catalog;toolchain_policy_digest=_policy_module.digest
try:
 import cloudif_toolchain_lifecycle as toolchain_lifecycle
except ModuleNotFoundError:
 _lifecycle_path=Path(__file__).with_name('cloudif_toolchain_lifecycle.py');_lifecycle_spec=importlib.util.spec_from_file_location('cloudif_toolchain_lifecycle',_lifecycle_path);toolchain_lifecycle=importlib.util.module_from_spec(_lifecycle_spec);assert _lifecycle_spec.loader;_lifecycle_spec.loader.exec_module(toolchain_lifecycle)
DB=os.environ.get('CLOUDIF_BUILD_DB','/var/lib/cloudif/build-broker/builds.sqlite3')
TOKEN=os.environ.get('CLOUDIF_BUILD_TOKEN','')
WORKER_TOKEN=os.environ.get('CLOUDIF_BUILD_WORKER_TOKEN','')
ATTEST_KEY=os.environ.get('CLOUDIF_BUILD_ATTESTATION_KEY','').encode()
RUNTIME_URL=os.environ.get('CLOUDIF_RUNTIME_URL','http://127.0.0.1:18212').rstrip('/')
WORKSPACE_URL=os.environ.get('CLOUDIF_WORKSPACE_URL','http://127.0.0.1:18206').rstrip('/')
WORKSPACE_TOKEN=os.environ.get('CLOUDIF_WORKSPACE_TOKEN','')
PROJECT_CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
PROJECT_CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
MULTISERVICE_WORKER_INTERVAL=int(os.environ.get('CLOUDIF_MULTISERVICE_BUILD_INTERVAL','2'))
STATIC_BASE='cgr.dev/chainguard/nginx@sha256:d36a7338ffc140bc1e3cd85e2eb9d3419cf8b03b848a2f26cc99db157f1f505d'
NODE24_BUILDER='node@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd'
NODE24_RUNTIME='gcr.io/distroless/nodejs24-debian12@sha256:6afed2f0373317ea4c66843fc7f1d4b4c88ef3e97254b2c5925793c2beb72809'
ARTIFACT_URL=os.environ.get('CLOUDIF_ARTIFACT_EXECUTOR_URL','http://10.62.91.3').rstrip('/')
ARTIFACT_TOKEN=os.environ.get('CLOUDIF_ARTIFACT_EXECUTOR_TOKEN','')
TOOLCHAIN_CATALOG=Path(os.environ.get('CLOUDIF_TOOLCHAIN_CATALOG','/etc/cloudif/toolchain-catalog-v1.json'))
HOST=os.environ.get('CLOUDIF_BUILD_HOST','127.0.0.1'); PORT=int(os.environ.get('CLOUDIF_BUILD_PORT','18213'))
SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$'); REF=re.compile(r'^[A-Za-z0-9._/-]{1,128}$')
def now(): return int(time.time())
def db():
 c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON')
 c.execute('''CREATE TABLE IF NOT EXISTS builds(id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE,project_slug TEXT,ref TEXT,framework TEXT,plan_digest TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,lease_until INTEGER,attempts INTEGER DEFAULT 0,result_json TEXT,log_text TEXT,next_attempt_at INTEGER DEFAULT 0,dead_reason TEXT)''')
 cols={r[1] for r in c.execute('PRAGMA table_info(builds)')}
 if 'next_attempt_at' not in cols:c.execute('ALTER TABLE builds ADD COLUMN next_attempt_at INTEGER DEFAULT 0')
 if 'dead_reason' not in cols:c.execute('ALTER TABLE builds ADD COLUMN dead_reason TEXT')
 c.execute('CREATE INDEX IF NOT EXISTS idx_build_due ON builds(status,next_attempt_at,created_at)')
 c.execute('CREATE INDEX IF NOT EXISTS idx_build_project_active ON builds(project_slug,status)')
 c.execute('''CREATE TABLE IF NOT EXISTS multiservice_jobs(job_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE,project_slug TEXT NOT NULL,ref TEXT NOT NULL,config_revision INTEGER NOT NULL,config_digest TEXT NOT NULL,toolchain_digest TEXT NOT NULL,archive_sha256 TEXT NOT NULL,plan_digest TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,result_json TEXT NOT NULL DEFAULT '{}',created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '')''')
 c.execute('CREATE INDEX IF NOT EXISTS idx_multiservice_jobs_due ON multiservice_jobs(status,created_at)')
 c.execute('''CREATE TABLE IF NOT EXISTS toolchain_jobs(job_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE,project_slug TEXT NOT NULL,ref TEXT NOT NULL,config_revision INTEGER NOT NULL,config_digest TEXT NOT NULL,toolchain_digest TEXT NOT NULL,archive_sha256 TEXT NOT NULL,plan_digest TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,result_json TEXT NOT NULL DEFAULT '{}',log_text TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '')''')
 c.execute('CREATE INDEX IF NOT EXISTS idx_toolchain_jobs_project ON toolchain_jobs(project_slug,status,created_at)')
 c.execute('''CREATE TABLE IF NOT EXISTS toolchain_images(image_record_id TEXT PRIMARY KEY,project_slug TEXT NOT NULL,service TEXT NOT NULL,toolchain_digest TEXT NOT NULL,image_ref TEXT NOT NULL,image_id TEXT NOT NULL,config_revision INTEGER NOT NULL,config_digest TEXT NOT NULL,archive_sha256 TEXT NOT NULL,plan_digest TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(project_slug,service,toolchain_digest,image_id))''')
 c.execute('CREATE INDEX IF NOT EXISTS idx_toolchain_images_project ON toolchain_images(project_slug,service,status,created_at DESC)')
 c.execute('''CREATE TABLE IF NOT EXISTS toolchain_activations(project_slug TEXT NOT NULL,environment TEXT NOT NULL,service TEXT NOT NULL,image_record_id TEXT NOT NULL,toolchain_digest TEXT NOT NULL,activation_revision INTEGER NOT NULL,approval_id TEXT NOT NULL,activated_by TEXT NOT NULL,activated_at INTEGER NOT NULL,PRIMARY KEY(project_slug,environment,service))''')
 c.execute('''CREATE TABLE IF NOT EXISTS toolchain_activation_history(event_id TEXT PRIMARY KEY,project_slug TEXT NOT NULL,environment TEXT NOT NULL,service TEXT NOT NULL,before_image_record_id TEXT,after_image_record_id TEXT NOT NULL,activation_revision INTEGER NOT NULL,approval_id TEXT NOT NULL,actor TEXT NOT NULL,created_at INTEGER NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS toolchain_activation_state(project_slug TEXT NOT NULL,environment TEXT NOT NULL,revision INTEGER NOT NULL,activation_digest TEXT NOT NULL,updated_by TEXT NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(project_slug,environment))''')
 c.commit()
 return c
def init_db():
 c=db();c.close()
def sanitize(s):
 s=str(s)[:20000]
 s=re.sub(r'(?i)(authorization|token|password|secret|api[_-]?key)\s*[:=]\s*\S+',r'\1=[redacted]',s)
 return s
def idem(a):
 raw='|'.join([a['project_slug'],a['ref'],a['framework'],a['build_plan_digest'],'preview','build.request'])
 return hashlib.sha256(raw.encode()).hexdigest()
def auth(h): return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def worker_auth(h): return bool(WORKER_TOKEN) and h.get('Authorization','')=='Bearer '+WORKER_TOKEN
def validate_plan(framework,digest_value):
 data=json.dumps({'framework':framework},separators=(',',':')).encode()
 req=urllib.request.Request(RUNTIME_URL+'/v1/plan',data=data,method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:x=json.load(r)
 return bool(x.get('ok') and hmac.compare_digest(str(x.get('build_plan_digest') or ''),str(digest_value)))
def attest(slug,bid,summary):
 payload={'version':1,'project_slug':slug,'build_id':bid,'artifact_image_id':summary.get('artifact_image_id'),'sbom_sha256':summary.get('sbom_sha256'),'scanner_sha256':summary.get('scanner_sha256'),'immutable_source_digest':summary.get('immutable_source_digest'),'policy':'HMAC-SHA256'}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode();sig=hmac.new(ATTEST_KEY,raw,hashlib.sha256).hexdigest()
 return {'payload':payload,'signature':sig,'algorithm':'HMAC-SHA256','verified':True}
def verify_attestation(att):
 try:
  raw=json.dumps(att['payload'],sort_keys=True,separators=(',',':')).encode();return hmac.compare_digest(hmac.new(ATTEST_KEY,raw,hashlib.sha256).hexdigest(),att['signature'])
 except Exception:return False

def artifact_build(slug,bid):
 data=json.dumps({'project_slug':slug,'build_id':bid},separators=(',',':')).encode()
 req=urllib.request.Request(ARTIFACT_URL+'/v1/artifacts',data=data,method='POST',headers={'Authorization':'Bearer '+ARTIFACT_TOKEN,'Content-Type':'application/json','Accept':'application/json','Host':'cloudif-artifact-executor.internal'})
 with urllib.request.urlopen(req,timeout=950) as r:return json.load(r)

def workspace_static(slug,ref,bid):
 data=json.dumps({'project_slug':slug,'ref':ref,'trace_id':bid}).encode()
 req=urllib.request.Request(WORKSPACE_URL+'/v1/test-static',data=data,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
def reserve(a):
 for k in ('project_slug','ref','framework','build_plan_digest'):
  if k not in a: raise ValueError('missing_'+k)
 if not SLUG.fullmatch(a['project_slug']) or not REF.fullmatch(a['ref']): raise ValueError('invalid_identifier')
 if a['framework']!='static': raise ValueError('framework_execution_not_ready')
 if not re.fullmatch(r'[0-9a-f]{64}',a['build_plan_digest']): raise ValueError('invalid_plan_digest')
 if not validate_plan(a['framework'],a['build_plan_digest']): raise ValueError('build_plan_digest_mismatch')
 k=idem(a); c=db(); row=c.execute('SELECT * FROM builds WHERE idempotency_key=?',(k,)).fetchone()
 if row:return dict(row)
 bid=str(uuid.uuid4()); t=now()
 c.execute('INSERT INTO builds(id,idempotency_key,project_slug,ref,framework,plan_digest,status,created_at,updated_at,lease_until,attempts,result_json,log_text,next_attempt_at,dead_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,k,a['project_slug'],a['ref'],a['framework'],a['build_plan_digest'],'queued',t,t,0,0,None,'reserved\n',t,None))
 c.commit(); return dict(c.execute('SELECT * FROM builds WHERE id=?',(bid,)).fetchone())
def drain_one():
 c=db(); t=now(); c.execute('BEGIN IMMEDIATE')
 row=c.execute("SELECT * FROM builds b WHERE ((b.status='queued' AND b.next_attempt_at<=?) OR (b.status='running' AND b.lease_until<?)) AND NOT EXISTS (SELECT 1 FROM builds a WHERE a.project_slug=b.project_slug AND a.status='running' AND a.id<>b.id AND a.lease_until>=?) ORDER BY b.created_at LIMIT 1",(t,t,t)).fetchone()
 if not row: c.commit(); return {'ok':True,'processed':False}
 bid=row['id']; c.execute("UPDATE builds SET status='running',lease_until=?,attempts=attempts+1,updated_at=?,log_text=log_text||? WHERE id=?",(t+1200,t,'effect:start\n',bid)); c.commit()
 try:
  res=workspace_static(row['project_slug'],row['ref'],bid)
  valid=bool((res.get('result') or {}).get('valid'))
  source_digest=hashlib.sha256(json.dumps(res,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  if not valid:
   status='failed';summary={'valid':False,'workspace_profile':'test-static','immutable_source_digest':source_digest,'image_created':False,'sbom_ready':False,'scanner_ready':False,'production_ready':False,'secrets_exposed':False}
  else:
   art=artifact_build(row['project_slug'],bid)
   artifact_ok=bool(art.get('ok') and art.get('production_ready') and art.get('sbom_ready') and art.get('scanner_ready') and not art.get('scanner_blocked'))
   status='succeeded' if artifact_ok else 'failed'
   summary={'valid':True,'workspace_profile':'test-static','immutable_source_digest':source_digest,'image_created':bool(art.get('artifact_image_id')),'artifact_image_id':art.get('artifact_image_id'),'artifact_tag':art.get('artifact_tag'),'base_image':art.get('base_image'),'sbom_ready':art.get('sbom_ready') is True,'sbom_format':art.get('sbom_format'),'sbom_spec_version':art.get('sbom_spec_version'),'sbom_components':art.get('sbom_components'),'sbom_sha256':art.get('sbom_sha256'),'scanner_ready':art.get('scanner_ready') is True,'scanner_policy':art.get('scanner_policy'),'scanner_counts':art.get('scanner_counts') or {},'scanner_sha256':art.get('scanner_sha256'),'scanner_blocked':art.get('scanner_blocked') is True,'runtime_proof':art.get('runtime_proof') or {},'production_ready':artifact_ok,'artifact_executor_idempotent':art.get('idempotent') is True,'secrets_exposed':False}
   summary['attestation']=attest(row['project_slug'],bid,summary);summary['attestation_verified']=verify_attestation(summary['attestation'])
  c=db(); c.execute('UPDATE builds SET status=?,updated_at=?,lease_until=0,result_json=?,log_text=log_text||? WHERE id=?',(status,now(),json.dumps(summary,separators=(',',':')),'artifact:'+status+'\n',bid)); c.commit()
 except Exception as e:
  c=db(); current=c.execute('SELECT attempts FROM builds WHERE id=?',(bid,)).fetchone(); attempts=int(current[0] if current else 1)
  if attempts < 3:
   delay=min(300,15*(2**(attempts-1))); status='queued'; nxt=now()+delay; reason=None; log='retry:scheduled delay='+str(delay)+'\n'
  else:
   status='dead_letter'; nxt=0; reason='max_attempts_exceeded'; log='dead-letter:max-attempts\n'
  c.execute('UPDATE builds SET status=?,updated_at=?,lease_until=0,next_attempt_at=?,dead_reason=?,result_json=?,log_text=log_text||? WHERE id=?',(status,now(),nxt,reason,json.dumps({'error':'build_execution_failed','retryable':status=='queued','secrets_exposed':False}),sanitize(log),bid)); c.commit()
 return {'ok':True,'processed':True,'build_id':bid}
def getrow(slug,bid):
 c=db(); r=c.execute('SELECT * FROM builds WHERE project_slug=? AND id=?',(slug,bid)).fetchone()
 if not r:return None
 d=dict(r); d['result']=json.loads(d.pop('result_json') or 'null');
 if isinstance(d['result'],dict) and d['result'].get('attestation'):
  d['result']['attestation_verified']=verify_attestation(d['result']['attestation'])
 d.pop('idempotency_key',None); d.pop('lease_until',None); d['retry_scheduled']=d.get('status')=='queued' and int(d.get('attempts') or 0)>0; d['dead_letter']=d.get('status')=='dead_letter'; d['secrets_exposed']=False; return d
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def structured_error(code,message,field='',example=None,allowed=None):
 error={'code':code,'message':message}
 if field:error['field']=field
 if example is not None:error['example']=example
 if allowed is not None:error['allowedValues']=allowed
 return error
def internal_json(method,url,token,payload=None,timeout=90):
 raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
 req=urllib.request.Request(url,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as error:
  try:data=json.load(error)
  except Exception:data={'ok':False,'error':{'code':'internal_http_error','message':'Falha em serviço interno.'}}
  return error.code,data
def project_configuration(slug):
 code,data=internal_json('GET',PROJECT_CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration',PROJECT_CONFIG_TOKEN,timeout=30)
 if code!=200 or not data.get('ok'):raise ValueError('configuration_unavailable')
 return data
def source_detection(slug,ref,trace):
 code,data=internal_json('POST',WORKSPACE_URL+'/v1/detect-multiservice',WORKSPACE_TOKEN,{'project_slug':slug,'ref':ref,'trace_id':trace},timeout=180)
 if code!=200 or not data.get('ok'):
  error=data.get('error') or {};raise ValueError(str(error.get('code') if isinstance(error,dict) else error or 'source_detection_failed'))
 return data.get('result') or data
def multiservice_runtime_policy(runtime,version):
 runtime=str(runtime or '').lower();version=str(version or '')
 if runtime=='static':return {'status':'ready','builder':STATIC_BASE,'runtimeImage':STATIC_BASE,'reason':'approved_static_digest'}
 if runtime=='node' and version=='24':return {'status':'ready','builder':NODE24_BUILDER,'runtimeImage':NODE24_RUNTIME,'reason':'node24_homologated'}
 if runtime=='node':return {'status':'blocked','reason':'node_version_not_homologated','allowedVersions':['24']}
 if runtime=='php':return {'status':'blocked','reason':'php_base_failed_security_scan','scannerCounts':{'HIGH':17,'CRITICAL':1}}
 if runtime in {'docker','compose'}:return {'status':'blocked','reason':'custom_container_policy_not_enabled_in_phase4'}
 return {'status':'blocked','reason':'runtime_not_supported'}
def normalize_command(value,field):
 if value is None or value=='':return None
 if not isinstance(value,list) or not value or len(value)>32:raise ValueError('invalid_command:'+field)
 result=[str(item) for item in value]
 if any(not item or len(item)>512 for item in result):raise ValueError('invalid_command:'+field)
 return result
def normalized_multiservice_services(configuration):
 raw_services=configuration.get('services') or {}
 if not isinstance(raw_services,dict) or not raw_services:raise ValueError('services_required')
 if len(raw_services)>16:raise ValueError('service_limit_exceeded')
 hooks=configuration.get('hooks') or {};services=[]
 root_children={str(cfg.get('path') or '.').split('/')[0] for cfg in raw_services.values() if isinstance(cfg,dict) and str(cfg.get('path') or '.')!='.'}
 for name,cfg in raw_services.items():
  if not isinstance(cfg,dict):raise ValueError('invalid_service:'+str(name))
  path=str(cfg.get('path') or '.');runtime=str(cfg.get('runtime') or '').lower();version=str(cfg.get('version') or '') or None
  health=cfg.get('healthcheck');health_path=str(health.get('path') or '') if isinstance(health,dict) else str(health or '')
  hook_steps=[]
  for phase in ('preBuild','postBuild'):
   values=hooks.get(phase) or []
   if not isinstance(values,list):continue
   for item in values:
    if isinstance(item,dict) and str(item.get('service') or '')==str(name) and item.get('script'):
     hook_steps.append({'phase':phase,'path':str(item['script'])})
  service={'name':str(name),'path':path,'runtime':runtime,'version':version,
   'install':normalize_command(cfg.get('install'),f'services.{name}.install'),'build':normalize_command(cfg.get('build'),f'services.{name}.build'),
   'start':normalize_command(cfg.get('start'),f'services.{name}.start'),'publish':cfg.get('publish'),'port':cfg.get('port'),
   'healthcheck':health_path or None,'hookSteps':hook_steps,'excludePaths':sorted(root_children) if path=='.' else []}
  service['policy']=multiservice_runtime_policy(runtime,version)
  services.append(service)
 return services
def reusable_multiservice(plan_digest):
 c=db();row=c.execute("select job_id,result_json from multiservice_jobs where plan_digest=? and status='succeeded' order by updated_at desc limit 1",(plan_digest,)).fetchone();c.close()
 if not row:return None
 return {'job_id':row['job_id'],'result':json.loads(row['result_json'] or '{}')}
def multiservice_plan(payload):
 if not isinstance(payload,dict):raise ValueError('invalid_request')
 slug=str(payload.get('project_slug') or '').strip();ref=str(payload.get('ref') or 'main').strip();expected=int(payload.get('expected_revision') or 0);trace=str(payload.get('trace_id') or 'build-plan')[:128]
 if not SLUG.fullmatch(slug):raise ValueError('invalid_project_slug')
 if not REF.fullmatch(ref) or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('invalid_ref')
 config=project_configuration(slug);actual=int(config.get('currentRevision') or 0)
 if actual<1:raise ValueError('configuration_required')
 if expected and expected!=actual:raise ValueError('configuration_revision_mismatch')
 detection=source_detection(slug,ref,trace);archive=str(detection.get('archiveSha256') or '').lower()
 if not re.fullmatch(r'[a-f0-9]{64}',archive):raise ValueError('archive_digest_missing')
 configuration=config.get('configuration') or {}
 services=normalized_multiservice_services(configuration)
 toolchain=configuration.get('toolchain') or {}
 toolchain_validations=[]
 for item in services:
  validation=validate_toolchain(toolchain,item['runtime'],item.get('version'),catalog_path=TOOLCHAIN_CATALOG)
  toolchain_validations.append({'service':item['name'],**validation})
 blocked=[{'service':item['name'],**item['policy']} for item in services if item['policy']['status']!='ready']
 for validation in toolchain_validations:
  for issue in validation.get('blockers') or []:blocked.append({'service':validation['service'],**issue})
 material={'project_slug':slug,'ref':ref,'config_revision':actual,'config_digest':config.get('configDigest'),'toolchain_digest':config.get('toolchainDigest'),'archive_sha256':archive,'services':services,'toolchain':toolchain,'toolchain_validations':[{key:value for key,value in item.items() if key not in {'warnings'}} for item in toolchain_validations]}
 plan_digest=hashlib.sha256(canonical(material)).hexdigest();reusable=reusable_multiservice(plan_digest)
 summary={'projectType':configuration.get('project',{}).get('type') or detection.get('projectType'),'serviceCount':len(services),'componentCount':detection.get('componentCount'),'networkPolicy':str((((toolchain.get('provision') or {}).get('network') or {'mode':'none'}).get('mode') if isinstance((toolchain.get('provision') or {}).get('network'),dict) else (toolchain.get('provision') or {}).get('network') or 'none')),'scannerPolicy':'block-high-critical','signatureAlgorithm':'Ed25519','secretsIncluded':False,'toolchainCatalogVersion':int(load_catalog(TOOLCHAIN_CATALOG).get('version') or 0),'sourceValidationRequired':any(item.get('script',{}).get('ok') is None for item in toolchain_validations)}
 return {'ok':True,'side_effect_free':True,'project_slug':slug,'ref':ref,'config_revision':actual,'config_digest':config.get('configDigest'),'toolchain_digest':config.get('toolchainDigest'),'archive_sha256':archive,'plan_digest':plan_digest,'services':services,'toolchain':toolchain,'toolchain_validations':toolchain_validations,'blocked':blocked,'policies':[item['policy'] for item in services],'summary':summary,'approval_required':not blocked and reusable is None,'build_required':reusable is None,'reusable_build':bool(reusable),'reusable':reusable,'secret_values_included':False}
def artifact_multiservice_build(request):
 payload={**request,'profile':'multiservice-v1'}
 code,data=internal_json('POST',ARTIFACT_URL+'/v1/multiservice/build',ARTIFACT_TOKEN,payload,timeout=3600)
 if code!=200 or not data.get('ok'):
  error=data.get('error') or {};message=error.get('message') if isinstance(error,dict) else str(error)
  raise RuntimeError(message or 'multiservice_artifact_failed')
 return data
def run_multiservice_job(job_id):
 c=db();row=c.execute('select * from multiservice_jobs where job_id=?',(job_id,)).fetchone()
 if not row:c.close();return
 if row['status'] not in {'queued','running'}:c.close();return
 c.execute("update multiservice_jobs set status='running',attempts=attempts+1,updated_at=? where job_id=?",(now(),job_id));c.commit();payload=json.loads(row['payload_json']);c.close()
 try:
  result=artifact_multiservice_build(payload);status='succeeded'
  c=db();c.execute('update multiservice_jobs set status=?,result_json=?,last_error=?,updated_at=? where job_id=?',(status,json.dumps(result,ensure_ascii=False,separators=(',',':')),'',now(),job_id));c.commit();c.close()
 except Exception as exc:
  c=db();c.execute('update multiservice_jobs set status=?,last_error=?,result_json=?,updated_at=? where job_id=?',('failed',sanitize(str(exc)),json.dumps({'ok':False,'error':{'code':'multiservice_build_failed','message':'O build multissserviço falhou.'},'secrets_exposed':False},separators=(',',':')),now(),job_id));c.commit();c.close()
def queue_multiservice(payload):
 if not isinstance(payload,dict):raise ValueError('invalid_request')
 if payload.get('approved') is not True:raise PermissionError('approval_required')
 plan=multiservice_plan(payload);provided=str(payload.get('plan_digest') or '').lower()
 if not hmac.compare_digest(plan['plan_digest'],provided):raise ValueError('plan_digest_mismatch')
 if plan['blocked']:raise ValueError('runtime_policy_blocked')
 key=hashlib.sha256((plan['project_slug']+'|'+plan['ref']+'|'+provided).encode()).hexdigest();c=db();row=c.execute('select * from multiservice_jobs where idempotency_key=?',(key,)).fetchone()
 if row:c.close();return {'ok':True,'job_id':row['job_id'],'status':row['status'],'idempotent':True,'plan_digest':provided}
 job_id='build_'+secrets.token_hex(12);t=now();request={'job_id':job_id,'project_slug':plan['project_slug'],'ref':plan['ref'],'archive_sha256':plan['archive_sha256'],'config_revision':plan['config_revision'],'config_digest':plan['config_digest'],'toolchain_digest':plan['toolchain_digest'],'plan_digest':provided,'services':plan['services'],'toolchain':plan.get('toolchain') or {},'trace_id':str(payload.get('trace_id') or job_id)}
 c.execute('insert into multiservice_jobs(job_id,idempotency_key,project_slug,ref,config_revision,config_digest,toolchain_digest,archive_sha256,plan_digest,status,payload_json,result_json,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,key,plan['project_slug'],plan['ref'],plan['config_revision'],plan['config_digest'],plan['toolchain_digest'],plan['archive_sha256'],provided,'queued',json.dumps(request,ensure_ascii=False,separators=(',',':')),'{}',t,t));c.commit();c.close()
 threading.Thread(target=run_multiservice_job,args=(job_id,),daemon=True).start()
 return {'ok':True,'job_id':job_id,'status':'queued','idempotent':False,'plan_digest':provided,'config_revision':plan['config_revision'],'archive_sha256':plan['archive_sha256']}
def multiservice_status(job_id):
 if not re.fullmatch(r'build_[a-f0-9]{24}',str(job_id or '')):raise ValueError('invalid_job_id')
 c=db();row=c.execute('select * from multiservice_jobs where job_id=?',(job_id,)).fetchone();c.close()
 if not row:raise LookupError('build_not_found')
 result=json.loads(row['result_json'] or '{}');payload={'project_slug':row['project_slug'],'ref':row['ref'],'config_revision':row['config_revision'],'config_digest':row['config_digest'],'toolchain_digest':row['toolchain_digest'],'archive_sha256':row['archive_sha256'],'plan_digest':row['plan_digest']}
 return {'ok':True,'job_id':job_id,'status':row['status'],'attempts':row['attempts'],'created_at':row['created_at'],'updated_at':row['updated_at'],'payload':payload,'result':result,'error':row['last_error'] or None,'secrets_exposed':False}
def recover_multiservice_jobs():
 c=db();rows=c.execute("select job_id from multiservice_jobs where status in ('queued','running') order by created_at").fetchall();c.execute("update multiservice_jobs set status='queued' where status='running'");c.commit();c.close()
 for row in rows:threading.Thread(target=run_multiservice_job,args=(row['job_id'],),daemon=True).start()

toolchain_lifecycle.configure(sys.modules[__name__])

def multiservice_runtime_config(job_id):
 if not re.fullmatch(r'build_[a-f0-9]{24}',str(job_id or '')):raise ValueError('invalid_build_job_id')
 c=db();row=c.execute('select * from multiservice_jobs where job_id=?',(job_id,)).fetchone();c.close()
 if not row:raise LookupError('multiservice_job_not_found')
 if row['status']!='succeeded':raise ValueError('multiservice_build_not_ready')
 payload=json.loads(row['payload_json'] or '{}');result=json.loads(row['result_json'] or '{}')
 effective=payload.get('effectiveEnvironment') or {}
 if not isinstance(effective,dict) or effective.get('secretValuesIncluded') is not False:
  raise ValueError('effective_environment_secret_contract_invalid')
 public_runtime=effective.get('publicRuntimeEnvironment') or {};secret_runtime=effective.get('secretRuntimeReferences') or {}
 if not isinstance(public_runtime,dict) or not isinstance(secret_runtime,dict):raise ValueError('effective_environment_runtime_contract_invalid')
 services={item.get('name') for item in payload.get('services') or [] if isinstance(item,dict)}
 for mapping in (public_runtime,secret_runtime):
  if set(mapping)-services:raise ValueError('effective_environment_unknown_service')
 for service,values in public_runtime.items():
  if not isinstance(values,dict):raise ValueError('public_runtime_environment_invalid')
  for name,value in values.items():
   if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',str(name)) or (not isinstance(value,(str,int,float,bool)) and value is not None):raise ValueError('public_runtime_environment_invalid')
 for service,values in secret_runtime.items():
  if not isinstance(values,dict):raise ValueError('secret_runtime_references_invalid')
  for name,reference in values.items():
   if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',str(name)) or not re.fullmatch(r'[a-z][a-z0-9_.+:-]{1,31}://[^\s\x00]{3,240}',str(reference or '')):raise ValueError('secret_runtime_references_invalid')
 service_artifacts=[]
 for item in result.get('services') or result.get('artifacts') or []:
  if not isinstance(item,dict):continue
  image=item.get('image') or item.get('applicationImage') or {}
  service=str(item.get('service') or item.get('name') or '')
  image_ref=str(image.get('image') or image.get('imageRef') or item.get('imageRef') or '')
  image_id=str(image.get('imageId') or item.get('imageId') or '')
  if service and image_ref and re.fullmatch(r'sha256:[a-f0-9]{64}',image_id):service_artifacts.append({'service':service,'imageRef':image_ref,'imageId':image_id})
 return {
  'ok':True,'internal':True,'job_id':job_id,'project_slug':row['project_slug'],'environment':str(payload.get('environment') or 'development'),
  'config_revision':row['config_revision'],'config_digest':row['config_digest'],'toolchain_digest':row['toolchain_digest'],'archive_sha256':row['archive_sha256'],'plan_digest':row['plan_digest'],
  'publicRuntimeEnvironment':public_runtime,'secretRuntimeReferences':secret_runtime,
  'buildEnvironmentDigest':effective.get('buildEnvironmentDigest'),'runtimeEnvironmentDigest':effective.get('runtimeEnvironmentDigest'),'environmentDigest':effective.get('environmentDigest'),
  'activeToolchainImages':payload.get('activeToolchainImages') or {},'serviceArtifacts':service_artifacts,
  'secretValuesIncluded':False,'secretReferencesIncluded':bool(any(secret_runtime.values())),'containersChanged':False,
 }


class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode(); self.send_response(n); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health': return self.sendj(200,{'ok':True,'service':'build-broker','queue':'sqlite-wal','production_ready':False,'secrets_exposed':False})
  if not auth(self.headers): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  parsed=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(parsed.query)
  mm=re.fullmatch(r'/v1/toolchain/jobs/(toolchain_[a-f0-9]{24})(/logs)?',parsed.path)
  if mm:
   try:return self.sendj(200,toolchain_lifecycle.logs(mm.group(1)) if mm.group(2) else toolchain_lifecycle.status(mm.group(1)))
   except LookupError:return self.sendj(404,{'ok':False,'error':{'code':'toolchain_job_not_found','message':'Job de toolchain não encontrado.'}})
   except ValueError as error:return self.sendj(400,{'ok':False,'error':{'code':str(error),'message':'job_id inválido.'}})
  image_list=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/toolchain/images',parsed.path)
  if image_list:
   try:return self.sendj(200,toolchain_lifecycle.images(image_list.group(1),(query.get('service') or [''])[0]))
   except ValueError as error:return self.sendj(400,{'ok':False,'error':{'code':str(error)}})
  image_get=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/toolchain/images/(img_[a-f0-9]{24})',parsed.path)
  if image_get:
   try:return self.sendj(200,toolchain_lifecycle.image_get(*image_get.groups()))
   except LookupError:return self.sendj(404,{'ok':False,'error':{'code':'toolchain_image_not_found'}})
  toolchain_get_match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/toolchain',parsed.path)
  if toolchain_get_match:
   try:return self.sendj(200,toolchain_lifecycle.get(toolchain_get_match.group(1),(query.get('ref') or ['main'])[0]))
   except ValueError as error:return self.sendj(422,{'ok':False,'error':{'code':str(error),'message':'Configuração da toolchain inválida.'}})
  runtime_config_match=re.fullmatch(r'/v1/multiservice/jobs/(build_[a-f0-9]{24})/runtime-config',parsed.path)
  if runtime_config_match:
   try:return self.sendj(200,multiservice_runtime_config(runtime_config_match.group(1)))
   except LookupError:return self.sendj(404,{'ok':False,'error':{'code':'multiservice_job_not_found'}})
   except ValueError as error:return self.sendj(409,{'ok':False,'error':{'code':str(error),'message':'O runtime do build não está disponível.'}})
  mm=re.fullmatch(r'/v1/multiservice/jobs/(build_[a-f0-9]{24})',parsed.path)
  if mm:
   try:return self.sendj(200,multiservice_status(mm.group(1)))
   except LookupError:return self.sendj(404,{'ok':False,'error':{'code':'build_not_found','message':'Build não encontrado.'}})
   except ValueError as error:return self.sendj(400,{'ok':False,'error':{'code':str(error),'message':'job_id inválido.'}})
  m=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/builds/([0-9a-f-]+)(/logs|/artifact)?',self.path)
  if not m:return self.sendj(404,{'ok':False,'error':'not_found'})
  r=getrow(m.group(1),m.group(2))
  if not r:return self.sendj(404,{'ok':False,'error':'build_not_found'})
  if m.group(3)=='/logs': return self.sendj(200,{'ok':True,'project_slug':m.group(1),'build_id':r['id'],'logs':sanitize(r.pop('log_text','')),'secrets_exposed':False})
  if m.group(3)=='/artifact': return self.sendj(200,{'ok':True,'project_slug':m.group(1),'build_id':r['id'],'artifact':r.get('result'),'attestation_verified':bool((r.get('result') or {}).get('attestation_verified')),'downloadable':False,'secrets_exposed':False})
  r.pop('log_text',None); return self.sendj(200,{'ok':True,'build':r})
 def do_POST(self):
  if self.path=='/internal/drain':
   if not worker_auth(self.headers):return self.sendj(401,{'ok':False,'error':'worker_unauthorized'})
   return self.sendj(200,drain_one())
  if not auth(self.headers): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except Exception:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/plan':
    framework=str(a.get('framework') or '')
    data=json.dumps({'framework':framework},separators=(',',':')).encode()
    request=urllib.request.Request(RUNTIME_URL+'/v1/plan',data=data,method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=15) as response:return self.sendj(200,json.load(response))
   if self.path=='/v1/execute':
    r=reserve(a);return self.sendj(202,{'ok':True,'phase':'reserve','build_id':r['id'],'status':r['status'],'idempotent':True,'secrets_exposed':False})
   if self.path=='/v1/builds':
    r=reserve(a); return self.sendj(202,{'ok':True,'phase':'reserve','build_id':r['id'],'status':r['status'],'idempotent':True,'secrets_exposed':False})
   if self.path=='/v1/toolchain/plan':return self.sendj(200,toolchain_lifecycle.plan(a))
   if self.path=='/v1/toolchain/validate':return self.sendj(200,toolchain_lifecycle.validate(a))
   if self.path=='/v1/toolchain/build':return self.sendj(202,toolchain_lifecycle.queue(a))
   if self.path=='/v1/toolchain/activation/plan':return self.sendj(200,toolchain_lifecycle.activation_plan(a))
   if self.path=='/v1/toolchain/activation/apply':return self.sendj(200,toolchain_lifecycle.activation_apply(a))
   if self.path=='/v1/multiservice/plan':return self.sendj(200,multiservice_plan(a))
   if self.path=='/v1/multiservice/execute':return self.sendj(202,queue_multiservice(a))
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except PermissionError as e:return self.sendj(403,{'ok':False,'error':{'code':str(e),'message':'Aprovação humana obrigatória.'}})
  except LookupError as e:return self.sendj(404,{'ok':False,'error':{'code':str(e),'message':'Recurso não encontrado.'}})
  except ValueError as e:return self.sendj(422,{'ok':False,'error':{'code':str(e),'message':'A solicitação contém campos ausentes ou incompatíveis.'}})
if __name__=='__main__':
 init_db();recover_multiservice_jobs();toolchain_lifecycle.recover_jobs()
 if len(sys.argv)>1 and sys.argv[1]=='drain': print(json.dumps(drain_one()))
 else: ThreadingHTTPServer((HOST,PORT),H).serve_forever()
