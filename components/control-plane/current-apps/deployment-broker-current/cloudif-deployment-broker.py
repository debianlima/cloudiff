#!/usr/bin/env python3
import datetime as dt, hashlib, hmac, json, os, re, sys, urllib.parse, urllib.request, sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0,'/srv/cloudif/lib')
try:
 import cloudif_release_manager as rm
except ModuleNotFoundError:
 local_lib=Path(__file__).resolve().parents[2]/'srv/cloudif/lib'
 if str(local_lib) not in sys.path:sys.path.insert(0,str(local_lib))
 import cloudif_release_manager as rm
HOST=os.environ.get('CLOUDIF_DEPLOYMENT_BROKER_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_DEPLOYMENT_BROKER_PORT','18207'))
TOKEN=os.environ.get('CLOUDIF_DEPLOYMENT_BROKER_TOKEN','')
IDEMPOTENCY_DB=Path(os.environ.get('CLOUDIF_DEPLOYMENT_IDEMPOTENCY_DB','/var/lib/cloudif/portal/deployment-broker-idempotency.db'))
EXECUTION_ID=re.compile(r'^exec_[a-f0-9]{24,64}$')
SLUG=re.compile(r'^[a-z0-9][a-z0-9._-]{0,62}$')
COMMIT=re.compile(r'^[0-9a-f]{40}$')
VERSION=re.compile(r'^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?$')

def send(h,code,obj):
 b=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode();h.send_response(code);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(b)));h.end_headers();h.wfile.write(b)
def auth(h):
 got=h.headers.get('Authorization','')
 return bool(TOKEN) and hmac.compare_digest(got,'Bearer '+TOKEN)
def body(h):
 try:n=int(h.headers.get('Content-Length','0'))
 except Exception:raise ValueError('invalid_length')
 if n<2 or n>16384:raise ValueError('invalid_length')
 raw=h.rfile.read(n);data=json.loads(raw)
 if not isinstance(data,dict):raise ValueError('invalid_json')
 return data
def idem_connect():
 IDEMPOTENCY_DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(IDEMPOTENCY_DB,timeout=30,isolation_level=None)
 c.row_factory=sqlite3.Row
 c.execute('pragma busy_timeout=30000')
 c.execute('pragma journal_mode=wal')
 c.execute("create table if not exists executions(execution_id text primary key,operation text not null,payload_digest text not null,state text not null,http_code integer,response_json text,effect_started integer not null default 0,created_at text not null,updated_at text not null)")
 return c
def idem_digest(operation,payload):
 canonical={'operation':operation,'payload':payload}
 return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def idem_begin(execution_id,operation,payload):
 if not execution_id:return {'mode':'legacy'}
 if not EXECUTION_ID.fullmatch(execution_id):raise ValueError('invalid_execution_id')
 digest=idem_digest(operation,payload);c=idem_connect();now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat();c.execute('begin immediate')
 row=c.execute('select * from executions where execution_id=?',(execution_id,)).fetchone()
 if row:
  if row['payload_digest']!=digest or row['operation']!=operation:
   c.rollback();c.close();return {'mode':'conflict'}
  if row['state']=='finished':
   out={'mode':'replay','http_code':int(row['http_code']),'response':json.loads(row['response_json']),'effect_started':bool(row['effect_started'])};c.commit();c.close();return out
  c.commit();c.close();return {'mode':'in_progress'}
 c.execute('insert into executions(execution_id,operation,payload_digest,state,created_at,updated_at) values(?,?,?,?,?,?)',(execution_id,operation,digest,'in_progress',now,now));c.commit();c.close();return {'mode':'new','execution_id':execution_id}
def idem_mark_effect(execution_id):
 if not execution_id:return
 c=idem_connect();c.execute('update executions set effect_started=1,updated_at=? where execution_id=? and state=?',(dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),execution_id,'in_progress'));c.close()
def idem_finish(execution_id,code,response):
 if not execution_id:return response
 out=dict(response);out['execution_id']=execution_id;out['idempotent_replay']=False
 c=idem_connect();c.execute('update executions set state=?,http_code=?,response_json=?,updated_at=? where execution_id=? and state=?',('finished',int(code),json.dumps(out,ensure_ascii=False,separators=(',',':')),dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),execution_id,'in_progress'));c.close();return out
def idem_response(state):
 if state['mode']=='conflict':return 409,{'ok':False,'error':'execution_id_conflict'}
 if state['mode']=='in_progress':return 409,{'ok':False,'error':'execution_in_progress'}
 if state['mode']=='replay':
  out=dict(state['response']);out['idempotent_replay']=True;out['effect_started']=state['effect_started'];return state['http_code'],out
 return None

def validate_common(d,allow_trace=True):
 allowed={'project_slug','commit_sha','version'}|({'trace_id'} if allow_trace else set())
 if set(d)!=allowed:raise ValueError('invalid_request')
 slug=str(d.get('project_slug') or '').strip().lower();commit=str(d.get('commit_sha') or '').strip().lower();version=str(d.get('version') or '').strip();trace=str(d.get('trace_id') or '').strip()
 if not SLUG.fullmatch(slug) or not COMMIT.fullmatch(commit) or not VERSION.fullmatch(version) or not trace:raise ValueError('invalid_request')
 setting=rm.project_setting(slug)
 if not setting:raise LookupError('project_not_reconciled')
 return slug,commit,version,trace,setting
TEST_PROJECT='sistema-de-biblioteca-teste'
PRODUCTION_TARGETS=os.environ.get('CLOUDIF_PRODUCTION_TARGETS','/etc/cloudif/production-targets.json')
HOMOLOGATION_URL=os.environ.get('CLOUDIF_PRODUCTION_HOMOLOGATION_URL','http://10.62.91.2:18217').rstrip('/')
HOMOLOGATION_TOKEN=os.environ.get('CLOUDIF_PRODUCTION_HOMOLOGATION_TOKEN','')
PROJECT_CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
PROJECT_CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
SECRET_RESOLVER_TOKEN=os.environ.get('CLOUDIF_SECRET_RESOLVER_TOKEN','')
PROJECT_RECONCILER_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILER_URL','http://127.0.0.1:18229').rstrip('/')
PROJECT_RECONCILER_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILER_TOKEN','')
BUILD_BROKER_URL=os.environ.get('CLOUDIF_BUILD_BROKER_URL','http://127.0.0.1:18213').rstrip('/')
BUILD_BROKER_TOKEN=os.environ.get('CLOUDIF_BUILD_BROKER_TOKEN','')
BUILD_JOB_RE=re.compile(r'^build_[a-f0-9]{24}$')
SHA256_RE=re.compile(r'^[a-f0-9]{64}$')
DEPLOY_ENVIRONMENTS={'homologation','production'}
SENSITIVE_ENV_RE=re.compile(r'(?i)(password|secret|token|private|jwt|service[_-]?role|api[_-]?key|access[_-]?key|signing[_-]?key)')
MULTISERVICE_DEPLOYMENT_EXECUTOR_URL=os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_URL','http://10.62.91.2:18230').rstrip('/')
MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN=os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN','')
TENANT_ROOT=Path(os.environ.get('CLOUDIF_TENANT_ROOT','/srv/cloudif/tenants'))
TENANT_DB_HOST=os.environ.get('CLOUDIF_TENANT_DB_HOST','10.62.92.7')
DEPLOYMENT_ID_RE=re.compile(r'^dep_[a-f0-9]{24}$')
TENANT_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,126}$')
ENV_NAME_RE=re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,127}$')
def _internal_json(method,url,token,payload=None,timeout=60):
 data=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
 request=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as error:
  try:value=json.load(error)
  except Exception:value={'ok':False,'error':{'code':'internal_http_error','message':'Serviço interno indisponível.'}}
  return error.code,value

def _multiservice_configuration(slug):
 code,data=_internal_json('GET',PROJECT_CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration',PROJECT_CONFIG_TOKEN,timeout=30)
 if code==404:raise LookupError('project_configuration_not_found')
 if code!=200 or not data.get('ok'):raise RuntimeError('project_configuration_unavailable')
 return data

def _multiservice_reconciliation(slug):
 code,data=_internal_json('GET',PROJECT_RECONCILER_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/state',PROJECT_RECONCILER_TOKEN,timeout=30)
 if code==404:return None
 if code!=200 or not data.get('ok'):raise RuntimeError('project_reconciliation_unavailable')
 return data

def _multiservice_build(job_id):
 if not job_id:return None
 if not BUILD_JOB_RE.fullmatch(job_id):raise ValueError('invalid_build_job_id')
 code,data=_internal_json('GET',BUILD_BROKER_URL+'/v1/multiservice/jobs/'+urllib.parse.quote(job_id,safe=''),BUILD_BROKER_TOKEN,timeout=30)
 if code==404:return None
 if code!=200 or not data.get('ok'):raise RuntimeError('multiservice_build_unavailable')
 return data

def _build_runtime_configuration(job_id):
 if not BUILD_JOB_RE.fullmatch(str(job_id or '')):raise ValueError('invalid_build_job_id')
 code,data=_internal_json('GET',BUILD_BROKER_URL+'/v1/multiservice/jobs/'+urllib.parse.quote(job_id,safe='')+'/runtime-config',BUILD_BROKER_TOKEN,timeout=30)
 if code==404:return None
 if code==409:
  error=data.get('error') or {};raise ValueError(str(error.get('code') if isinstance(error,dict) else error or 'multiservice_build_not_ready'))
 if code!=200 or not data.get('ok'):raise RuntimeError('multiservice_runtime_configuration_unavailable')
 if data.get('internal') is not True or data.get('secretValuesIncluded') is not False:raise ValueError('runtime_secret_contract_invalid')
 return data

def _resolve_runtime_secrets(slug,environment,references):
 if not SECRET_RESOLVER_TOKEN:raise RuntimeError('secret_resolver_unavailable')
 if not isinstance(references,dict):raise ValueError('invalid_secret_references')
 payload={'environment':str(environment or ''),'references':references,'actor':'deployment-broker'}
 data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
 path='/v1/projects/'+urllib.parse.quote(str(slug or ''),safe='')+'/environment/secrets/resolve-internal'
 request=urllib.request.Request(PROJECT_CONFIG_URL+path,data=data,method='POST',headers={'Authorization':'Bearer '+PROJECT_CONFIG_TOKEN,'X-CloudIF-Secret-Resolver-Token':SECRET_RESOLVER_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=30) as response:result=json.load(response)
 except urllib.error.HTTPError as error:
  try:failure=json.load(error);code=(failure.get('error') or {}).get('code') if isinstance(failure,dict) else ''
  except Exception:code=''
  raise RuntimeError(str(code or 'secret_resolution_failed')) from error
 except Exception as error:
  if isinstance(error,RuntimeError):raise
  raise RuntimeError('secret_resolution_failed') from error
 if not isinstance(result,dict) or result.get('ok') is not True or result.get('internal') is not True or result.get('secretValuesIncluded') is not True:raise RuntimeError('secret_resolution_contract_invalid')
 resolved=result.get('resolvedSecrets')
 if not isinstance(resolved,dict) or set(resolved)!=set(references):raise RuntimeError('secret_resolution_scope_mismatch')
 normalized={}
 for service,expected in references.items():
  values=resolved.get(service)
  if not isinstance(expected,dict) or not isinstance(values,dict) or set(values)!=set(expected):raise RuntimeError('secret_resolution_scope_mismatch')
  normalized[str(service)]={}
  for name,value in values.items():
   if not isinstance(value,str):raise RuntimeError('secret_resolution_contract_invalid')
   normalized[str(service)][str(name)]=value
 return normalized

def _runtime_configuration_for_executor(runtime_configuration):
 if not isinstance(runtime_configuration,dict):raise ValueError('runtime_configuration_missing')
 safe=json.loads(json.dumps(runtime_configuration,ensure_ascii=False,separators=(',',':')))
 references=safe.get('secretRuntimeReferences') or {}
 if not isinstance(references,dict):raise ValueError('runtime_secret_contract_invalid')
 safe['secretRuntimeReferences']={str(service):{} for service in references}
 safe['secretValuesIncluded']=False
 return safe

def _merge_runtime_variables(public_runtime,resolved):
 merged={}
 for service,values in (public_runtime or {}).items():
  if not isinstance(values,dict):raise ValueError('runtime_environment_contract_invalid')
  merged[str(service)]={str(name):value for name,value in values.items()}
 for service,values in (resolved or {}).items():
  if not isinstance(values,dict):raise ValueError('runtime_secret_contract_invalid')
  target=merged.setdefault(str(service),{})
  for name,value in values.items():target[str(name)]=value
 return merged

def _deployment_runtime_summary(runtime_configuration):
 if not isinstance(runtime_configuration,dict):return {'environment':None,'variableNames':{},'secretNames':{},'digests':{},'secretReferencesPresent':False}
 public=runtime_configuration.get('publicRuntimeEnvironment') or {};secret=runtime_configuration.get('secretRuntimeReferences') or {}
 if not isinstance(public,dict) or not isinstance(secret,dict):raise ValueError('runtime_environment_contract_invalid')
 public_names={str(service):sorted(str(name) for name in values) for service,values in sorted(public.items()) if isinstance(values,dict)}
 secret_names={str(service):sorted(str(name) for name in values) for service,values in sorted(secret.items()) if isinstance(values,dict)}
 return {
  'environment':str(runtime_configuration.get('environment') or ''),
  'variableNames':public_names,'secretNames':secret_names,
  'digests':{'build':runtime_configuration.get('buildEnvironmentDigest'),'runtime':runtime_configuration.get('runtimeEnvironmentDigest'),'effective':runtime_configuration.get('environmentDigest')},
  'secretReferencesPresent':any(bool(values) for values in secret.values() if isinstance(values,dict)),
 }

def _deployment_routes(configuration,applications,requested=None):
 names={str(item.get('service') or '') for item in applications}
 if requested is not None:
  if not isinstance(requested,list) or not requested:raise ValueError('invalid_routes')
  routes=[]
  for index,item in enumerate(requested):
   if not isinstance(item,dict):raise ValueError('invalid_route')
   prefix=str(item.get('pathPrefix') or '').strip();service=str(item.get('service') or '').strip();strip=bool(item.get('stripPrefix',False))
   if not prefix.startswith('/') or '..' in prefix or '//' in prefix or service not in names:raise ValueError('invalid_route')
   if len(prefix)>1:prefix=prefix.rstrip('/')
   routes.append({'pathPrefix':prefix,'service':service,'stripPrefix':strip})
 else:
  services=configuration.get('services') or {};routes=[]
  for service_name,service in services.items():
   if service_name not in names or not isinstance(service,dict):continue
   for route in service.get('routes') or []:
    if isinstance(route,dict) and str(route.get('path') or '').startswith('/'):
     routes.append({'pathPrefix':str(route['path']).rstrip('/') or '/','service':service_name,'stripPrefix':bool(route.get('stripPrefix',False))})
  if not routes and applications:
   primary=str((configuration.get('project') or {}).get('primaryService') or applications[0].get('service') or '')
   routes=[{'pathPrefix':'/','service':primary,'stripPrefix':False}]
   routes.extend({'pathPrefix':'/'+str(item['service']),'service':str(item['service']),'stripPrefix':True} for item in applications if item.get('service')!=primary)
 prefixes=[item['pathPrefix'] for item in routes]
 if len(prefixes)!=len(set(prefixes)) or '/' not in prefixes:raise ValueError('invalid_routes')
 return sorted(routes,key=lambda item:len(item['pathPrefix']),reverse=True)

def _tenant_env(slug):
 setting=rm.project_setting(slug) or {};tenant=str(setting.get('tenant') or '').strip()
 if not TENANT_RE.fullmatch(tenant):return tenant,{}
 path=TENANT_ROOT/tenant/'.env'
 values={}
 try:
  for raw in path.read_text(encoding='utf-8',errors='strict').splitlines():
   line=raw.strip()
   if not line or line.startswith('#') or '=' not in line:continue
   key,value=line.split('=',1);key=key.strip();value=value.strip()
   if not ENV_NAME_RE.fullmatch(key):continue
   if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
   if '\x00' in value or '\n' in value or '\r' in value:continue
   values[key]=value
 except (FileNotFoundError,PermissionError,UnicodeError):pass
 return tenant,values

def _known_reference(slug,environment,reference,tenant,tenant_env):
 ref=str(reference or '').strip()
 public_url=str(tenant_env.get('SUPABASE_PUBLIC_URL') or tenant_env.get('API_EXTERNAL_URL') or (f'https://{tenant}.cloudiff.duckdns.org' if tenant else ''))
 if ref=='project.slug':return slug
 if ref=='deployment.environment':return environment
 if ref=='supabase.public_url':return public_url
 if ref=='supabase.anon_key':return str(tenant_env.get('ANON_KEY') or tenant_env.get('SUPABASE_ANON_KEY') or '')
 if ref=='supabase.service_role_key':return str(tenant_env.get('SERVICE_ROLE_KEY') or tenant_env.get('SUPABASE_SERVICE_KEY') or '')
 if ref=='supabase.jwt_secret':return str(tenant_env.get('JWT_SECRET') or '')
 if ref=='supabase.database_url':
  password=str(tenant_env.get('POSTGRES_PASSWORD') or '');port=str(tenant_env.get('POSTGRES_PORT') or '')
  if not password or not port.isdigit():return ''
  return 'postgresql://postgres:'+urllib.parse.quote(password,safe='')+'@'+TENANT_DB_HOST+':'+port+'/postgres'
 return ''

def _resolve_environment(slug,environment,configuration):
 global_env=configuration.get('environment') or {};global_values=global_env.get('variables') or {};required=global_env.get('required') or {};services=configuration.get('services') or {}
 tenant,tenant_env=_tenant_env(slug);values={};references=[];unresolved=[]
 for service_name,service in services.items():
  service_env=(service.get('environment') or {}) if isinstance(service,dict) else {}
  merged={str(name):str(value) for name,value in {**global_values,**(service_env.get('variables') or {})}.items()}
  values[str(service_name)]=merged
 for name,spec in required.items():
  spec=spec if isinstance(spec,dict) else {};reference=str(spec.get('secretRef') or spec.get('configRef') or '');targets=sorted(str(x) for x in (spec.get('services') or services.keys()));kind='secret' if spec.get('secretRef') else 'config'
  resolved=_known_reference(slug,environment,reference,tenant,tenant_env) if reference else ''
  references.append({'name':str(name),'kind':kind,'services':targets,'configured':bool(reference),'resolved':bool(resolved)})
  if not reference:unresolved.append({'name':str(name),'services':targets,'reason':'reference_missing'})
  elif not resolved:unresolved.append({'name':str(name),'services':targets,'reason':'reference_unresolved','referenceType':kind})
  else:
   for target in targets:
    if target not in values:unresolved.append({'name':str(name),'service':target,'reason':'service_not_found'})
    else:values[target][str(name)]=resolved
 for service_name,service in services.items():
  service_env=(service.get('environment') or {}) if isinstance(service,dict) else {}
  for name in service_env.get('required') or []:
   if str(name) not in values.get(str(service_name),{}):unresolved.append({'name':str(name),'service':str(service_name),'reason':'value_unresolved'})
 value_digests={service:{name:hashlib.sha256(value.encode()).hexdigest() for name,value in sorted(items.items())} for service,items in sorted(values.items())}
 variables_digest=hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'values':values,'variableNames':{service:sorted(items) for service,items in values.items()},'valueDigests':value_digests,'variablesDigest':variables_digest,'references':references,'unresolved':unresolved,'tenantConfigured':bool(tenant),'secretValuesIncluded':False}

def _environment_summary(slug,environment,configuration):
 resolved=_resolve_environment(slug,environment,configuration)
 return {key:resolved[key] for key in ('variableNames','valueDigests','variablesDigest','references','unresolved','tenantConfigured','secretValuesIncluded')}


def _multiservice_applications(build):
 if not build or build.get('status')!='succeeded':return []
 result=build.get('result') or {};applications=[]
 for raw in result.get('applications') or []:
  image=(raw.get('image') or {}).get('immutableReference') or (raw.get('image') or {}).get('id') or ''
  item={'service':str(raw.get('service') or ''),'imageId':str(image),'applicationDigest':str(raw.get('applicationDigest') or ''),'runtime':str(raw.get('runtime') or ''),'port':int(raw.get('containerPort') or 0),'healthcheck':str(raw.get('healthcheck') or '/')}
  applications.append(item)
 return applications

def multiservice_plan(payload,include_internal=False):
 allowed={'project_slug','build_job_id','environment','routes','trace_id'}
 if not isinstance(payload,dict) or not set(payload).issubset(allowed) or 'project_slug' not in payload or 'environment' not in payload or 'trace_id' not in payload:raise ValueError('invalid_request')
 slug=str(payload.get('project_slug') or '').strip().lower();environment=str(payload.get('environment') or '').strip().lower();trace=str(payload.get('trace_id') or '').strip();build_job_id=str(payload.get('build_job_id') or '').strip()
 if not SLUG.fullmatch(slug) or environment not in DEPLOY_ENVIRONMENTS or not trace:raise ValueError('invalid_request')
 if build_job_id and not BUILD_JOB_RE.fullmatch(build_job_id):raise ValueError('invalid_build_job_id')
 config=_multiservice_configuration(slug);configuration=config.get('configuration') or {};state=_multiservice_reconciliation(slug)
 blockers=[]
 if not config.get('configured') or int(config.get('currentRevision') or 0)<1:blockers.append('configuration-required')
 if not state:blockers.append('reconciliation-state-missing')
 elif state.get('status')!='ready':blockers.append('reconciliation-not-ready:'+str(state.get('status') or 'unknown'))
 build=None;runtime_configuration=None
 if not build_job_id:
  blockers.append('build-job-required')
 else:
  build=_multiservice_build(build_job_id)
  if not build:blockers.append('build-not-found')
  elif build.get('status')!='succeeded':blockers.append('build-not-succeeded')
  else:
   try:runtime_configuration=_build_runtime_configuration(build_job_id)
   except ValueError as error:
    code=str(error);blockers.append('build-not-ready' if code=='multiservice_build_not_ready' else code.replace('_','-'))
   if runtime_configuration is None:blockers.append('build-runtime-configuration-missing')
 applications=_multiservice_applications(build)
 runtime_summary=_deployment_runtime_summary(runtime_configuration)
 if runtime_configuration:
  if str(runtime_configuration.get('project_slug') or '')!=slug:blockers.append('build-project-mismatch')
  if str(runtime_configuration.get('environment') or '')!=environment:blockers.append('build-environment-mismatch')
  if int(runtime_configuration.get('config_revision') or 0)!=int(config.get('currentRevision') or 0):blockers.append('build-config-revision-mismatch')
  if str(runtime_configuration.get('config_digest') or '')!=str(config.get('configDigest') or ''):blockers.append('build-config-digest-mismatch')
  if str(runtime_configuration.get('toolchain_digest') or '')!=str(config.get('toolchainDigest') or ''):blockers.append('build-toolchain-digest-mismatch')
  if runtime_summary.get('secretReferencesPresent') and not SECRET_RESOLVER_TOKEN:blockers.append('secret-resolver-unavailable')
 if not applications and build and build.get('status')=='succeeded':blockers.append('build-applications-missing')
 try:routes=_deployment_routes(configuration,applications,payload.get('routes')) if applications else []
 except ValueError:routes=[];blockers.append('routes-invalid')
 if environment=='production':
  cfg=_production_config(slug)
  if cfg.get('enabled') is not True or cfg.get('production_effects_enabled') is not True:blockers.append('production-target-not-enabled')
 public_runtime=(runtime_configuration or {}).get('publicRuntimeEnvironment') or {}
 variables_digest=hashlib.sha256(json.dumps(public_runtime,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 build_result=(build or {}).get('result') or {};build_payload=(build or {}).get('payload') or {}
 material={
  'action':'deployment.multiservice.deploy','project_slug':slug,'environment':environment,'build_job_id':build_job_id,
  'build_plan_digest':str((runtime_configuration or {}).get('plan_digest') or build_result.get('planDigest') or ''),
  'config_revision':int(config.get('currentRevision') or 0),'config_digest':str(config.get('configDigest') or ''),'toolchain_digest':str(config.get('toolchainDigest') or ''),
  'archive_sha256':str((runtime_configuration or {}).get('archive_sha256') or build_payload.get('archive_sha256') or build_result.get('archiveSha256') or ''),
  'environment_digest':str((runtime_configuration or {}).get('environmentDigest') or ''),'runtime_environment_digest':str((runtime_configuration or {}).get('runtimeEnvironmentDigest') or ''),
  'applications':applications,'routes':routes,'variables_digest':variables_digest,
 }
 plan_digest=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest();blockers=sorted(set(blockers))
 summary={'technologies':sorted({item['runtime'] for item in applications if item.get('runtime')}),'services':[{'service':item['service'],'runtime':item['runtime'],'port':item['port'],'healthcheck':item['healthcheck']} for item in applications],'routes':routes,'runtimeEnvironment':runtime_summary,'buildJobId':build_job_id,'secretResolutionRequired':bool(runtime_summary.get('secretReferencesPresent')),'secretResolverAvailable':bool(SECRET_RESOLVER_TOKEN),'hooks':[{'phase':phase,'service':item.get('service'),'script':item.get('script')} for phase,items in (configuration.get('hooks') or {}).items() for item in (items or []) if isinstance(item,dict)]}
 base={'ok':True,'side_effect_free':True,'project_slug':slug,'environment':environment,'build_job_id':build_job_id,'deployment_plan_digest':plan_digest,'operation':material,'summary':summary,'blockers':blockers,'execution_allowed':not blockers,'approval_required':True,'reconciliation':{'status':(state or {}).get('status'),'configRevision':(state or {}).get('configRevision'),'membershipRevision':(state or {}).get('membershipRevision'),'aclDigest':(state or {}).get('aclDigest')},'variables_digest':variables_digest,'secret_values_included':False,'secret_references_included':False,'secretValuesIncluded':False,'secretReferencesIncluded':False,'containers_created':False,'trace_id':trace}
 if include_internal:base['_internal_runtime_configuration']=runtime_configuration
 return base

def _multiservice_deployment_plan(payload,include_internal=False):
 return multiservice_plan(payload,include_internal=include_internal)


def _deployment_executor_call(method,path,payload=None,timeout=300):
 data=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
 request=urllib.request.Request(MULTISERVICE_DEPLOYMENT_EXECUTOR_URL+path,data=data,method=method,headers={'Authorization':'Bearer '+MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as error:
  try:value=json.load(error)
  except Exception:value={'ok':False,'error':{'code':'deployment_executor_error','message':'Falha no executor de deploy.'}}
  return error.code,value
 except Exception:return 599,{'ok':False,'error':{'code':'deployment_executor_unavailable','message':'Executor de deploy indisponível.'}}

def _deployment_id(execution_id):
 return 'dep_'+hashlib.sha256(execution_id.encode()).hexdigest()[:24]

def _multiservice_execute(d,execution_id):
 allowed={'project_slug','build_job_id','environment','routes','trace_id','deployment_plan_digest'}
 if not isinstance(d,dict) or not set(d).issubset(allowed) or not {'project_slug','build_job_id','environment','trace_id','deployment_plan_digest'}.issubset(d):raise ValueError('invalid_request')
 build_job_id=str(d.get('build_job_id') or '').strip()
 if not BUILD_JOB_RE.fullmatch(build_job_id):raise ValueError('invalid_build_job_id')
 plan_payload={key:d[key] for key in ('project_slug','build_job_id','environment','trace_id')}
 if d.get('routes') is not None:plan_payload['routes']=d['routes']
 plan=_multiservice_deployment_plan(plan_payload,include_internal=True);digest=str(d.get('deployment_plan_digest') or '').lower()
 if not SHA256_RE.fullmatch(digest) or not hmac.compare_digest(digest,plan['deployment_plan_digest']):raise ValueError('deployment_plan_digest_mismatch')
 if not plan.get('execution_allowed'):raise PermissionError('deployment_plan_blocked:'+','.join(plan.get('blockers') or []))
 runtime_configuration=plan.pop('_internal_runtime_configuration',None)
 if not isinstance(runtime_configuration,dict):raise ValueError('runtime_configuration_missing')
 if runtime_configuration.get('secretValuesIncluded') is not False:raise ValueError('runtime_secret_contract_invalid')
 public_runtime=runtime_configuration.get('publicRuntimeEnvironment') or {};references=runtime_configuration.get('secretRuntimeReferences') or {}
 approved_variables_digest=hashlib.sha256(json.dumps(public_runtime,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if not hmac.compare_digest(approved_variables_digest,str(plan.get('variables_digest') or '')):raise ValueError('variables_digest_changed')
 resolved={}
 try:
  if any(bool(values) for values in references.values() if isinstance(values,dict)):resolved=_resolve_runtime_secrets(plan['project_slug'],plan['environment'],references)
  variables=_merge_runtime_variables(public_runtime,resolved);executor_runtime=_runtime_configuration_for_executor(runtime_configuration)
  variables_digest=hashlib.sha256(json.dumps(variables,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  operation=plan['operation'];deployment_id=_deployment_id(execution_id)
  applications=[{'service':item['service'],'image_id':item['imageId'],'application_digest':item['applicationDigest'],'port':item['port'],'healthcheck':item['healthcheck']} for item in operation['applications']]
  payload={'deployment_id':deployment_id,'project_slug':plan['project_slug'],'environment':plan['environment'],'build_job_id':build_job_id,'deployment_plan_digest':digest,'build_plan_digest':operation['build_plan_digest'],'config_revision':operation['config_revision'],'config_digest':operation['config_digest'],'toolchain_digest':operation['toolchain_digest'],'archive_sha256':operation['archive_sha256'],'applications':applications,'routes':operation['routes'],'variables':variables,'variables_digest':variables_digest,'runtimeConfiguration':executor_runtime}
  idem_mark_effect(execution_id);code,result=_deployment_executor_call('POST','/v1/deployments',payload,timeout=600)
 finally:
  resolved.clear()
 safe=dict(result) if isinstance(result,dict) else {'ok':False}
 safe.pop('variables',None);safe.pop('runtimeConfiguration',None);safe['variable_values_returned']=False;safe['secret_values_in_metadata']=False;safe['secret_references_in_metadata']=False;safe['effect_started']=True;safe['deployment_plan_digest']=digest
 return code,safe

def _production_config(slug):
 try:
  data=json.load(open(PRODUCTION_TARGETS))
  cfg=data.get(slug) if isinstance(data,dict) else None
  return cfg if isinstance(cfg,dict) else {}
 except Exception:return {}
def _latest_build_artifact(slug):
 try:
  c=sqlite3.connect('/var/lib/cloudif/build-broker/builds.sqlite3');c.row_factory=sqlite3.Row
  r=c.execute("select id,status,result_json,updated_at from builds where project_slug=? and status='succeeded' order by created_at desc limit 1",(slug,)).fetchone()
  if not r:return {}
  x=json.loads(r['result_json'] or '{}');x['build_id']=r['id'];x['build_status']=r['status'];x['build_updated_at']=r['updated_at'];return x
 except Exception:return {}

def _production_readiness(slug):
 if not SLUG.fullmatch(slug):raise ValueError('invalid_project')
 setting=rm.project_setting(slug)
 if not setting:raise LookupError('project_not_reconciled')
 cfg=_production_config(slug)
 artifact=_latest_build_artifact(slug)
 checks={'target_enabled':cfg.get('enabled') is True,'separate_from_test':cfg.get('separate_from_test') is True,'komodo_stack_configured':bool(cfg.get('komodo_stack')),'public_url_configured':bool(cfg.get('public_url')),'smoke_url_configured':bool(cfg.get('smoke_url')),'rollback_strategy_configured':bool(cfg.get('rollback_strategy')),'automatic_database_restore':cfg.get('database_restore')=='automatic','immutable_image_required':cfg.get('immutable_image') is True,'artifact_image_created':artifact.get('image_created') is True,'artifact_digest_present':str(artifact.get('artifact_image_id') or '').startswith('sha256:'),'sbom_ready':artifact.get('sbom_ready') is True and bool(artifact.get('sbom_sha256')),'scanner_ready':artifact.get('scanner_ready') is True and bool(artifact.get('scanner_sha256')),'scanner_high_zero':int((artifact.get('scanner_counts') or {}).get('HIGH',0))==0,'scanner_critical_zero':int((artifact.get('scanner_counts') or {}).get('CRITICAL',0))==0,'runtime_rootless':str((artifact.get('runtime_proof') or {}).get('user') or '').split(':')[0] not in {'','0','root'},'runtime_read_only':(artifact.get('runtime_proof') or {}).get('read_only') is True,'runtime_no_capabilities':(artifact.get('runtime_proof') or {}).get('cap_drop')==['ALL'],'runtime_no_published_ports':(artifact.get('runtime_proof') or {}).get('published_ports')==[],'change_window_configured':bool(cfg.get('change_window')),'change_window_open':cfg.get('change_window_open') is True,'snapshot_policy_configured':cfg.get('snapshot_policy')=='required-before-activation','snapshot_verified':cfg.get('snapshot_signature_verified') is True and bool(cfg.get('snapshot_sha256')) and bool(cfg.get('snapshot_signature_sha256')),'change_dossier_signed':cfg.get('change_dossier_signed') is True and bool(cfg.get('change_dossier_path')),'rollback_plan_verified':cfg.get('rollback_plan_verified') is True,'dual_approval_required':cfg.get('dual_approval_required') is True,'production_effects_explicitly_enabled':cfg.get('production_effects_enabled') is True}
 blockers=[k for k,v in checks.items() if not v]
 return {'ok':True,'project_slug':slug,'production_ready':not blockers,'execution_allowed':not blockers,'checks':checks,'blockers':blockers,'artifact':{k:artifact.get(k) for k in ('build_id','artifact_image_id','sbom_sha256','scanner_sha256','scanner_counts','production_ready')},'two_approvers_required':True,'approval_policy':{'activation':'two_distinct_admin_or_professor','requester_cannot_approve':True,'approval_replay':'blocked'},'target_configured':bool(cfg),'side_effect_free':True,'secrets_exposed':False}
def _production_plan(d):
 if set(d)!={'project_slug','commit_sha','version','trace_id'}:raise ValueError('invalid_request')
 slug=str(d.get('project_slug') or '').strip();commit=str(d.get('commit_sha') or '').strip().lower();version=str(d.get('version') or '').strip();trace=str(d.get('trace_id') or '').strip()
 if not SLUG.fullmatch(slug) or not COMMIT.fullmatch(commit) or not VERSION.fullmatch(version) or not trace:raise ValueError('invalid_request')
 ready=_production_readiness(slug);prepared=rm.forja_prepare(slug,version,commit,'production plan',True);body=prepared.get('data') if isinstance(prepared.get('data'),dict) else {}
 if not prepared.get('ok') or not body.get('ok'):raise RuntimeError('forgejo_validation_failed')
 canonical={'action':'deployment.production.deploy','project_slug':slug,'commit_sha':commit,'version':version,'target':'production','readiness_checks':ready['checks'],'snapshot_sha256':_production_config(slug).get('snapshot_sha256'),'snapshot_signature_sha256':_production_config(slug).get('snapshot_signature_sha256'),'change_dossier_signed':_production_config(slug).get('change_dossier_signed') is True}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'ok':True,'project_slug':slug,'commit_sha':commit,'version':version,'plan_digest':digest,'snapshot':{'sha256':_production_config(slug).get('snapshot_sha256'),'signature_sha256':_production_config(slug).get('snapshot_signature_sha256'),'signing_key_fingerprint':_production_config(slug).get('snapshot_signing_key_fingerprint'),'signature_verified':_production_config(slug).get('snapshot_signature_verified') is True},'change_dossier_signed':_production_config(slug).get('change_dossier_signed') is True,'production_ready':ready['production_ready'],'execution_allowed':ready['execution_allowed'],'blockers':ready['blockers'],'approval_policy':ready['approval_policy'],'two_approvers_required':True,'approval_required':True,'side_effect_free':True,'backup_created':False,'deployment_created':False,'trace_id':trace}

def _production_activation_plan(d):
 if set(d)!={'project_slug','trace_id'}:raise ValueError('invalid_request')
 slug=str(d.get('project_slug') or '').strip();trace=str(d.get('trace_id') or '').strip()
 if not SLUG.fullmatch(slug) or not trace:raise ValueError('invalid_request')
 ready=_production_readiness(slug);cfg=_production_config(slug);w=cfg.get('change_window') or {}
 canonical={'action':'deployment.production.activate','project_slug':slug,'target_url':cfg.get('real_target_url'),'target_mode':cfg.get('real_target_mode'),'snapshot_sha256':cfg.get('snapshot_sha256'),'snapshot_signature_sha256':cfg.get('snapshot_signature_sha256'),'window_digest_sha256':w.get('digest_sha256'),'window_id':w.get('id'),'window_start_at':w.get('start_at'),'window_end_at':w.get('end_at'),'canary_a_sha256':cfg.get('real_canary_a_body_sha256'),'canary_b_sha256':cfg.get('real_canary_b_body_sha256'),'canary_rollback_verified':cfg.get('real_canary_rollback_verified') is True,'restore_test_verified':cfg.get('restore_test_verified') is True,'rollback_plan_verified':cfg.get('rollback_plan_verified') is True,'dual_approval_required':True,'auto_reseal':w.get('auto_reseal') is True,'max_duration_seconds':w.get('max_duration_seconds'),'readiness_checks':ready['checks'],'effect_tool_available':False}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 blockers=list(ready['blockers'])
 if cfg.get('real_target_mode')!='sealed':blockers.append('real_target_not_sealed')
 if cfg.get('real_canary_rollback_verified') is not True:blockers.append('real_canary_rollback_unverified')
 if cfg.get('restore_test_verified') is not True:blockers.append('restore_test_unverified')
 return {'ok':True,'project_slug':slug,'activation_digest':digest,'operation':canonical,'approval_action':'deployment.production.activate','two_approvers_required':True,'requester_cannot_approve':True,'approval_required':True,'effect_tool_available':False,'side_effect_free':True,'activation_allowed':False,'execution_allowed':False,'production_enabled':False,'blockers':sorted(set(blockers)),'trace_id':trace,'secrets_exposed':False}

def _homologation_executor(path,payload=None,timeout=180):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(HOMOLOGATION_URL+path,data=data,method='GET' if data is None else 'POST',headers={'Authorization':'Bearer '+HOMOLOGATION_TOKEN,'Content-Type':'application/json','Accept':'application/json','Host':'cloudif-production-homologation.internal'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
 except urllib.error.HTTPError as e:
  try:b=json.load(e)
  except Exception:b={}
  return e.code,b
def _homologation_artifact(slug,build_id):
 c=sqlite3.connect('/var/lib/cloudif/build-broker/builds.sqlite3');c.row_factory=sqlite3.Row;r=c.execute("select id,project_slug,status,result_json from builds where id=? and project_slug=?",(build_id,slug)).fetchone();c.close()
 if not r or r['status']!='succeeded':raise LookupError('build_not_ready')
 x=json.loads(r['result_json'] or '{}');att=x.get('attestation') or {};counts=x.get('scanner_counts') or {}
 if not (x.get('attestation_verified') is True and att.get('algorithm')=='HMAC-SHA256' and len(str(att.get('signature') or ''))==64 and str(x.get('artifact_image_id') or '').startswith('sha256:') and x.get('sbom_ready') is True and x.get('scanner_ready') is True and x.get('scanner_blocked') is False and counts.get('HIGH',0)==0 and counts.get('CRITICAL',0)==0 and x.get('production_ready') is True):raise RuntimeError('artifact_not_attested')
 return x
def _homologation_plan(d):
 if set(d)!={'project_slug','build_id','trace_id'}:raise ValueError('invalid_request')
 slug=str(d['project_slug']);build_id=str(d['build_id']);trace=str(d['trace_id']);cfg=_production_config(slug)
 if not (cfg.get('homologation_enabled') is True and cfg.get('homologation_only') is True and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False):raise PermissionError('homologation_target_not_allowed')
 art=_homologation_artifact(slug,build_id)
 canonical={'action':'deployment.production.homologation.deploy','project_slug':slug,'build_id':build_id,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art.get('immutable_source_digest'),'attestation_signature':(art.get('attestation') or {}).get('signature'),'target':'production-homologation','atomic_switch':True}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'ok':True,'side_effect_free':True,'homologation_digest':digest,'operation':canonical,'approval_required':True,'production_enabled':False,'homologation_only':True,'trace_id':trace,'secrets_exposed':False}
def _executor_execution_id(execution_id):
 return 'exe_'+hashlib.sha256(execution_id.encode()).hexdigest()[:24]
def _executor_rollback_id(execution_id):
 return 'rbk_'+hashlib.sha256(execution_id.encode()).hexdigest()[:24]
def _homologation_deploy(d,execution_id):
 if set(d)!={'project_slug','build_id','homologation_digest','trace_id'}:raise ValueError('invalid_request')
 pl=_homologation_plan({'project_slug':d['project_slug'],'build_id':d['build_id'],'trace_id':d['trace_id']})
 if not hmac.compare_digest(pl['homologation_digest'],d['homologation_digest']):raise ValueError('homologation_digest_mismatch')
 op=pl['operation'];idem_mark_effect(execution_id);code,x=_homologation_executor('/v1/deploy',{'project_slug':op['project_slug'],'artifact_image_id':op['artifact_image_id'],'execution_id':_executor_execution_id(execution_id)},180)
 if code!=200 or not x.get('ok'):return code,{'ok':False,'error':x.get('error') or 'homologation_deploy_failed','effect_started':True}
 x.update({'homologation_only':True,'production_enabled':False,'build_id':d['build_id'],'attestation_verified':True,'effect_started':True,'secrets_exposed':False});return 200,x
def _homologation_rollback(d,execution_id):
 if set(d)!={'project_slug','trace_id'}:raise ValueError('invalid_request')
 cfg=_production_config(d['project_slug'])
 if not (cfg.get('homologation_only') is True and cfg.get('enabled') is False):raise PermissionError('homologation_target_not_allowed')
 idem_mark_effect(execution_id);code,x=_homologation_executor('/v1/rollback',{'project_slug':d['project_slug'],'execution_id':_executor_rollback_id(execution_id)},180)
 if code!=200 or not x.get('ok'):return code,{'ok':False,'error':x.get('error') or 'homologation_rollback_failed','effect_started':True}
 x.update({'homologation_only':True,'production_enabled':False,'effect_started':True,'secrets_exposed':False});return 200,x

def _migration_analysis(d,plan_only=False):
 slug,commit,version,trace,setting=validate_common(d)
 if plan_only and slug!=TEST_PROJECT:raise PermissionError('project_not_allowed')
 tenant=str(setting.get('tenant') or '').strip()
 prepared=rm.forja_prepare(slug,version,commit,'migration inspection',True)
 body=prepared.get('data') if isinstance(prepared.get('data'),dict) else {}
 if not prepared.get('ok') or not body.get('ok'):raise RuntimeError('forgejo_validation_failed')
 bundle=body.get('migrations') or {};items=bundle.get('items') or []
 if not isinstance(items,list):raise RuntimeError('invalid_migration_bundle')
 checked=rm.supabase_inspect(slug,tenant,version,items)
 sb=checked.get('data') if isinstance(checked.get('data'),dict) else {}
 if not checked.get('ok') or not sb.get('ok'):raise RuntimeError('supabase_inspect_failed')
 safe=[]
 for item in items:
  name=str(item.get('name') or '')
  sha=str(item.get('sha256') or '')
  raw=str(item.get('content_b64') or '')
  size=(len(raw)*3)//4 if raw else 0
  safe.append({'name':name,'sha256':sha,'size_bytes':size})
 canonical={'action':'supabase.migrations.plan' if plan_only else 'supabase.migrations.inspect','project_slug':slug,'commit_sha':commit,'version':version,'tenant':tenant,'migrations':[{'name':x['name'],'sha256':x['sha256']} for x in safe],'target':'isolated-test' if plan_only else 'project','side_effect_free':True}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'ok':True,'project_slug':slug,'commit_sha':commit,'version':version,'tenant':tenant,'migration_count':len(safe),'total_bytes':int(bundle.get('total_bytes') or 0),'migrations':safe,'tenant_available':bool(sb.get('available')),'side_effect_free':True,'sql_exposed':False,'content_b64_exposed':False,'backup_created':False,'migrations_applied':0,'deployment_created':False,'plan_digest':digest if plan_only else '', 'target':'isolated-test' if plan_only else 'project','apply_allowed':len(safe)==0,'blocked_reason':'' if len(safe)==0 else 'automatic_restore_unavailable','automatic_restore_available':False,'trace_id':trace}

def _client_env(path,url_key,token_key,default):
 cfg=rm.read_env(Path(path));return (cfg.get(url_key) or default).rstrip('/'),cfg.get(token_key) or ''
def _komodo_operational(body):
 busy=body.get('busy') or {}
 return body.get('deploy_status') in {'ready','completed'} and not bool(busy.get('repo')) and not bool(busy.get('stack'))

def _komodo_status(project):
 base,token=_client_env('/etc/cloudif/komodo-agent-client.env','KOMODO_AGENT_URL','KOMODO_AGENT_TOKEN','http://10.62.91.2:18098')
 return rm.http_json('GET',base+'/komodo/status?'+urllib.parse.urlencode({'project':project}),token,None,60)
def _komodo_smoke(project):
 base,token=_client_env('/etc/cloudif/komodo-agent-client.env','KOMODO_AGENT_URL','KOMODO_AGENT_TOKEN','http://10.62.91.2:18098')
 return rm.http_json('POST',base+'/komodo/stack/http-smoke',token,{'project':project},30)
def _last_published(project):
 con=rm.connect();con.row_factory=sqlite3.Row
 row=con.execute("SELECT * FROM release_jobs WHERE project=? AND dry_run=0 AND status='published' ORDER BY id DESC LIMIT 1",(project,)).fetchone();con.close()
 return dict(row) if row else None
def _prestate(project):
 previous=_last_published(project)
 if not previous or not COMMIT.fullmatch(str(previous.get('commit_sha') or '')):raise RuntimeError('previous_release_missing')
 status=_komodo_status(project);body=status.get('data') if isinstance(status.get('data'),dict) else {}
 if not status.get('ok') or not body.get('ok') or not _komodo_operational(body):raise RuntimeError('komodo_not_ready')
 latest=str((body.get('repo') or {}).get('latest_hash') or '')
 telemetry_mismatch=bool(latest and not str(previous['commit_sha']).startswith(latest))
 smoke=_komodo_smoke(project);sb=smoke.get('data') if isinstance(smoke.get('data'),dict) else {}
 if not smoke.get('ok') or not sb.get('ok') or sb.get('status')!=200:raise RuntimeError('predeploy_smoke_failed')
 return {'commit_sha':previous['commit_sha'],'version':previous['version'],'job_id':previous['id'],'tenant':previous.get('tenant') or '', 'http_sha256':sb.get('sha256'),'http_size':sb.get('size'),'komodo_repo_latest_hash':latest,'komodo_repo_telemetry_mismatch':telemetry_mismatch}
def _rollback_test(project,tenant,commit,trace):
 deploy=rm.komodo_deploy_commit(project,tenant,commit,'deployment-broker-rollback:'+trace)
 body=deploy.get('data') if isinstance(deploy.get('data'),dict) else {}
 smoke=_komodo_smoke(project);sb=smoke.get('data') if isinstance(smoke.get('data'),dict) else {}
 status=_komodo_status(project);st=status.get('data') if isinstance(status.get('data'),dict) else {}
 ok=bool(deploy.get('ok') and body.get('ok') and smoke.get('ok') and sb.get('ok') and sb.get('status')==200 and status.get('ok') and _komodo_operational(st))
 return {'ok':ok,'deploy_confirmed':bool(deploy.get('ok') and body.get('ok')),'smoke_ok':bool(smoke.get('ok') and sb.get('ok')),'status_ready':bool(status.get('ok') and _komodo_operational(st)),'http_sha256':sb.get('sha256'),'http_size':sb.get('size')}

def _published_job(project,job_id):
 con=rm.connect();con.row_factory=sqlite3.Row
 row=con.execute("select * from release_jobs where id=? and project=? and dry_run=0 and status='published'",(int(job_id),project)).fetchone();con.close()
 return dict(row) if row else None

def _rollback_plan(d):
 if set(d)!={'project_slug','target_job_id','trace_id'}:raise ValueError('invalid_request')
 slug=str(d.get('project_slug') or '').strip().lower();trace=str(d.get('trace_id') or '').strip();target_job_id=int(d.get('target_job_id') or 0)
 if slug!=TEST_PROJECT or not trace or target_job_id<1:raise ValueError('invalid_request')
 pre=_prestate(slug);target=_published_job(slug,target_job_id)
 if not target:raise LookupError('rollback_target_not_published')
 canonical={'action':'deployment.rollback-test','project_slug':slug,'target_job_id':target_job_id,'target_commit':target['commit_sha'],'target_version':target['version'],'expected_current_job_id':pre['job_id'],'expected_current_commit':pre['commit_sha'],'target':'isolated-test','real_deploy':True}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'ok':True,'side_effect_free':True,'rollback_digest':digest,'operation':canonical,'prestate':pre,'target_release':{'job_id':target_job_id,'commit_sha':target['commit_sha'],'version':target['version'],'release_id':target.get('release_id') or ''},'approval_required':True,'trace_id':trace}

def _record_deploy_state(project,tenant,commit,actor,response):
 con=rm.connect();now=rm.now_utc()
 sql="insert into deploy_state(project,tenant,mode,commit_sha,commit_short,commit_message,actor,updated_at,response_json) values(?,?,?,?,?,?,?,?,?) on conflict(project) do update set tenant=excluded.tenant,mode=excluded.mode,commit_sha=excluded.commit_sha,commit_short=excluded.commit_short,commit_message=excluded.commit_message,actor=excluded.actor,updated_at=excluded.updated_at,response_json=excluded.response_json"
 con.execute(sql,(project,tenant,'manual_rollback',commit,commit[:7],'manual rollback',actor,now,rm.safe_detail(response)));con.commit();con.close()

def _rollback_real(d,execution_id=''):
 if set(d)!={'project_slug','target_job_id','expected_current_job_id','expected_current_commit','trace_id'}:raise ValueError('invalid_request')
 slug=str(d.get('project_slug') or '').strip().lower();target_job_id=int(d.get('target_job_id') or 0);current_job_id=int(d.get('expected_current_job_id') or 0);current_commit=str(d.get('expected_current_commit') or '').strip().lower();trace=str(d.get('trace_id') or '').strip()
 if slug!=TEST_PROJECT or target_job_id<1 or current_job_id<1 or not COMMIT.fullmatch(current_commit) or not trace:raise ValueError('invalid_request')
 pre=_prestate(slug)
 if pre['job_id']!=current_job_id or not hmac.compare_digest(pre['commit_sha'],current_commit):raise RuntimeError('current_release_changed')
 target=_published_job(slug,target_job_id)
 if not target:raise LookupError('rollback_target_not_published')
 setting=rm.project_setting(slug) or {};tenant=setting.get('tenant') or pre.get('tenant') or ''
 version=f"v0.0.0-rollback-j{target_job_id}-{int(dt.datetime.now(dt.timezone.utc).timestamp())}"
 scheduled=rm.schedule(slug,tenant,version,target['commit_sha'],dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),f'deployment-broker-manual-rollback:{trace}',dry_run=False,notes=f'Manual approved rollback to historical job {target_job_id}.')
 job_id=scheduled['job_id'];rm.update_job(job_id,status='running',started_at=rm.now_utc(),message='Manual rollback started.');idem_mark_effect(execution_id)
 backup_path=''
 if tenant:
  backup=rm.supabase_backup(slug,tenant,version);bb=backup.get('data') if isinstance(backup.get('data'),dict) else {}
  if not backup.get('ok') or not bb.get('ok') or not bb.get('backup_path'):
   rm.update_job(job_id,status='failed',finished_at=rm.now_utc(),message='Manual rollback backup failed.');return 502,{'ok':False,'status':'failed','job_id':job_id,'failure':'backup_failed'}
  backup_path=str(bb.get('backup_path') or '');rm.update_job(job_id,backup_path=backup_path)
 rb=_rollback_test(slug,tenant,target['commit_sha'],trace)
 if not rb.get('ok'):
  recovery=_rollback_test(slug,tenant,pre['commit_sha'],trace+'-recovery')
  rm.update_job(job_id,status='rolled_back',finished_at=rm.now_utc(),message='Manual rollback target failed; previous release restored.',detail_json=rm.safe_detail({'target_job_id':target_job_id,'rollback':rb,'recovery':recovery,'prestate':pre}))
  return 502,{'ok':False,'status':'rolled_back' if recovery.get('ok') else 'rollback_failed','job_id':job_id,'target_job_id':target_job_id,'recovery':recovery,'failure':'target_deploy_failed'}
 response={'target_job_id':target_job_id,'target_commit':target['commit_sha'],'target_version':target['version'],'prestate':pre,'rollback':rb}
 rm.update_job(job_id,status='published',finished_at=rm.now_utc(),message=f'Manual rollback to job {target_job_id} completed.',detail_json=rm.safe_detail(response),migration_applied=0)
 _record_deploy_state(slug,tenant,target['commit_sha'],f'deployment-broker-manual-rollback:{trace}',response)
 return 200,{'ok':True,'status':'published','operation':'manual_rollback','job_id':job_id,'project_slug':slug,'target_job_id':target_job_id,'commit_sha':target['commit_sha'],'version':version,'backup_path':backup_path,'migrations_applied':0,'komodo_called':True,'postcheck':{'status_ready':rb.get('status_ready') is True,'http_smoke':rb.get('smoke_ok') is True,'http_sha256':rb.get('http_sha256'),'http_size':rb.get('http_size')},'prestate':pre,'rollback_prepared':True}

def _promote_real(d,execution_id=""):
 if set(d)!={'project_slug','commit_sha','version','trace_id','expected_previous_commit'}:raise ValueError('invalid_request')
 expected_previous=str(d.get('expected_previous_commit') or '').strip().lower()
 if not COMMIT.fullmatch(expected_previous):raise ValueError('invalid_request')
 base={k:d[k] for k in ('project_slug','commit_sha','version','trace_id')}
 slug,commit,version,trace,setting=validate_common(base)
 if slug!=TEST_PROJECT:raise PermissionError('project_not_allowed')
 pre=_prestate(slug)
 if not hmac.compare_digest(pre['commit_sha'],expected_previous):raise RuntimeError('previous_commit_changed')
 idem_mark_effect(execution_id)
 scheduled=rm.schedule(slug,setting.get('tenant') or '',version,commit,dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),f'deployment-broker:{trace}',dry_run=False,notes='CloudIF approved real deployment for isolated test project.')
 result=rm.process_job(scheduled['job_id']);item=rm.get_job(scheduled['job_id']) or {}
 if not result.get('ok') or result.get('status')!='published' or item.get('status')!='published':
  rb=_rollback_test(slug,pre['tenant'],pre['commit_sha'],trace)
  rm.update_job(scheduled['job_id'],status='rolled_back',finished_at=rm.now_utc(),message='Deploy failed; automatic rollback executed.',detail_json=rm.safe_detail({'process_result':result,'rollback':rb,'prestate':pre}))
  return 502,{'ok':False,'status':'rolled_back' if rb.get('ok') else 'rollback_failed','job_id':scheduled['job_id'],'rollback':rb,'prestate':pre,'failure':'process_job_failed'}
 status=_komodo_status(slug);st=status.get('data') if isinstance(status.get('data'),dict) else {}
 smoke=_komodo_smoke(slug);sb=smoke.get('data') if isinstance(smoke.get('data'),dict) else {}
 post_ok=bool(status.get('ok') and st.get('ok') and _komodo_operational(st) and smoke.get('ok') and sb.get('ok') and sb.get('status')==200)
 if not post_ok:
  rb=_rollback_test(slug,pre['tenant'],pre['commit_sha'],trace)
  rm.update_job(scheduled['job_id'],status='rolled_back',finished_at=rm.now_utc(),message='Post-deploy verification failed; automatic rollback executed.',detail_json=rm.safe_detail({'rollback':rb,'prestate':pre,'status':st,'smoke':sb}))
  return 502,{'ok':False,'status':'rolled_back' if rb.get('ok') else 'rollback_failed','job_id':scheduled['job_id'],'rollback':rb,'prestate':pre,'failure':'postcheck_failed'}
 return 200,{'ok':True,'status':'published','job_id':scheduled['job_id'],'project_slug':slug,'commit_sha':commit,'version':version,'release_id':item.get('release_id') or '','release_url':item.get('release_url') or '','backup_path':item.get('backup_path') or '','migrations_applied':int(item.get('migration_applied') or 0),'komodo_called':True,'postcheck':{'status_ready':True,'http_smoke':True,'http_sha256':sb.get('sha256'),'http_size':sb.get('size')},'prestate':pre,'rollback_prepared':True}


class H(BaseHTTPRequestHandler):
 server_version='CloudIFDeploymentBroker/1.0'
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path=='/health':return send(self,200,{'ok':True,'service':'cloudif-deployment-broker','mode':'approved-test-promotion'})
  if not auth(self):return send(self,401,{'ok':False,'error':'unauthorized'})
  p=urllib.parse.urlparse(self.path);q=urllib.parse.parse_qs(p.query)
  if p.path=='/v1/multiservice-status' and set(q)=={'deployment_id'}:
   deployment_id=str(q['deployment_id'][0])
   if not DEPLOYMENT_ID_RE.fullmatch(deployment_id):return send(self,400,{'ok':False,'error':{'code':'invalid_deployment_id','message':'deployment_id inválido.'}})
   code,result=_deployment_executor_call('GET','/v1/deployments/'+urllib.parse.quote(deployment_id,safe=''),None,timeout=30)
   if isinstance(result,dict):result.pop('variables',None);result['variable_values_returned']=False
   return send(self,code,result)
  if p.path!='/v1/status' or set(q)!={'job_id'}:return send(self,404,{'ok':False,'error':'not_found'})
  try:job_id=int(q['job_id'][0]);item=rm.get_job(job_id)
  except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
  if not item:return send(self,404,{'ok':False,'error':'not_found'})
  safe={k:item.get(k) for k in ('id','created_at','scheduled_at','started_at','finished_at','project','tenant','version','commit_sha','actor','status','dry_run','migration_count','migration_applied','release_id','release_url','backup_path','message')}
  return send(self,200,{'ok':True,'job':safe,'read_only':True})
 def do_POST(self):
  if not auth(self):return send(self,401,{'ok':False,'error':'unauthorized'})
  try:d=body(self)
  except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
  if self.path=='/v1/multiservice-plan':
   try:result=_multiservice_deployment_plan(d)
   except LookupError as e:return send(self,404,{'ok':False,'error':{'code':str(e),'message':'Configuração do projeto não encontrada.'}})
   except RuntimeError as e:return send(self,503,{'ok':False,'error':{'code':str(e),'message':'Serviço interno indisponível.'}})
   except ValueError as e:return send(self,422,{'ok':False,'error':{'code':str(e),'message':'project_slug, environment e trace_id são obrigatórios. build_job_id é obrigatório para um plano executável; sem ele o plano retorna build-job-required.','example':{'project_slug':'meu-projeto','build_job_id':'build_111111111111111111111111','environment':'homologation','trace_id':'trace-123'}}})
   return send(self,200,result)
  if self.path=='/v1/multiservice-deploy':
   execution_id=str(d.pop('execution_id','') or '').strip();payload=dict(d)
   try:istate=idem_begin(execution_id,'deployment.multiservice',payload)
   except ValueError as error:return send(self,400,{'ok':False,'error':{'code':str(error),'message':'execution_id inválido.'},'effect_started':False})
   if (cached:=idem_response(istate)):return send(self,cached[0],cached[1])
   try:code,result=_multiservice_execute(d,execution_id)
   except LookupError as error:return send(self,404,idem_finish(execution_id,404,{'ok':False,'error':{'code':str(error),'message':'Configuração não encontrada.'},'effect_started':False}))
   except PermissionError as error:return send(self,409,idem_finish(execution_id,409,{'ok':False,'error':{'code':'deployment_blocked','message':str(error)},'effect_started':False}))
   except ValueError as error:return send(self,409,idem_finish(execution_id,409,{'ok':False,'error':{'code':str(error),'message':'O plano mudou ou é incompatível.'},'effect_started':False}))
   except RuntimeError as error:return send(self,503,idem_finish(execution_id,503,{'ok':False,'error':{'code':str(error),'message':'Serviço interno indisponível.'},'effect_started':False}))
   except Exception as error:return send(self,502,idem_finish(execution_id,502,{'ok':False,'error':{'code':'multiservice_deployment_failed','message':'O deploy multissserviço falhou.'},'error_type':type(error).__name__,'effect_started':True}))
   return send(self,code,idem_finish(execution_id,code,result))
  if self.path=='/v1/production-readiness':
   try:
    if set(d)!={'project_slug','trace_id'}:raise ValueError('invalid_request')
    result=_production_readiness(str(d.get('project_slug') or '').strip());result['trace_id']=str(d.get('trace_id') or '')
   except LookupError as e:return send(self,404,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path=='/v1/production-activation-plan':
   try:result=_production_activation_plan(d)
   except LookupError as e:return send(self,404,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path=='/v1/production-plan':
   try:result=_production_plan(d)
   except LookupError as e:return send(self,404,{'ok':False,'error':str(e)})
   except RuntimeError as e:return send(self,409,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path=='/v1/production-homologation-plan':
   try:result=_homologation_plan(d)
   except PermissionError as e:return send(self,403,{'ok':False,'error':str(e)})
   except LookupError as e:return send(self,404,{'ok':False,'error':str(e)})
   except RuntimeError as e:return send(self,409,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path in {'/v1/production-homologation-deploy','/v1/production-homologation-rollback'}:
   execution_id=str(d.pop('execution_id','') or '').strip();payload=dict(d);op='deployment.production.homologation.deploy' if self.path.endswith('-deploy') else 'deployment.production.homologation.rollback'
   try:istate=idem_begin(execution_id,op,payload)
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   if (cached:=idem_response(istate)):return send(self,cached[0],cached[1])
   try:code,result=(_homologation_deploy(d,execution_id) if self.path.endswith('-deploy') else _homologation_rollback(d,execution_id))
   except PermissionError as e:return send(self,403,idem_finish(execution_id,403,{'ok':False,'error':str(e),'effect_started':False}))
   except LookupError as e:return send(self,404,idem_finish(execution_id,404,{'ok':False,'error':str(e),'effect_started':False}))
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   except Exception as e:return send(self,502,idem_finish(execution_id,502,{'ok':False,'error':'homologation_effect_failed','error_type':type(e).__name__,'effect_started':True}))
   return send(self,code,idem_finish(execution_id,code,result))
  if self.path in {'/v1/migrations-inspect','/v1/migrations-plan'}:
   try:result=_migration_analysis(d,self.path.endswith('-plan'))
   except PermissionError as e:return send(self,403,{'ok':False,'error':str(e)})
   except LookupError:return send(self,404,{'ok':False,'error':'project_not_reconciled'})
   except RuntimeError as e:return send(self,409,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path=='/v1/plan':
   try:slug,commit,version,trace,setting=validate_common(d)
   except LookupError:return send(self,404,{'ok':False,'error':'project_not_reconciled'})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   canonical={'action':'deployment.validate','project_slug':slug,'commit_sha':commit,'version':version,'dry_run':True}
   digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   return send(self,200,{'ok':True,'side_effect_free':True,'deployment_digest':digest,'operation':canonical,'tenant':setting.get('tenant') or '','target':'validation-only','trace_id':trace})
  if self.path=='/v1/plan-promote-test':
   try:slug,commit,version,trace,setting=validate_common(d)
   except LookupError:return send(self,404,{'ok':False,'error':'project_not_reconciled'})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   if slug!=TEST_PROJECT:return send(self,403,{'ok':False,'error':'project_not_allowed'})
   try:pre=_prestate(slug)
   except RuntimeError as e:return send(self,409,{'ok':False,'error':str(e)})
   canonical={'action':'deployment.promote-test','project_slug':slug,'commit_sha':commit,'version':version,'target':'isolated-test','real_deploy':True,'expected_previous_commit':pre['commit_sha']}
   digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   return send(self,200,{'ok':True,'side_effect_free':True,'promotion_digest':digest,'operation':canonical,'prestate':{'commit_sha':pre['commit_sha'],'version':pre['version'],'job_id':pre['job_id'],'http_sha256':pre['http_sha256'],'komodo_repo_latest_hash':pre.get('komodo_repo_latest_hash'),'komodo_repo_telemetry_mismatch':pre.get('komodo_repo_telemetry_mismatch',False)},'rollback_required':True,'trace_id':trace})
  if self.path=='/v1/plan-rollback-test':
   try:result=_rollback_plan(d)
   except LookupError as e:return send(self,404,{'ok':False,'error':str(e)})
   except RuntimeError as e:return send(self,409,{'ok':False,'error':str(e)})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   return send(self,200,result)
  if self.path=='/v1/rollback-test':
   execution_id=str(d.pop('execution_id','') or '').strip();payload=dict(d)
   try:istate=idem_begin(execution_id,'deployment.rollback-test',payload)
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   if (cached:=idem_response(istate)):return send(self,cached[0],cached[1])
   try:code,result=_rollback_real(d,execution_id)
   except LookupError as e:return send(self,404,idem_finish(execution_id,404,{'ok':False,'error':str(e),'effect_started':False}))
   except RuntimeError as e:return send(self,409,idem_finish(execution_id,409,{'ok':False,'error':str(e),'effect_started':False}))
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   except Exception as e:return send(self,502,idem_finish(execution_id,502,{'ok':False,'error':'rollback_failed','error_type':type(e).__name__,'effect_started':True}))
   result=dict(result);result['effect_started']=True
   return send(self,code,idem_finish(execution_id,code,result))
  if self.path=='/v1/validate':
   execution_id=str(d.pop('execution_id','') or '').strip()
   try:slug,commit,version,trace,setting=validate_common(d)
   except LookupError:return send(self,404,{'ok':False,'error':'project_not_reconciled'})
   except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
   payload={'project_slug':slug,'commit_sha':commit,'version':version,'trace_id':trace}
   try:istate=idem_begin(execution_id,'deployment.validate',payload)
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   if (cached:=idem_response(istate)):return send(self,cached[0],cached[1])
   try:
    idem_mark_effect(execution_id)
    scheduled=rm.schedule(slug,setting.get('tenant') or '',version,commit,dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),f'deployment-broker:{trace}',dry_run=True,notes='CloudIF MCP approved deployment validation; dry-run only.')
    result=rm.process_job(scheduled['job_id'])
    item=rm.get_job(scheduled['job_id']) or {}
   except Exception as e:
    out={'ok':False,'error':'validation_failed','error_type':type(e).__name__,'effect_started':True};return send(self,502,idem_finish(execution_id,502,out))
   if not result.get('ok') or result.get('status')!='validated' or item.get('status')!='validated' or int(item.get('dry_run') or 0)!=1:
    out={'ok':False,'error':'validation_not_confirmed','job_id':scheduled.get('job_id'),'effect_started':True};return send(self,502,idem_finish(execution_id,502,out))
   forbidden=any([item.get('release_id'),item.get('release_url'),item.get('backup_path'),int(item.get('migration_applied') or 0)])
   if forbidden:
    out={'ok':False,'error':'dry_run_boundary_violated','job_id':scheduled['job_id'],'effect_started':True};return send(self,502,idem_finish(execution_id,502,out))
   out={'ok':True,'status':'validated','job_id':scheduled['job_id'],'project_slug':slug,'commit_sha':commit,'version':version,'dry_run':True,'release_created':False,'backup_created':False,'migrations_applied':0,'komodo_called':False,'trace_id':trace,'effect_started':True}
   return send(self,200,idem_finish(execution_id,200,out))
  if self.path=='/v1/promote-test':
   execution_id=str(d.pop('execution_id','') or '').strip()
   payload=dict(d)
   try:istate=idem_begin(execution_id,'deployment.promote-test',payload)
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   if (cached:=idem_response(istate)):return send(self,cached[0],cached[1])
   try:
    code,result=_promote_real(d,execution_id)
   except PermissionError:return send(self,403,idem_finish(execution_id,403,{'ok':False,'error':'project_not_allowed','effect_started':False}))
   except LookupError:return send(self,404,idem_finish(execution_id,404,{'ok':False,'error':'project_not_reconciled','effect_started':False}))
   except ValueError as e:return send(self,400,idem_finish(execution_id,400,{'ok':False,'error':str(e),'effect_started':False}))
   except RuntimeError as e:
    if str(e)=='previous_commit_changed':return send(self,409,idem_finish(execution_id,409,{'ok':False,'error':'previous_commit_changed','effect_started':False}))
    return send(self,502,idem_finish(execution_id,502,{'ok':False,'error':'promotion_failed','error_type':type(e).__name__,'effect_started':True}))
   except Exception as e:return send(self,502,idem_finish(execution_id,502,{'ok':False,'error':'promotion_failed','error_type':type(e).__name__,'effect_started':True}))
   result=dict(result);result['effect_started']=True
   return send(self,code,idem_finish(execution_id,code,result))
  return send(self,404,{'ok':False,'error':'not_found'})
if __name__=='__main__':
 if not TOKEN:raise SystemExit('missing token')
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
