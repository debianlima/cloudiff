#!/usr/bin/env python3
import argparse,datetime as dt,hashlib,json,os,sqlite3,subprocess,tempfile,time
ON='/var/lib/cloudif/onboarding/onboarding.db'
OUT='/var/lib/cloudif/health/project-state-reconcile.json'
AGENT='/var/lib/cloudif/health/agent-controller.json'
CAP='/var/lib/cloudif/health/project-capabilities-v2.json'
SOURCES=(
 '/srv/cloudif/app-pointers/agent-controller-current/cloudif-agent-controller.py',
 '/srv/cloudif/app-pointers/project-capabilities-current/cloudif-project-capabilities.py',
 '/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py',
 '/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py',
 '/etc/cloudif/project-capabilities-policy.json',
)
def now():return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def jload(path,default=None):
 try:return json.load(open(path))
 except Exception:return {} if default is None else default
def sha_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def atomic(path,data,mode=0o600):
 os.makedirs(os.path.dirname(path),exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.state-',dir=os.path.dirname(path))
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(tmp,mode);os.replace(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
def onboarding_rows():
 c=sqlite3.connect('file:'+ON+'?mode=ro',uri=True,timeout=10);c.row_factory=sqlite3.Row
 cols={x[1] for x in c.execute('pragma table_info(project_onboarding)')}
 wanted=['project_slug','client_id','owner_user','tenant','role_profile','environment','rate_per_minute','daily_quota','status','scopes_json','connectors_json']
 use=[x for x in wanted if x in cols]
 rows=[dict(r) for r in c.execute('select '+','.join(use)+' from project_onboarding order by project_slug')];c.close();return rows
def fingerprint(rows):
 payload={'projects':rows,'sources':{p:sha_file(p) for p in SOURCES if os.path.isfile(p)}}
 raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();return hashlib.sha256(raw).hexdigest(),payload['sources']
def run_unit(unit):
 started=time.monotonic();p=subprocess.run(['/bin/systemctl','start',unit],text=True,capture_output=True,timeout=180)
 result=subprocess.run(['/bin/systemctl','show',unit,'-p','Result','--value'],text=True,capture_output=True,timeout=10).stdout.strip()
 return {'unit':unit,'ok':p.returncode==0 and result in ('success',''),'result':result or 'unknown','duration_ms':round((time.monotonic()-started)*1000),'stderr':p.stderr.strip()[:240] if p.returncode else ''}
def parallel_reconcile():
 units=('cloudif-project-capabilities.service','cloudif-agent-controller.service');procs=[];started={}
 for u in units:
  started[u]=time.monotonic();procs.append((u,subprocess.Popen(['/bin/systemctl','start',u],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)))
 out=[]
 for u,p in procs:
  try:stdout,stderr=p.communicate(timeout=180)
  except subprocess.TimeoutExpired:p.kill();stdout,stderr=p.communicate();p.returncode=124
  result=subprocess.run(['/bin/systemctl','show',u,'-p','Result','--value'],text=True,capture_output=True,timeout=10).stdout.strip()
  out.append({'unit':u,'ok':p.returncode==0 and result in ('success',''),'result':result or 'unknown','duration_ms':round((time.monotonic()-started[u])*1000),'stderr':stderr.strip()[:240] if p.returncode else ''})
 return out
def build_report(rows,fp,sources,components,changed):
 agent=jload(AGENT);cap=jload(CAP);am={x.get('project_slug'):x for x in agent.get('results') or []};cm={x.get('project_slug'):x for x in cap.get('projects') or []};projects=[]
 for r in rows:
  slug=r.get('project_slug');a=am.get(slug,{});c=cm.get(slug,{});connectors=jload_text(r.get('connectors_json'))
  connector_states={k:(v.get('status') if isinstance(v,dict) else str(v)) for k,v in connectors.items()}
  onboarding_ok=r.get('status')=='ready';agent_ok=a.get('status') in ('aligned','corrected');cap_ok=c.get('scope_match') is True and int(c.get('tool_count') or 0)==int(cap.get('catalog_tools') or 0)
  projects.append({'project_slug':slug,'client_id':r.get('client_id'),'onboarding':'ready' if onboarding_ok else r.get('status') or 'unknown','agent':'aligned' if agent_ok else a.get('status') or 'missing','capabilities':'aligned' if cap_ok else 'drift','tool_count':int(c.get('tool_count') or 0),'connectors':connector_states,'overall':'ready' if onboarding_ok and agent_ok and cap_ok else 'attention','token_rotated':False})
 all_ok=bool(rows) and all(x['overall']=='ready' for x in projects) and agent.get('tokens_rotated')==0 and agent.get('tokens_returned')==0 and cap.get('effects_executed') is False
 previous=jload(OUT)
 return {'ok':all_ok,'generated_at':now(),'last_success_at':now() if all_ok else previous.get('last_success_at'),'fingerprint':fp,'changed':changed,'execution_mode':'parallel','components':components,'projects_count':len(projects),'projects_ready':sum(1 for x in projects if x['overall']=='ready'),'agents_aligned':sum(1 for x in projects if x['agent']=='aligned'),'capabilities_aligned':sum(1 for x in projects if x['capabilities']=='aligned'),'catalog_tools':int(cap.get('catalog_tools') or 0),'future_project_template':{'automatic_onboarding':True,'automatic_agent_identity':True,'automatic_capabilities':True,'default_role_profile':'project-admin','default_environment':'project','production_effects_enabled':False},'sources':sources,'projects':projects,'tokens_rotated':0,'tokens_returned':0,'effects_executed':False,'secrets_exposed':False}
def jload_text(raw):
 try:
  x=json.loads(raw or '{}');return x if isinstance(x,dict) else {}
 except Exception:return {}
def main(force=False):
 rows=onboarding_rows();fp,sources=fingerprint(rows);previous=jload(OUT)
 if not force and previous.get('ok') is True and previous.get('fingerprint')==fp and previous.get('projects_count')==len(rows):
  print(json.dumps({'ok':True,'changed':False,'projects':len(rows),'fingerprint':fp,'execution_mode':'noop','tokens_rotated':0},separators=(',',':')));return 0
 components=parallel_reconcile();report=build_report(rows,fp,sources,components,True);atomic(OUT,report)
 print(json.dumps({'ok':report['ok'],'changed':True,'projects':report['projects_count'],'ready':report['projects_ready'],'components':components,'tokens_rotated':0},separators=(',',':')))
 return 0 if report['ok'] and all(x['ok'] for x in components) else 1
def selftest():
 rows=onboarding_rows();fp,sources=fingerprint(rows);assert len(fp)==64 and rows and all('project_slug' in x for x in rows)
 a=jload(AGENT);c=jload(CAP);assert a.get('tokens_rotated')==0 and c.get('effects_executed') is False
 print(json.dumps({'ok':True,'projects':len(rows),'fingerprint_length':len(fp),'source_count':len(sources),'parallel_components':2,'tokens_rotated':0,'effects_executed':False},separators=(',',':')));return 0
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--force',action='store_true');ap.add_argument('--selftest',action='store_true');args=ap.parse_args();raise SystemExit(selftest() if args.selftest else main(args.force))
