#!/usr/bin/env python3
import hashlib, json, re, sqlite3, ssl, time, urllib.error, urllib.request
from pathlib import Path
DB=Path('/var/lib/cloudif/portal/cloudif-portal.db')

def _env(path):
    d={}; p=Path(path)
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            s=line.strip()
            if s and not s.startswith('#') and '=' in s:
                k,v=s.split('=',1); d[k.strip()]=v.strip().strip('"\'')
    return d

def _post(url,payload,token,host='',timeout=420):
    h={'Accept':'application/json','Content-Type':'application/json','X-CloudIF-Token':token}
    if host: h['Host']=host
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),method='POST',headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode(errors='ignore'); data=json.loads(raw or '{}')
            return r.status,data
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='ignore')
        try:data=json.loads(raw or '{}')
        except:data={'raw':raw}
        return e.code,data

def _project_allowed(con,slug,user):
    row=con.execute('select * from projects where slug=?',(slug,)).fetchone()
    if not row:return None
    if user.get('admin'):return row
    username=(user.get('username') or '').strip().lower()
    groups={str(x).strip().lower() for x in user.get('groups',[]) if str(x).strip()}
    cols=set(row.keys())
    owners=[]
    for k in ('owner','created_by'):
        if k in cols and row[k]: owners.append(str(row[k]).strip().lower())
    if username and username in owners:return row
    for acl in con.execute('select subject_type,subject from project_acl where slug=?',(slug,)):
        st=str(acl[0] or '').lower(); sub=str(acl[1] or '').strip().lower()
        if st=='user' and sub==username:return row
        if st=='group' and sub in groups:return row
    return None

def _ensure_schema(con):
    con.executescript('''
CREATE TABLE IF NOT EXISTS project_public_ids(project_slug TEXT PRIMARY KEY,public_number INTEGER NOT NULL UNIQUE,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_publications(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,
 version TEXT NOT NULL DEFAULT '',commit_sha TEXT NOT NULL DEFAULT '',stable_hostname TEXT NOT NULL,version_hostname TEXT NOT NULL,
 status TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,published_at TEXT,
 message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',UNIQUE(project_slug,deploy_number),UNIQUE(version_hostname));
CREATE INDEX IF NOT EXISTS idx_project_publications_active ON project_publications(project_slug,is_active,status);
CREATE TABLE IF NOT EXISTS publication_jobs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,actor TEXT NOT NULL,status TEXT NOT NULL,
 step TEXT NOT NULL DEFAULT 'queued',message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT);
CREATE INDEX IF NOT EXISTS idx_publication_jobs_project ON publication_jobs(project_slug,id DESC);
CREATE TABLE IF NOT EXISTS project_publication_aliases(
 alias TEXT PRIMARY KEY,project_slug TEXT NOT NULL UNIQUE,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS publication_job_acknowledgements(
 job_id INTEGER PRIMARY KEY,actor TEXT NOT NULL,acknowledged_at TEXT NOT NULL);
''')

def _number(con,slug):
    r=con.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
    if not r: raise RuntimeError('Número público ausente para o projeto.')
    return int(r[0])

def _clients():
    k=_env('/etc/cloudif/komodo-publication-client.env'); n=_env('/etc/cloudif/npm-publisher-client.env')
    ku=(k.get('KOMODO_PUBLICATION_URL') or 'http://10.62.91.2:18098').rstrip('/'); kt=k.get('KOMODO_PUBLICATION_TOKEN','')
    nt=n.get('NPM_PUBLISHER_TOKEN','')
    if not kt or not nt: raise RuntimeError('Credenciais internas de publicação ausentes.')
    return ku,kt,nt

def _external_ok(host):
    req=urllib.request.Request('https://'+host+'/',headers={'User-Agent':'CloudIF-Publication-Validator/1.0'})
    with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context()) as r:
        body=r.read(200000)
        return r.status==200 and len(body)>0


TARGET_SLUG='atalhos-cloudif-iff1860746'
PRODUCTION_URL='https://cloudiff.duckdns.org/production/atalhos-cloudif-iff1860746/'
def _production_env():return _env('/etc/cloudif/production-public-client.env')
def _production_call(path,payload=None,timeout=180):
 e=_production_env();token=e.get('CLOUDIF_PRODUCTION_PUBLIC_TOKEN','')
 if not token:raise RuntimeError('Token interno de produção ausente.')
 headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};url='http://cloudif-production-public.internal'+path
 req=urllib.request.Request(url,data=(json.dumps(payload).encode() if payload is not None else None),method=('POST' if payload is not None else 'GET'),headers=headers)
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read() or b'{}')
def _latest_production_build(slug):
 c=sqlite3.connect('/var/lib/cloudif/build-broker/builds.sqlite3');c.row_factory=sqlite3.Row
 rows=c.execute("select id,result_json from builds where project_slug=? and status='succeeded' order by created_at desc",(slug,)).fetchall();c.close()
 for r in rows:
  try:x=json.loads(r['result_json'] or '{}')
  except Exception:continue
  if x.get('production_ready') is True and x.get('attestation_verified') is True and x.get('scanner_ready') is True and x.get('scanner_blocked') is False and x.get('sbom_ready') is True and x.get('artifact_image_id'):
   return r['id'],x
 raise RuntimeError('Nenhum build imutável e aprovado está disponível para produção.')
def _publish_production(slug,user):
 con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;project=_project_allowed(con,slug,user);con.close()
 if not project:raise PermissionError('Projeto não encontrado ou sem permissão.')
 if not user.get('admin'):raise PermissionError('Publicação real exige administrador tenant ou professor.')
 build_id,x=_latest_production_build(slug);eid='prd_'+hashlib.sha256((slug+build_id+x['artifact_image_id']+str(time.time_ns())).encode()).hexdigest()[:24]
 result=_production_call('/v1/deploy',{'project_slug':slug,'artifact_image_id':x['artifact_image_id'],'execution_id':eid},240)
 if not result.get('ok'):raise RuntimeError('Executor de produção recusou a publicação.')
 return {'ok':True,'slug':slug,'public_number':0,'deploy_number':int(result.get('release_id') or 0),'stable_url':PRODUCTION_URL,'version_url':PRODUCTION_URL,'commit':build_id,'artifact_image_id':x['artifact_image_id'],'blue_green':True,'external_health':result.get('external_health'),'idempotent':result.get('idempotent') is True}
def rollback_production(slug,user):
 con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;project=_project_allowed(con,slug,user);con.close()
 if not project or not user.get('admin'):raise PermissionError('Rollback real exige administrador tenant ou professor.')
 eid='prb_'+hashlib.sha256((slug+str(time.time_ns())).encode()).hexdigest()[:24];return _production_call('/v1/rollback',{'project_slug':slug,'execution_id':eid},240)
def production_status(slug):
 if slug!=TARGET_SLUG:return None
 try:return _production_call('/v1/status')
 except Exception:return {'ok':False,'public_url':PRODUCTION_URL,'public_traffic':False}

def publish_now(slug,user,progress=None):
    def notify(step,message):
        if progress:
            progress(step,message)
    notify('preparing','Validando projeto e preparando a publicação.')
    if slug==TARGET_SLUG:return _publish_production(slug,user)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; _ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project: con.close(); raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug)
    dep=int(con.execute('select coalesce(max(deploy_number),0)+1 from project_publications where project_slug=?',(slug,)).fetchone()[0])
    actor=user.get('username') or 'portal'; ku,kt,nt=_clients()
    notify('deploying','Agente de hospedagem criando a versão imutável.')
    status,kres=_post(ku+'/komodo/publication/deploy',{'project':slug,'public_number':num,'deploy_number':dep,'timeout':300},kt,timeout=420)
    if status//100!=2 or not kres.get('ok'):
        con.close(); raise RuntimeError('Falha no deploy versionado: '+json.dumps(kres,ensure_ascii=False)[:500])
    notify('https','Configurando HTTPS e endereços públicos.')
    alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone()
    alias=str(alias_row[0]) if alias_row else ''
    status,nres=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if status//100!=2 or not nres.get('ok'):
        con.close(); raise RuntimeError('Falha na publicação HTTPS: '+json.dumps(nres,ensure_ascii=False)[:500])
    version_host=f'{num}-d{dep}.cloudiff.duckdns.org'
    if not _external_ok(version_host):
        con.close(); raise RuntimeError('Validação HTTPS externa falhou para '+version_host)
    notify('promoting','Ativando a nova versão com rollback disponível.')
    status,pres=_post(ku+'/komodo/publication/promote',{'public_number':num,'deploy_number':dep},kt,timeout=120)
    if status//100!=2 or not pres.get('ok'):
        con.close(); raise RuntimeError('Falha ao promover a publicação: '+json.dumps(pres,ensure_ascii=False)[:500])
    notify('validating','Validando o endereço público.')
    stable_host=f'{num}.cloudiff.duckdns.org'
    if not _external_ok(stable_host):
        con.close(); raise RuntimeError('Validação da URL estável falhou após promoção.')
    now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); commit=str(kres.get('commit') or '')
    republished=bool(kres.get('republished'));republished_from=kres.get('republished_from')
    publication_message=('Republicação do mesmo código da d'+str(republished_from) if republished and republished_from is not None else 'Nova revisão publicada a partir do Git')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    con.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json)
 values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(slug,num,dep,f'd{dep}',commit,stable_host,version_host,'published',1,actor,now,now,publication_message,json.dumps({'komodo':kres,'npm':nres,'promotion':pres,'republished':republished,'republished_from':republished_from},ensure_ascii=False)))
    cols=[x[1] for x in con.execute('pragma table_info(projects)')]
    updates={k:v for k,v in {'status':'published','komodo_status':'running','updated_at':now}.items() if k in cols}
    if updates: con.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
    con.commit(); con.close()
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':dep,'stable_url':'https://'+stable_host+'/','version_url':'https://'+version_host+'/','alias':alias,'alias_url':('https://'+alias+'.cloudiff.duckdns.org/' if alias else ''),'commit':commit,'republished':republished,'republished_from':republished_from,'message':publication_message}

def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def enqueue_publish(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    active=con.execute("select id from publication_jobs where project_slug=? and status in ('queued','running') order by id desc limit 1",(slug,)).fetchone()
    if active:
        job_id=int(active[0]);con.close();return {'ok':True,'queued':True,'job_id':job_id,'existing':True}
    actor=user.get('username') or 'portal';now=_now()
    cur=con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at) values(?,?,?,?,?,?)",(slug,actor,'queued','queued','Solicitação recebida.',now))
    con.commit();job_id=int(cur.lastrowid);con.close()
    return {'ok':True,'queued':True,'job_id':job_id,'existing':False}

def latest_job(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    row=con.execute("""select j.* from publication_jobs j
        left join publication_job_acknowledgements a on a.job_id=j.id
        where j.project_slug=? and a.job_id is null order by j.id desc limit 1""",(slug,)).fetchone();con.close()
    return dict(row) if row else None

def acknowledge_job(slug,job_id,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    job=con.execute('select id,status from publication_jobs where id=? and project_slug=?',(int(job_id),slug)).fetchone()
    if not job:con.close();raise ValueError('Publicação não encontrada.')
    if job['status'] not in ('succeeded','failed'):con.close();raise ValueError('A publicação ainda está em andamento.')
    con.execute('insert or replace into publication_job_acknowledgements(job_id,actor,acknowledged_at) values(?,?,?)',(int(job_id),user.get('username') or 'portal',_now()))
    con.commit();con.close();return {'ok':True,'job_id':int(job_id)}

def claim_next_job():
    con=sqlite3.connect(DB,timeout=30);con.row_factory=sqlite3.Row;_ensure_schema(con)
    con.execute('begin immediate')
    stale=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()-1800))
    con.execute("update publication_jobs set status='queued',step='queued',message='Job recuperado após reinício do worker.',started_at=null where status='running' and started_at<?",(stale,))
    row=con.execute("select * from publication_jobs where status='queued' order by id limit 1").fetchone()
    if not row:con.commit();con.close();return None
    con.execute("update publication_jobs set status='running',step='preparing',message='Preparando publicação.',started_at=? where id=? and status='queued'",(_now(),row['id']))
    con.commit();result=dict(row);result['status']='running';con.close();return result

def _job_update(job_id,status=None,step=None,message=None,detail=None,finished=False):
    con=sqlite3.connect(DB);_ensure_schema(con);sets=[];vals=[]
    for key,value in (('status',status),('step',step),('message',message),('detail_json',json.dumps(detail or {},ensure_ascii=False) if detail is not None else None)):
        if value is not None:sets.append(key+'=?');vals.append(value)
    if finished:sets.append('finished_at=?');vals.append(_now())
    vals.append(job_id);con.execute('update publication_jobs set '+','.join(sets)+' where id=?',vals);con.commit();con.close()

def run_job(job):
    job_id=int(job['id']);slug=job['project_slug'];actor=job['actor']
    user={'username':actor,'groups':[],'admin':False}
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
        row=con.execute('select owner,created_by from projects where slug=?',(slug,)).fetchone();con.close()
        if row and actor not in {(row['owner'] or ''),(row['created_by'] or '')}:user['admin']=True
        def progress(step,message):
            _job_update(job_id,status='running',step=step,message=message)
        result=publish_now(slug,user,progress=progress)
        _job_update(job_id,status='succeeded',step='completed',message='Site publicado e ativado.',detail=result,finished=True)
        return result
    except Exception as exc:
        _job_update(job_id,status='failed',step='failed',message=str(exc),detail={'error':type(exc).__name__,'message':str(exc)[:800]},finished=True)
        return None

def set_alias(slug,alias,user):
    alias=str(alias or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',alias):raise ValueError('Alias inválido. Use letras minúsculas, números e hífen.')
    if alias in {'www','api','admin','cloudiff','auth','login','status','mail'}:raise ValueError('Alias reservado.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    other=con.execute('select project_slug from project_publication_aliases where alias=? and project_slug<>?',(alias,slug)).fetchone()
    if other:con.close();raise ValueError('Este alias já está em uso.')
    now=_now();actor=user.get('username') or 'portal'
    previous=con.execute('select alias,created_by,created_at,updated_at from project_publication_aliases where project_slug=?',(slug,)).fetchone()
    pub=con.execute('select public_number,deploy_number from project_publications where project_slug=? and is_active=1 order by id desc limit 1',(slug,)).fetchone()
    if pub:
        _,_,nt=_clients();status,data=_post('http://10.62.91.3/alias',{'public_number':int(pub['public_number']),'deploy_number':int(pub['deploy_number']),'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
        if status//100!=2 or not data.get('ok'):
            con.close()
            raise RuntimeError('Falha ao ativar alias HTTPS: '+json.dumps(data,ensure_ascii=False)[:500])
    con.execute('insert into project_publication_aliases(alias,project_slug,created_by,created_at,updated_at) values(?,?,?,?,?) on conflict(project_slug) do update set alias=excluded.alias,updated_at=excluded.updated_at',(alias,slug,actor,(previous['created_at'] if previous else now),now))
    con.commit();con.close()
    result={'ok':True,'alias':alias,'hostname':alias+'.cloudiff.duckdns.org'}
    if pub:result.update(data)
    return result

def activate(slug,deploy_number,user):
    if slug==TARGET_SLUG:raise RuntimeError('Use o rollback blue/green da produção real.')
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; _ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project: con.close(); raise PermissionError('Projeto não encontrado ou sem permissão.')
    row=con.execute('select * from project_publications where project_slug=? and deploy_number=? and status=?',(slug,int(deploy_number),'published')).fetchone()
    if not row: con.close(); raise RuntimeError('Publicação não encontrada ou não está válida.')
    num=int(row['public_number']); ku,kt,nt=_clients()
    status,pres=_post(ku+'/komodo/publication/promote',{'public_number':num,'deploy_number':int(deploy_number)},kt,timeout=120)
    if status//100!=2 or not pres.get('ok'):
        con.close(); raise RuntimeError('Falha ao ativar versão: '+json.dumps(pres,ensure_ascii=False)[:500])
    alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone()
    alias=str(alias_row[0]) if alias_row else ''
    _post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':int(deploy_number),'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if not _external_ok(f'{num}.cloudiff.duckdns.org'):
        con.close(); raise RuntimeError('URL estável falhou após ativação.')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    con.execute('update project_publications set is_active=1,message=? where project_slug=? and deploy_number=?',('Ativada manualmente pelo Portal',slug,int(deploy_number)))
    con.commit(); con.close()
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':int(deploy_number),'stable_url':f'https://{num}.cloudiff.duckdns.org/'}
