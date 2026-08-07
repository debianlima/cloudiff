#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, sqlite3, subprocess, tarfile, tempfile, urllib.request
from pathlib import Path

DB=Path('/var/lib/cloudif/portal/cloudif-portal.db')
ROOT=Path('/srv/cloudif/managed-backups/projects')
STATE=Path('/var/lib/cloudif/portal/project-backup-settings.json')
REMOTE_ENV=Path('/etc/cloudif/project-backup-remote.env')

def now(): return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')
def stamp(): return dt.datetime.now().strftime('%Y%m%d-%H%M%S')
def safe(v):
    x=re.sub(r'[^A-Za-z0-9_.-]+','-',str(v or '')).strip('-')
    if not x: raise ValueError('invalid_value')
    return x[:180]
def load_state():
    try: return json.loads(STATE.read_text())
    except Exception: return {'projects':{}}
def save_state(d):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)); os.chmod(tmp,0o600); tmp.replace(STATE)
def db_rows(sql,args=()):
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    try: return [dict(x) for x in c.execute(sql,args)]
    finally: c.close()
def project(slug):
    rows=db_rows('select * from projects where slug=?',(slug,))
    if not rows: raise SystemExit('project_not_found')
    return rows[0]
def publications(slug):
    try: return db_rows('select * from project_publications where project_slug=? order by deploy_number',(slug,))
    except Exception: return []
def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def write_manifest(path,meta):
    side=Path(str(path)+'.json'); side.write_text(json.dumps(meta,ensure_ascii=False,indent=2)); os.chmod(side,0o600)
def run(cmd,**kw): return subprocess.run(cmd,check=True,text=kw.pop('text',True),**kw)
def owner_for(p): return safe(p.get('owner') or p.get('tenant') or p.get('tenant_default'))
def tenant_for(p): return safe(p.get('tenant') or p.get('tenant_default') or p.get('owner'))
def backup_basename(p,slug,container,kind,st):
    return f'{owner_for(p)}__{safe(slug)}__{safe(container)}__{safe(kind)}__{safe(st)}'
def db_container(tenant):
    candidates=[f'cloudif_{tenant}-db-1']
    if tenant=='akadmin': candidates.insert(0,'supabase-db')
    names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines()
    return next((x for x in candidates if x in names),None)
def container_metadata(names):
    out=[]
    for name in names:
        try:
            raw=subprocess.check_output(['docker','inspect',name],text=True,timeout=20)
            x=json.loads(raw)[0]; state=x.get('State') or {}; cfg=x.get('Config') or {}; ns=x.get('NetworkSettings') or {}
            ports=[]
            for k,vals in (ns.get('Ports') or {}).items():
                for v in vals or []: ports.append({'container':k,'host_ip':v.get('HostIp') or '', 'host_port':v.get('HostPort') or ''})
            out.append({'name':name,'image':cfg.get('Image') or '', 'created':x.get('Created') or '', 'status':state.get('Status') or '', 'health':((state.get('Health') or {}).get('Status') or ''), 'ports':ports, 'networks':sorted((ns.get('Networks') or {}).keys())})
        except Exception as e: out.append({'name':name,'error':str(e)[:120]})
    return out
def make_database(slug,p,dest):
    tenant=tenant_for(p); c=db_container(tenant)
    if not c: return None,{'type':'database','status':'container_not_found','tenant':tenant}
    st=stamp(); tmp=Path(tempfile.mkdtemp(prefix='cloudif-db-'))
    try:
        t=tmp/'database'; t.mkdir()
        with open(t/'globals.sql','wb') as f: subprocess.run(['docker','exec',c,'sh','-lc','pg_dumpall -U "$POSTGRES_USER" --globals-only'],stdout=f,check=True)
        names=subprocess.check_output(['docker','exec',c,'sh','-lc','psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where datistemplate=false order by datname"'],text=True).splitlines()
        (t/'databases.txt').write_text('\n'.join(names)+'\n')
        for name in names:
            fn=t/(backup_basename(p,slug,c,'database-'+safe(name),st)+'.dump')
            with open(fn,'wb') as f: subprocess.run(['docker','exec',c,'sh','-lc','pg_dump -U "$POSTGRES_USER" -Fc --no-owner --no-privileges -d "$1"','sh',name],stdout=f,check=True)
        (t/'backup-metadata.json').write_text(json.dumps({'owner':owner_for(p),'project':slug,'tenant':tenant,'container':c,'created_at':now(),'databases':names},ensure_ascii=False,indent=2))
        path=dest/(backup_basename(p,slug,c,'database',st)+'.tar.gz')
        with tarfile.open(path,'w:gz') as tar: tar.add(t,arcname='database')
        os.chmod(path,0o600)
        meta={'type':'database','status':'ready','owner':owner_for(p),'project':slug,'tenant':tenant,'container':c,'created_at':now(),'size':path.stat().st_size,'sha256':sha256(path),'filename':path.name}
        write_manifest(path,meta); return path,meta
    finally: shutil.rmtree(tmp,ignore_errors=True)
def remote_publication_metadata(public_numbers):
    env={}
    try:
        for line in Path('/etc/cloudif/komodo-publication-client.env').read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1); env[k.strip()]=v.strip().strip('"\'')
    except Exception: return []
    token=env.get('KOMODO_PUBLICATION_TOKEN') or env.get('CLOUDIF_PUBLICATION_TOKEN') or ''
    base=(env.get('KOMODO_PUBLICATION_URL') or env.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/')
    if not token:return []
    try:
        req=urllib.request.Request(base+'/komodo/containers/telemetry?prefix=cloudif-p',headers={'X-CloudIF-Token':token})
        with urllib.request.urlopen(req,timeout=30) as r: items=json.loads(r.read().decode()).get('items') or []
    except Exception:return []
    allowed={int(x) for x in public_numbers}
    out=[]
    for row in items:
        m=re.match(r'^cloudif-p(\d+)-d\d+-web$',row.get('name') or '')
        if m and int(m.group(1)) in allowed: out.append(row)
    return out

def tenant_container_metadata(tenant):
    prefix=f'cloudif_{safe(tenant)}-'
    names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines()
    return container_metadata(sorted(x for x in names if x.startswith(prefix)))

def make_application(slug,p,dest):
    st=stamp(); tmp=Path(tempfile.mkdtemp(prefix='cloudif-app-'))
    try:
        root=tmp/'application'; root.mkdir()
        pubs=publications(slug)
        (root/'project.json').write_text(json.dumps({**p,'backup_owner':owner_for(p),'backup_project':slug,'backup_container_scope':'all-containers'},ensure_ascii=False,indent=2))
        (root/'publications.json').write_text(json.dumps(pubs,ensure_ascii=False,indent=2))
        nums=sorted({int(x['public_number']) for x in pubs if x.get('public_number')})
        names=[]
        allnames=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines()
        for n in nums: names.extend(x for x in allnames if re.match(rf'^cloudif-p{n}-d\d+-web$',x))
        remote_containers=remote_publication_metadata(nums)
        tenant_containers=tenant_container_metadata(tenant_for(p))
        (root/'publication-containers.json').write_text(json.dumps(remote_containers or container_metadata(sorted(set(names))),ensure_ascii=False,indent=2))
        (root/'tenant-containers.json').write_text(json.dumps(tenant_containers,ensure_ascii=False,indent=2))
        artifacts=root/'artifacts'; artifacts.mkdir()
        def _ignore_sensitive(path,names):
            hidden={'.git','node_modules','__pycache__','.venv','venv','keys','secrets'}
            out=[]
            for name in names:
                low=name.lower()
                if name in hidden or (low.startswith('.env') or low.endswith('.env')) or low.endswith(('.key','.pem','.p12','.pfx','.jks')) or any(x in low for x in ('secret','token','credential','password')):
                    out.append(name)
            return out
        prov=Path('/srv/cloudif/provisioning/projects')/slug
        if prov.exists(): shutil.copytree(prov,artifacts/'provisioning',symlinks=False,ignore=_ignore_sensitive)
        for n in nums:
            src=Path('/srv/cloudif/publications')/f'p{n}'
            if src.exists(): shutil.copytree(src,artifacts/f'publication-p{n}',symlinks=False,ignore=_ignore_sensitive)
        path=dest/(backup_basename(p,slug,'all-containers','application',st)+'.tar.gz')
        with tarfile.open(path,'w:gz') as tar: tar.add(root,arcname='application')
        os.chmod(path,0o600)
        meta={'type':'application','status':'ready','owner':owner_for(p),'project':slug,'container_scope':'all-containers','created_at':now(),'size':path.stat().st_size,'sha256':sha256(path),'filename':path.name,'public_numbers':nums,'containers':len(remote_containers or names),'tenant_containers':len(tenant_containers)}
        write_manifest(path,meta); return path,meta
    finally: shutil.rmtree(tmp,ignore_errors=True)
def remote_config():
    env={}
    if REMOTE_ENV.exists():
        for line in REMOTE_ENV.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1); env[k.strip()]=v.strip().strip('"\'')
    return {'host':env.get('REMOTE_HOST','10.68.128.250'),'port':int(env.get('REMOTE_PORT') or 22),'user':env.get('REMOTE_USER',''),'path':env.get('REMOTE_PATH',''),'key':env.get('REMOTE_KEY',''),'enabled':env.get('REMOTE_ENABLED','1')=='1'}

def remote_probe():
    cfg=remote_config(); reachable=False
    if cfg['enabled'] and cfg['host']:
        try: reachable=subprocess.run(['nc','-z','-w','3',cfg['host'],str(cfg['port'])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode==0
        except Exception: reachable=False
    ready=bool(cfg['user'] and cfg['path'] and cfg['key'])
    status='disabled' if not cfg['enabled'] else 'server_offline' if not reachable else 'pending_configuration' if not ready else 'online'
    return {'requested':True,'configured':bool(cfg['host']),'reachable':reachable,'ready':ready,'status':status,'server':cfg['host'],'port':cfg['port']}

def remote_status(slug,files):
    probe=remote_probe(); cfg=remote_config()
    if probe['status']!='online': return probe
    cmd=['rsync','-a','--chmod=F600','-e',f"ssh -p {cfg['port']} -i {cfg['key']} -o BatchMode=yes -o StrictHostKeyChecking=yes"]+[str(x) for x in files]+[f"{cfg['user']}@{cfg['host']}:{cfg['path'].rstrip('/')}/{slug}/"]
    r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    probe.update({'status':'synced' if r.returncode==0 else 'sync_failed','detail':r.stderr[-180:] if r.returncode else ''})
    return probe

def backup(slug):
    slug=safe(slug); p=project(slug); dest=ROOT/slug; dest.mkdir(parents=True,exist_ok=True); os.chmod(dest,0o700)
    files=[]; metas=[]
    for fn in (make_database,make_application):
        path,meta=fn(slug,p,dest); metas.append(meta)
        if path: files.extend([path,Path(str(path)+'.json')])
    state=load_state(); cfg=state.setdefault('projects',{}).setdefault(slug,{})
    cfg['last_run']=now(); cfg['last_result']=metas
    if cfg.get('remote_requested'): cfg['remote']=remote_status(slug,files)
    save_state(state)
    cutoff=dt.datetime.now().timestamp()-14*86400
    for f in dest.iterdir():
        if not f.is_file():
            continue
        if f.name == 'MARCO_ZERO.json' or 'marco-zero' in f.name:
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
    return {'ok':True,'project':slug,'backups':metas,'remote':cfg.get('remote')}
def listing(slug):
    slug=safe(slug); dest=ROOT/slug; items=[]
    if dest.exists():
        for f in sorted(dest.glob('*.tar.gz'),key=lambda x:x.stat().st_mtime,reverse=True):
            meta={}
            try: meta=json.loads(Path(str(f)+'.json').read_text())
            except Exception: pass
            items.append({'filename':f.name,'size':f.stat().st_size,'modified':dt.datetime.fromtimestamp(f.stat().st_mtime,dt.timezone.utc).astimezone().isoformat(timespec='seconds'),'type':meta.get('type') or ('database' if ('database' in f.name and 'application' not in f.name) else 'application'),'sha256':meta.get('sha256') or sha256(f)})
    cfg=load_state().get('projects',{}).get(slug,{})
    if cfg.get('remote_requested'): cfg['remote']=remote_probe()
    return {'ok':True,'project':slug,'settings':cfg,'items':items}
def set_auto(slug,enabled,remote_requested=None):
    slug=safe(slug); project(slug); d=load_state(); cfg=d.setdefault('projects',{}).setdefault(slug,{})
    cfg['enabled']=bool(enabled); cfg['updated_at']=now()
    if remote_requested is not None:
        cfg['remote_requested']=bool(remote_requested)
        if remote_requested: cfg['remote']={'requested':True,'status':'server_offline','server':'10.68.128.250'}
    save_state(d); return {'ok':True,'project':slug,'settings':cfg}
def run_enabled():
    d=load_state(); out=[]
    for slug,cfg in d.get('projects',{}).items():
        if cfg.get('enabled'):
            try: out.append(backup(slug))
            except Exception as e: out.append({'ok':False,'project':slug,'error':str(e)[:180]})
    return {'ok':all(x.get('ok') for x in out),'results':out}
def enable_all():
    d=load_state(); rows=db_rows('select slug from projects')
    for r in rows:
        cfg=d.setdefault('projects',{}).setdefault(r['slug'],{}); cfg.update({'enabled':True,'remote_requested':True,'remote':{'requested':True,'status':'server_offline','server':'10.68.128.250'},'updated_at':now()})
    save_state(d); return {'ok':True,'projects':len(rows)}

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='op',required=True)
    for op in ('backup','list'):
        p=sub.add_parser(op); p.add_argument('--slug',required=True)
    p=sub.add_parser('set-auto'); p.add_argument('--slug',required=True); p.add_argument('--enabled',choices=('0','1'),required=True); p.add_argument('--remote-requested',choices=('0','1'))
    sub.add_parser('run-enabled'); sub.add_parser('enable-all')
    a=ap.parse_args()
    if a.op=='backup': x=backup(a.slug)
    elif a.op=='list': x=listing(a.slug)
    elif a.op=='set-auto': x=set_auto(a.slug,a.enabled=='1',None if a.remote_requested is None else a.remote_requested=='1')
    elif a.op=='run-enabled': x=run_enabled()
    else: x=enable_all()
    print(json.dumps(x,ensure_ascii=False))
if __name__=='__main__': main()
