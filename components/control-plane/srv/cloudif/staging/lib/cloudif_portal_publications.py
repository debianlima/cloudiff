#!/usr/bin/env python3
import json, sqlite3, ssl, time, urllib.error, urllib.request
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

def publish(slug,user):
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; _ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project: con.close(); raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug)
    dep=int(con.execute('select coalesce(max(deploy_number),0)+1 from project_publications where project_slug=?',(slug,)).fetchone()[0])
    actor=user.get('username') or 'portal'; ku,kt,nt=_clients()
    status,kres=_post(ku+'/komodo/publication/deploy',{'project':slug,'public_number':num,'deploy_number':dep,'timeout':300},kt,timeout=420)
    if status//100!=2 or not kres.get('ok'):
        con.close(); raise RuntimeError('Falha no deploy versionado: '+json.dumps(kres,ensure_ascii=False)[:500])
    status,nres=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep},nt,host='cloudif-publisher.internal',timeout=300)
    if status//100!=2 or not nres.get('ok'):
        con.close(); raise RuntimeError('Falha na publicação HTTPS: '+json.dumps(nres,ensure_ascii=False)[:500])
    version_host=f'{num}-d{dep}.cloudiff.duckdns.org'
    if not _external_ok(version_host):
        con.close(); raise RuntimeError('Validação HTTPS externa falhou para '+version_host)
    status,pres=_post(ku+'/komodo/publication/promote',{'public_number':num,'deploy_number':dep},kt,timeout=120)
    if status//100!=2 or not pres.get('ok'):
        con.close(); raise RuntimeError('Falha ao promover a publicação: '+json.dumps(pres,ensure_ascii=False)[:500])
    stable_host=f'{num}.cloudiff.duckdns.org'
    if not _external_ok(stable_host):
        con.close(); raise RuntimeError('Validação da URL estável falhou após promoção.')
    now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); commit=str(kres.get('commit') or '')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    con.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json)
 values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(slug,num,dep,f'd{dep}',commit,stable_host,version_host,'published',1,actor,now,now,'Publicação versionada pelo Portal',json.dumps({'komodo':kres,'npm':nres,'promotion':pres},ensure_ascii=False)))
    cols=[x[1] for x in con.execute('pragma table_info(projects)')]
    updates={k:v for k,v in {'status':'published','komodo_status':'running','updated_at':now}.items() if k in cols}
    if updates: con.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
    con.commit(); con.close()
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':dep,'stable_url':'https://'+stable_host+'/','version_url':'https://'+version_host+'/','commit':commit}

def activate(slug,deploy_number,user):
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; _ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project: con.close(); raise PermissionError('Projeto não encontrado ou sem permissão.')
    row=con.execute('select * from project_publications where project_slug=? and deploy_number=? and status=?',(slug,int(deploy_number),'published')).fetchone()
    if not row: con.close(); raise RuntimeError('Publicação não encontrada ou não está válida.')
    num=int(row['public_number']); ku,kt,nt=_clients()
    status,pres=_post(ku+'/komodo/publication/promote',{'public_number':num,'deploy_number':int(deploy_number)},kt,timeout=120)
    if status//100!=2 or not pres.get('ok'):
        con.close(); raise RuntimeError('Falha ao ativar versão: '+json.dumps(pres,ensure_ascii=False)[:500])
    _post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':int(deploy_number)},nt,host='cloudif-publisher.internal',timeout=300)
    if not _external_ok(f'{num}.cloudiff.duckdns.org'):
        con.close(); raise RuntimeError('URL estável falhou após ativação.')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    con.execute('update project_publications set is_active=1,message=? where project_slug=? and deploy_number=?',('Ativada manualmente pelo Portal',slug,int(deploy_number)))
    con.commit(); con.close()
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':int(deploy_number),'stable_url':f'https://{num}.cloudiff.duckdns.org/'}
