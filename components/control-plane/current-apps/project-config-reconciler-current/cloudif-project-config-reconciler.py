#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,re,sqlite3,time,urllib.error,urllib.parse,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

HOST=os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILER_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILER_PORT','18229'))
TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILER_TOKEN','')
CONFIG_DB=Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_DB','/var/lib/cloudif/project-config/config.db'))
CONTROL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
BUILD_DB=Path(os.environ.get('CLOUDIF_BUILD_DB','/var/lib/cloudif/build-broker/builds.sqlite3'))
INTERVAL=max(2,min(int(os.environ.get('CLOUDIF_PROJECT_CONFIG_RECONCILE_INTERVAL','10')),300))
SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
SECRET_NAME=re.compile(r'(?i)(password|secret|token|private|jwt|service[_-]?role|api[_-]?key|access[_-]?key|signing[_-]?key)')

def now():return int(time.time())
def connect(path,readonly=False):
    if readonly:
        conn=sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=20)
    else:conn=sqlite3.connect(path,timeout=20)
    conn.row_factory=sqlite3.Row;conn.execute('pragma busy_timeout=20000');return conn

def init_db():
    conn=connect(CONFIG_DB)
    conn.execute('''create table if not exists reconciliation_state(project_slug text primary key,status text not null,config_revision integer not null,membership_revision integer not null,config_digest text,toolchain_digest text,acl_digest text,latest_build_job_id text,latest_build_status text,required_actions_json text not null,checks_json text not null,updated_at integer not null)''')
    conn.execute('create index if not exists idx_config_reconciliation_state on reconciliation_state(status,updated_at)')
    conn.commit();conn.close()

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def acl_snapshot(slug):
    conn=connect(CONTROL_DB,True);project=conn.execute('select project_id,owner,tenant,status from projects where slug=?',(slug,)).fetchone()
    if not project:conn.close();raise LookupError('project_not_found')
    acl=[dict(row) for row in conn.execute('select subject_type,subject,role from project_acl where project_id=? order by subject_type,subject,role',(project['project_id'],)).fetchall()];conn.close()
    material={'owner':project['owner'],'tenant':project['tenant'],'status':project['status'],'acl':acl}
    return hashlib.sha256(canonical(material)).hexdigest(),len(acl)
def latest_build(slug,config_revision,config_digest,toolchain_digest):
    if not BUILD_DB.exists():return None
    conn=connect(BUILD_DB,True)
    try:rows=conn.execute("select job_id,status,config_revision,config_digest,toolchain_digest,archive_sha256,result_json,updated_at from multiservice_jobs where project_slug=? order by updated_at desc limit 50",(slug,)).fetchall()
    except sqlite3.Error:rows=[]
    conn.close()
    for row in rows:
        if int(row['config_revision'])==config_revision and row['config_digest']==config_digest and row['toolchain_digest']==toolchain_digest:
            return dict(row)
    return None
def configuration(slug):
    conn=connect(CONFIG_DB);project=conn.execute('select * from projects where project_slug=?',(slug,)).fetchone()
    revision=None
    if project and int(project['current_revision'])>0:revision=conn.execute('select * from revisions where project_slug=? and revision=?',(slug,project['current_revision'])).fetchone()
    conn.close();return project,revision
def required_refs(effective):
    if not isinstance(effective,dict):
        return []
    env=effective.get('environment') or {}
    required=env.get('required') or {}
    global_variables=set((env.get('variables') or {}).keys())
    services=effective.get('services') or {}
    result=[]
    covered=set()
    for name,spec in required.items():
        if not isinstance(spec,dict):
            spec={}
        ref=str(spec.get('secretRef') or spec.get('configRef') or '')
        targets=sorted(str(x) for x in (spec.get('services') or services.keys()))
        result.append({
            'name':str(name),'reference':ref,
            'kind':'secret' if spec.get('secretRef') else 'config',
            'services':targets,'configured':bool(ref),
        })
        covered.add(str(name))
    for service_name,service in services.items():
        if not isinstance(service,dict):
            continue
        service_env=service.get('environment') or {}
        service_variables=set((service_env.get('variables') or {}).keys())
        for name in service_env.get('required') or []:
            name=str(name)
            if name in covered:
                continue
            configured=name in service_variables or name in global_variables
            result.append({
                'name':name,'reference':'declared-variable' if configured else '',
                'kind':'variable','services':[str(service_name)],'configured':configured,
            })
    return result
def hooks(effective):
    output=[]
    for phase,items in ((effective.get('hooks') or {}) if isinstance(effective,dict) else {}).items():
        for item in items or []:
            if isinstance(item,dict):output.append({'phase':phase,'service':item.get('service'),'script':item.get('script'),'argv':item.get('run')})
    return output
def previous_state(slug):
    conn=connect(CONFIG_DB)
    try:
        row=conn.execute('select * from reconciliation_state where project_slug=?',(slug,)).fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def reconcile(slug,event_id=''):
    if not SLUG.fullmatch(slug):raise ValueError('invalid_project_slug')
    project,revision=configuration(slug);acl_digest,acl_count=acl_snapshot(slug);prior=previous_state(slug)
    config_revision=int(project['current_revision']) if project else 0;membership_revision=int(project['membership_revision']) if project else 0
    checks={'projectExists':True,'configured':bool(revision),'aclSnapshot':True,'aclCount':acl_count,'aclChanged':bool(prior and prior.get('acl_digest')!=acl_digest),'membershipRevisionChanged':bool(prior and int(prior.get('membership_revision') or 0)!=membership_revision),'secretValuesRead':False,'containersChanged':False}
    actions=[];status='ready';config_digest=project['config_digest'] if project else None;toolchain_digest=project['toolchain_digest'] if project else None;latest=None
    if not revision:
        status='configuration_required';actions.append('review_and_apply_manifest')
    else:
        effective=json.loads(revision['effective_json'] or '{}');refs=required_refs(effective);hook_list=hooks(effective)
        hooks_versioned=all(bool(x.get('script')) and not x.get('argv') for x in hook_list)
        checks.update({
            'requiredReferences':[{'name':x['name'],'kind':x['kind'],'services':x['services'],'configured':bool(x.get('configured'))} for x in refs],
            'hookCount':len(hook_list),'hooksVersioned':hooks_versioned,
        })
        unresolved=sorted({x['name'] for x in refs if not x.get('configured')})
        if unresolved:
            status='secret_reference_unresolved';actions.append('configure_required_references')
        if not hooks_versioned:
            status='hook_configuration_invalid';actions.append('version_hooks_in_repository')
        latest=latest_build(slug,config_revision,config_digest,toolchain_digest)
        checks['matchingBuild']=bool(latest);checks['matchingBuildSucceeded']=bool(latest and latest['status']=='succeeded')
        if not latest:
            if status=='ready':status='toolchain_build_required'
            actions.append('create_multiservice_build')
        elif latest['status']!='succeeded':
            if status=='ready':status='application_build_required'
            actions.append('complete_multiservice_build')
    state={'projectSlug':slug,'status':status,'configRevision':config_revision,'membershipRevision':membership_revision,'configDigest':config_digest,'toolchainDigest':toolchain_digest,'aclDigest':acl_digest,'latestBuildJobId':latest['job_id'] if latest else None,'latestBuildStatus':latest['status'] if latest else None,'requiredActions':sorted(set(actions)),'checks':checks,'updatedAt':now(),'secretsExposed':False}
    conn=connect(CONFIG_DB);conn.execute('''insert into reconciliation_state(project_slug,status,config_revision,membership_revision,config_digest,toolchain_digest,acl_digest,latest_build_job_id,latest_build_status,required_actions_json,checks_json,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug) do update set status=excluded.status,config_revision=excluded.config_revision,membership_revision=excluded.membership_revision,config_digest=excluded.config_digest,toolchain_digest=excluded.toolchain_digest,acl_digest=excluded.acl_digest,latest_build_job_id=excluded.latest_build_job_id,latest_build_status=excluded.latest_build_status,required_actions_json=excluded.required_actions_json,checks_json=excluded.checks_json,updated_at=excluded.updated_at''',(slug,status,config_revision,membership_revision,config_digest,toolchain_digest,acl_digest,state['latestBuildJobId'],state['latestBuildStatus'],json.dumps(state['requiredActions'],separators=(',',':')),json.dumps(checks,ensure_ascii=False,separators=(',',':')),state['updatedAt']))
    conn.execute('update projects set observation_status=?,updated_at=? where project_slug=?',(status,state['updatedAt'],slug))
    if event_id:conn.execute('update reconciliation_events set status=?,details_json=?,finished_at=? where event_id=?',(status,json.dumps({'reconciliation':state,'secretValuesIncluded':False},ensure_ascii=False,separators=(',',':')),state['updatedAt'],event_id))
    conn.commit();conn.close();return state
def process_pending(limit=50):
    conn=connect(CONFIG_DB);rows=conn.execute("select event_id,project_slug from reconciliation_events where status='pending' order by created_at limit ?",(limit,)).fetchall();conn.close();results=[]
    for row in rows:
        try:results.append(reconcile(row['project_slug'],row['event_id']))
        except Exception as exc:
            conn=connect(CONFIG_DB);conn.execute("update reconciliation_events set status='blocked',details_json=?,finished_at=? where event_id=?",(json.dumps({'error':type(exc).__name__,'secretValuesIncluded':False},separators=(',',':')),now(),row['event_id']));conn.commit();conn.close();results.append({'projectSlug':row['project_slug'],'status':'blocked','errorType':type(exc).__name__})
    return {'ok':all(x.get('status')!='blocked' for x in results),'processed':len(results),'results':results,'secretsExposed':False}
def state(slug):
    conn=connect(CONFIG_DB);row=conn.execute('select * from reconciliation_state where project_slug=?',(slug,)).fetchone();conn.close()
    if not row:return None
    return {'ok':True,'projectSlug':row['project_slug'],'status':row['status'],'configRevision':row['config_revision'],'membershipRevision':row['membership_revision'],'configDigest':row['config_digest'],'toolchainDigest':row['toolchain_digest'],'aclDigest':row['acl_digest'],'latestBuildJobId':row['latest_build_job_id'],'latestBuildStatus':row['latest_build_status'],'requiredActions':json.loads(row['required_actions_json']),'checks':json.loads(row['checks_json']),'updatedAt':row['updated_at'],'secretsExposed':False}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def sendj(self,code,data):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def authed(self):return bool(TOKEN) and self.headers.get('Authorization','')=='Bearer '+TOKEN
    def do_GET(self):
        if self.path=='/health':return self.sendj(200,{'ok':True,'service':'cloudif-project-config-reconciler','mode':'active-verification','secretsExposed':False})
        if not self.authed():return self.sendj(401,{'ok':False,'error':'unauthorized'})
        match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/state',urllib.parse.urlparse(self.path).path)
        if not match:return self.sendj(404,{'ok':False,'error':'not_found'})
        data=state(match.group(1));return self.sendj(200,data) if data else self.sendj(404,{'ok':False,'error':'state_not_found'})
    def do_POST(self):
        if not self.authed():return self.sendj(401,{'ok':False,'error':'unauthorized'})
        if self.path!='/v1/reconcile':return self.sendj(404,{'ok':False,'error':'not_found'})
        return self.sendj(200,process_pending())
if __name__=='__main__':
    init_db()
    import threading
    def loop():
        while True:
            try:process_pending()
            except Exception:pass
            time.sleep(INTERVAL)
    threading.Thread(target=loop,daemon=True).start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
