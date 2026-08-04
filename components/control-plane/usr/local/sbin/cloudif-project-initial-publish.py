#!/usr/bin/env python3
import json,os,sqlite3,subprocess,sys,time,tempfile,urllib.request,urllib.error
from pathlib import Path
DB='/var/lib/cloudif/portal/cloudif-portal.db'
def envfile(path):
 d={}; p=Path(path)
 if p.exists():
  for line in p.read_text(errors='ignore').splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1); d[k.strip()]=v.strip().strip('"\'')
 return d
def request(url,method='GET',payload=None,headers=None,timeout=120):
 h={'Accept':'application/json'}; h.update(headers or {}); data=None
 if payload is not None: data=json.dumps(payload).encode(); h['Content-Type']='application/json'
 req=urllib.request.Request(url,data=data,method=method,headers=h)
 with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,json.loads(r.read() or b'{}')
def public_number(slug):
 c=sqlite3.connect(DB); r=c.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone(); c.close()
 if not r: raise RuntimeError('public_number_missing')
 return int(r[0])
def seed_db(tenant):
 name=f'cloudif_{tenant}-db-1'
 sql='''CREATE TABLE IF NOT EXISTS public.cloudif_tutorial_steps (id integer PRIMARY KEY,title text NOT NULL,completed boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT now()); ALTER TABLE public.cloudif_tutorial_steps ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS cloudif_tutorial_read ON public.cloudif_tutorial_steps; CREATE POLICY cloudif_tutorial_read ON public.cloudif_tutorial_steps FOR SELECT TO anon, authenticated USING (true); GRANT USAGE ON SCHEMA public TO anon, authenticated; GRANT SELECT ON public.cloudif_tutorial_steps TO anon, authenticated; INSERT INTO public.cloudif_tutorial_steps(id,title,completed) VALUES (1,'Entrar no Portal CloudIF',true),(2,'Editar um arquivo no Forgejo',false),(3,'Acompanhar o deploy no Komodo',false),(4,'Consultar o banco no Supabase',false),(5,'Entender os webhooks',false) ON CONFLICT(id) DO UPDATE SET title=excluded.title; NOTIFY pgrst, 'reload schema';'''
 p=subprocess.run(['docker','exec','-i',name,'psql','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],input=sql,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
 if p.returncode: raise RuntimeError('seed_db_failed:'+p.stderr[-300:])
def canonical_repo_url(c,slug,owner):
 row=c.execute('select forgejo_repo_url,repo_url from project_integrations where project=?',(slug,)).fetchone()
 if row:
  confirmed=str(row[0] or row[1] or '').strip()
  if confirmed:return confirmed.rstrip('.git') if confirmed.endswith('.git') else confirmed
 owner=str(owner or '').strip().lower()
 if not owner:raise RuntimeError('project_owner_missing')
 return f'https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}'
def update_db(slug,tenant,owner,num,commit=''):
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS project_publications (id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,version TEXT NOT NULL DEFAULT '',commit_sha TEXT NOT NULL DEFAULT '',stable_hostname TEXT NOT NULL,version_hostname TEXT NOT NULL,status TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,published_at TEXT,message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',UNIQUE(project_slug,deploy_number),UNIQUE(version_hostname))''')
 now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 c.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
 c.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug,deploy_number) do update set commit_sha=excluded.commit_sha,status='published',is_active=1,published_at=excluded.published_at,message=excluded.message''',(slug,num,1,'d1',commit,f'{num}.cloudiff.duckdns.org',f'{num}-d1.cloudiff.duckdns.org','published',1,owner,now,now,'Publicação inicial automática',json.dumps({'tenant':tenant})))
 cols=[r[1] for r in c.execute('pragma table_info(projects)')]
 updates={}
 repo_url=canonical_repo_url(c,slug,owner)
 for k,v in {'status':'published','repo_url':repo_url,'komodo_status':'running','updated_at':now}.items():
  if k in cols: updates[k]=v
 if updates:
  c.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
 c.commit(); c.close()
def atomic_job(path,data):
 fd,tmp=tempfile.mkstemp(prefix='.project-job-',dir=str(path.parent))
 try:
  with os.fdopen(fd,'w') as f:
   json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass

def progress(path,job,message,attempt=0,detail=''):
 job.update(status='running',current_step='initial-publication',message=message,progress_attempt=attempt,progress_detail=detail[:500],updated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
 atomic_job(path,job)

def main():
 job_path=Path(sys.argv[1]); job=json.loads(job_path.read_text()); slug=job['slug']; tenant=job['tenant']; owner=(job.get('user') or {}).get('username',''); kind=job.get('template_kind','none'); num=public_number(slug)
 kc=envfile('/etc/cloudif/komodo-agent-client.env'); kbase=(kc.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/'); kt=kc.get('KOMODO_AGENT_TOKEN',''); kh={'X-CloudIF-Token':kt,'Authorization':'Bearer '+kt} if kt else {}
 payload={'project_slug':slug,'project':slug,'slug':slug,'tenant':tenant,'actor':'project-initial-publish','deploy':True,'wait_timeout':1200}
 final={}
 def deployment_ready():
  nonlocal final
  _,final=request(kbase+'/komodo/project/status','POST',payload,kh,20)
  stack=final.get('stack') or {}; busy=final.get('busy') or {}
  deployed=str(stack.get('deployed_hash') or ''); latest=str(stack.get('latest_hash') or '')
  remote_errors=stack.get('remote_errors') or []
  completed=final.get('ok') is True and final.get('deploy_status')=='completed'
  idle=not busy.get('repo') and not busy.get('stack')
  runtime=final.get('runtime') or {}
  runtime_confirmed=runtime.get('running') is True
  hashes_consistent=(not deployed) or (not latest) or deployed==latest
  detail=f"status={final.get('deploy_status')} runtime_running={bool(runtime.get('running'))} container={runtime.get('container_name') or '-'} busy_repo={bool(busy.get('repo'))} busy_stack={bool(busy.get('stack'))} deployed={deployed or '-'} latest={latest or '-'} errors={len(remote_errors)}"
  return completed and idle and runtime_confirmed and not (stack.get('missing_files') or []) and not remote_errors and hashes_consistent,detail
 progress(job_path,job,'Verificando a stack no Komodo.',0)
 try:ready,detail=deployment_ready()
 except Exception as exc:ready=False;detail=type(exc).__name__+': '+str(exc)
 if kind in ('onboarding','links'):
  ready=False;detail='Template atualizado; sincronização e novo deploy obrigatórios.'
 if not ready:
  progress(job_path,job,'Atualizando o repositório e reconstruindo a stack.',1,detail)
  deploy_confirmed=False
  if kind in ('onboarding','links'):
   full_payload={**payload,'force_reclone':True,'force_clone':True,'force_rebuild':True,'no_cache':False,'wait_for_completion':True,'max_wait_seconds':600,'poll_interval':5,'reset_reclone_after':False}
   _,deploy_result=request(kbase+'/komodo/project/deploy-full','POST',full_payload,kh,720)
   if isinstance(deploy_result,dict) and deploy_result.get('ok') is False: raise RuntimeError('komodo_full_deploy_failed:'+str(deploy_result)[:700])
   if isinstance(deploy_result,dict):
    local=deploy_result.get('local_health') or ((deploy_result.get('after') or {}).get('local_health') if isinstance(deploy_result.get('after'),dict) else {}) or {}
    if deploy_result.get('ok') is True and deploy_result.get('deploy_status') in ('completed','ready') and local.get('ok') is True:
     final=dict(deploy_result.get('after') or {})
     final.update({'ok':True,'deploy_status':'completed','runtime':{'running':True,'container_name':local.get('container'),'health':local.get('health'),'image':local.get('image')}})
     ready=True;detail=f"status=completed runtime_running=True container={local.get('container') or '-'} health={local.get('health') or '-'} local_reconciled=True"
     deploy_confirmed=True
  else:
   request(kbase+'/komodo/stack/pull','POST',payload,kh,60)
   progress(job_path,job,'Iniciando o deploy da stack.',2,detail)
   request(kbase+'/komodo/stack/deploy','POST',payload,kh,60)
  deadline=time.monotonic()+1200;attempt=2;deploy_retries=0;next_retry=time.monotonic()+45
  while not deploy_confirmed and time.monotonic()<deadline:
   attempt+=1
   try:ready,detail=deployment_ready()
   except Exception as exc:ready=False;detail=type(exc).__name__+': '+str(exc)
   if not ready and time.monotonic() >= next_retry and deploy_retries < 8:
    deploy_retries+=1
    progress(job_path,job,'Repetindo a reconstrução após falha transitória.',attempt,detail)
    if kind in ('onboarding','links'):
     retry_payload={**payload,'force_reclone':True,'force_clone':True,'force_rebuild':True,'wait_for_completion':True,'max_wait_seconds':300,'poll_interval':5,'reset_reclone_after':False}
     request(kbase+'/komodo/project/deploy-full','POST',retry_payload,kh,420)
    else:
     request(kbase+'/komodo/stack/deploy','POST',payload,kh,60)
    next_retry=time.monotonic()+min(180,45*(deploy_retries+1))
   else:
    progress(job_path,job,'Aguardando a confirmação do Komodo.',attempt,detail)
   if ready:break
   time.sleep(5)
  if not deploy_confirmed and not ready: raise RuntimeError('komodo_deploy_not_ready: '+detail)
 progress(job_path,job,'Publicando o endereço inicial.',attempt if 'attempt' in locals() else 1,detail)
 commit=((final.get('stack') or {}).get('deployed_hash') or (final.get('repo') or {}).get('latest_hash') or '')
 if kind=='onboarding': seed_db(tenant)
 nc=envfile('/etc/cloudif/npm-publisher-client.env'); nt=nc.get('NPM_PUBLISHER_TOKEN','');
 _,pub=request('http://10.62.91.3/publish','POST',{'public_number':num,'deploy_number':1},{'Host':'cloudif-publisher.internal','X-CloudIF-Token':nt},240)
 if not pub.get('ok'): raise RuntimeError('npm_publish_failed')
 progress(job_path,job,'Verificando os endereços públicos.',attempt if 'attempt' in locals() else 1)
 for public_url in (pub.get('stable_url'),pub.get('version_url')):
  if not public_url: raise RuntimeError('public_url_missing')
  deadline=time.monotonic()+600;last_status='unknown';health_attempt=0
  while time.monotonic()<deadline:
   health_attempt+=1
   try:
    req=urllib.request.Request(public_url,headers={'User-Agent':'CloudIF-Homologation/1.0'})
    with urllib.request.urlopen(req,timeout=30) as response:
     last_status=str(response.status)
     if response.status==200: break
   except urllib.error.HTTPError as exc:
    last_status=str(exc.code)
    if exc.code not in (404,425,429,500,502,503,504): raise RuntimeError('public_health_status_'+str(exc.code))
   except Exception as exc:
    last_status=type(exc).__name__
   progress(job_path,job,'Aguardando o proxy público ficar saudável.',health_attempt,f'{public_url} status={last_status}')
   time.sleep(min(12,2+health_attempt))
  else: raise RuntimeError('public_health_timeout_'+last_status)
 update_db(slug,tenant,owner,num,commit)
 result={'ok':True,'project':slug,'template_kind':kind,'public_number':num,'stable_url':pub['stable_url'],'version_url':pub['version_url'],'deployed_services':((final.get('stack') or {}).get('deployed_services') or [])}
 out=Path(f'/srv/cloudif/provisioning/projects/{slug}/initial-publication.json'); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()
