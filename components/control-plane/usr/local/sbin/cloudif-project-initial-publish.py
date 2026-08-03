#!/usr/bin/env python3
import json,sqlite3,subprocess,sys,time,urllib.request,urllib.error
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
def update_db(slug,tenant,owner,num,commit=''):
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS project_publications (id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,version TEXT NOT NULL DEFAULT '',commit_sha TEXT NOT NULL DEFAULT '',stable_hostname TEXT NOT NULL,version_hostname TEXT NOT NULL,status TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,published_at TEXT,message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',UNIQUE(project_slug,deploy_number),UNIQUE(version_hostname))''')
 now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 c.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
 c.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug,deploy_number) do update set commit_sha=excluded.commit_sha,status='published',is_active=1,published_at=excluded.published_at,message=excluded.message''',(slug,num,1,'d1',commit,f'{num}.cloudiff.duckdns.org',f'{num}-d1.cloudiff.duckdns.org','published',1,owner,now,now,'Publicação inicial automática',json.dumps({'tenant':tenant})))
 cols=[r[1] for r in c.execute('pragma table_info(projects)')]
 updates={}
 for k,v in {'status':'published','repo_url':f'https://cloudiff.duckdns.org/git/cloudif/cloudif-{slug}','komodo_status':'running','updated_at':now}.items():
  if k in cols: updates[k]=v
 if updates:
  c.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
 c.commit(); c.close()
def main():
 job=json.loads(Path(sys.argv[1]).read_text()); slug=job['slug']; tenant=job['tenant']; owner=(job.get('user') or {}).get('username',''); kind=job.get('template_kind','none'); num=public_number(slug)
 kc=envfile('/etc/cloudif/komodo-agent-client.env'); kbase=(kc.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/'); kt=kc.get('KOMODO_AGENT_TOKEN',''); kh={'X-CloudIF-Token':kt,'Authorization':'Bearer '+kt} if kt else {}
 payload={'project_slug':slug,'project':slug,'slug':slug,'tenant':tenant,'actor':'project-initial-publish','deploy':True,'wait_timeout':600}
 final={}
 def deployment_ready():
  nonlocal final
  try:
   _,final=request(kbase+'/komodo/project/status','POST',payload,kh,30)
  except Exception:
   return False
  stack=final.get('stack') or {}
  busy=final.get('busy') or {}
  deployed=stack.get('deployed_hash') or ''
  latest=stack.get('latest_hash') or ''
  remote_errors=stack.get('remote_errors') or []
  hash_confirmed=bool(deployed) and deployed == latest
  service_confirmed=(
   not deployed and bool(latest) and
   bool(stack.get('latest_services') or stack.get('services'))
  )
  return (
   final.get('ok') is True and
   final.get('deploy_status') == 'completed' and
   not busy.get('repo') and not busy.get('stack') and
   not (stack.get('missing_files') or []) and
   not remote_errors and
   (hash_confirmed or service_confirmed)
  )
 if not deployment_ready():
  request(kbase+'/komodo/stack/pull','POST',payload,kh,90)
  request(kbase+'/komodo/stack/deploy','POST',payload,kh,90)
  for i in range(120):
   if deployment_ready(): break
   if i and i%20==0:
    try: request(kbase+'/komodo/stack/pull','POST',payload,kh,90)
    except Exception: pass
    try: request(kbase+'/komodo/stack/deploy','POST',payload,kh,90)
    except Exception: pass
   time.sleep(5)
  else: raise RuntimeError('komodo_deploy_not_ready')
 commit=((final.get('stack') or {}).get('deployed_hash') or (final.get('repo') or {}).get('latest_hash') or '')
 if kind=='onboarding': seed_db(tenant)
 nc=envfile('/etc/cloudif/npm-publisher-client.env'); nt=nc.get('NPM_PUBLISHER_TOKEN','');
 _,pub=request('http://10.62.91.3/publish','POST',{'public_number':num,'deploy_number':1},{'Host':'cloudif-publisher.internal','X-CloudIF-Token':nt},240)
 if not pub.get('ok'): raise RuntimeError('npm_publish_failed')
 update_db(slug,tenant,owner,num,commit)
 result={'ok':True,'project':slug,'template_kind':kind,'public_number':num,'stable_url':pub['stable_url'],'version_url':pub['version_url'],'deployed_services':((final.get('stack') or {}).get('deployed_services') or [])}
 out=Path(f'/srv/cloudif/provisioning/projects/{slug}/initial-publication.json'); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()
