#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_RUNTIME_RECONCILER_PORT','18232'))
TOKEN=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_TOKEN','')
STATE_DB=Path(os.environ.get('CLOUDIF_RUNTIME_RECONCILER_DB','/var/lib/cloudif/runtime-reconciler/state.db'))
CONTROL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
BUILD_DB=Path(os.environ.get('CLOUDIF_BUILD_DB','/var/lib/cloudif/build-broker/builds.sqlite3'))
CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
RUNTIME_URL=os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_URL','http://10.62.91.2:18230').rstrip('/')
RUNTIME_TOKEN=os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN','')
ENVIRONMENTS=('development','preview','homologation','production')
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
AUTO_REPAIR_ENVIRONMENTS={item.strip() for item in os.environ.get('CLOUDIF_RUNTIME_RECONCILER_AUTO_ENVIRONMENTS','development,preview').split(',') if item.strip()}


def now()->int:return int(time.time())
def canonical(value:Any)->str:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)


def db()->sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(STATE_DB,timeout=30);connection.row_factory=sqlite3.Row;connection.execute('pragma busy_timeout=30000');return connection


def init_db()->None:
    connection=db();connection.executescript('''
      create table if not exists runtime_reconciliation(
        project_slug text not null,
        environment text not null,
        status text not null,
        desired_json text not null,
        observed_json text not null,
        reasons_json text not null,
        pending_action text not null,
        latest_build_job_id text,
        observed_build_job_id text,
        auto_repair_allowed integer not null default 0,
        effects_executed integer not null default 0,
        checked_at integer not null,
        primary key(project_slug,environment)
      );
      create index if not exists idx_runtime_reconciliation_status on runtime_reconciliation(status,checked_at desc);
      create table if not exists runtime_reconcile_plans(
        plan_digest text primary key,
        project_slug text not null,
        environment text not null,
        state_status text not null,
        pending_action text not null,
        state_checked_at integer not null,
        latest_build_job_id text,
        observed_build_job_id text,
        summary_json text not null,
        created_by text not null,
        created_at integer not null,
        expires_at integer not null
      );
      create index if not exists idx_runtime_reconcile_plans_project on runtime_reconcile_plans(project_slug,environment,created_at desc);
    ''');connection.commit();connection.close()


def _json_call(url:str,token:str,timeout:int=20)->tuple[int,dict[str,Any]]:
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'upstream_http_'+str(error.code)}}
        return error.code,data
    except Exception as error:return 503,{'ok':False,'error':{'code':'upstream_unavailable','detail':type(error).__name__}}


def project_slugs()->list[str]:
    if not CONTROL_DB.exists():return []
    connection=sqlite3.connect(f'file:{CONTROL_DB}?mode=ro',uri=True,timeout=20)
    try:rows=connection.execute("select slug from projects where status not in ('deleted','deleting') order by slug").fetchall()
    except Exception:rows=connection.execute('select slug from projects order by slug').fetchall()
    connection.close();return [str(row[0]) for row in rows if SLUG_RE.fullmatch(str(row[0]))]


def _configuration(slug:str)->dict[str,Any]:
    code,data=_json_call(CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration',CONFIG_TOKEN)
    if code!=200 or not data.get('ok'):return {'ok':False,'code':'configuration-unavailable','rawStatus':code}
    return data


def _effective(slug:str,environment:str)->dict[str,Any]:
    url=CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/effective?'+urllib.parse.urlencode({'environment':environment})
    code,data=_json_call(url,CONFIG_TOKEN)
    if code!=200 or not data.get('ok'):return {'ok':False,'code':'effective-environment-unavailable','rawStatus':code}
    return data


def _missing(slug:str,environment:str)->dict[str,Any]:
    url=CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/missing?'+urllib.parse.urlencode({'environment':environment})
    code,data=_json_call(url,CONFIG_TOKEN)
    if code!=200 or not data.get('ok'):return {'ok':False,'count':0,'missing':[],'code':'missing-variable-check-unavailable'}
    return data


def _runtime(slug:str,environment:str)->dict[str,Any]|None:
    if not RUNTIME_TOKEN:return None
    url=RUNTIME_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/runtime-state?'+urllib.parse.urlencode({'environment':environment})
    code,data=_json_call(url,RUNTIME_TOKEN)
    if code!=200 or not data.get('ok'):return None
    states=data.get('states') or []
    return dict(states[0]) if states else None


def _decode_json(value:Any)->dict[str,Any]:
    if isinstance(value,dict):return value
    if not isinstance(value,str) or not value:return {}
    try:parsed=json.loads(value);return parsed if isinstance(parsed,dict) else {}
    except Exception:return {}


def latest_successful_build(slug:str,environment:str)->dict[str,Any]|None:
    if not BUILD_DB.exists():return None
    connection=sqlite3.connect(f'file:{BUILD_DB}?mode=ro',uri=True,timeout=20);connection.row_factory=sqlite3.Row
    try:columns=[row[1] for row in connection.execute('pragma table_info(multiservice_jobs)').fetchall()]
    except Exception:connection.close();return None
    order='created_at desc' if 'created_at' in columns else 'rowid desc'
    try:rows=connection.execute('select * from multiservice_jobs order by '+order+' limit 500').fetchall()
    except Exception:connection.close();return None
    connection.close()
    for raw in rows:
        row=dict(raw);status=str(row.get('status') or '')
        if status!='succeeded':continue
        payload=_decode_json(row.get('payload_json') or row.get('payload'));result=_decode_json(row.get('result_json') or row.get('result'))
        project=str(row.get('project_slug') or payload.get('project_slug') or payload.get('projectSlug') or '')
        env=str(row.get('environment') or payload.get('environment') or result.get('environment') or '')
        if project!=slug or (env and env!=environment):continue
        job_id=str(row.get('job_id') or row.get('id') or result.get('jobId') or '')
        return {'jobId':job_id,'status':'succeeded','payload':payload,'result':result}
    return None


def desired_state(slug:str,environment:str)->dict[str,Any]:
    configuration=_configuration(slug);effective=_effective(slug,environment);missing=_missing(slug,environment);latest=latest_successful_build(slug,environment)
    desired={
      'ok':bool(configuration.get('ok') and effective.get('ok')),
      'configRevision':int(configuration.get('currentRevision') or effective.get('configRevision') or 0),
      'configDigest':str(configuration.get('configDigest') or effective.get('configDigest') or ''),
      'toolchainDigest':str(configuration.get('toolchainDigest') or effective.get('toolchainDigest') or ''),
      'buildEnvironmentDigest':str(effective.get('buildEnvironmentDigest') or ''),
      'runtimeEnvironmentDigest':str(effective.get('runtimeEnvironmentDigest') or ''),
      'environmentDigest':str(effective.get('environmentDigest') or ''),
      'missingVariables':sorted([{'service':str(item.get('service') or ''),'name':str(item.get('name') or ''),'secret':bool(item.get('secret'))} for item in (missing.get('missing') or [])],key=lambda item:(item['service'],item['name'])),
      'missingCheckOk':bool(missing.get('ok')),
      'latestBuildJobId':str((latest or {}).get('jobId') or ''),
      'latestBuildAvailable':bool(latest),
    }
    return desired


def evaluate(desired:dict[str,Any],observed:dict[str,Any]|None,environment:str)->dict[str,Any]:
    reasons=[];pending='none';status='synchronized'
    if not desired.get('ok'):
        status='blocked';reasons.append('desired-state-unavailable')
    elif not desired.get('missingCheckOk'):
        status='blocked';reasons.append('missing-variable-check-unavailable')
    elif desired.get('missingVariables'):
        status='missing-variable';reasons.extend('missing:'+((item.get('service')+':') if item.get('service') else '')+item.get('name','') for item in desired['missingVariables']);pending='configure'
    elif not observed:
        status='blocked';reasons.append('deployment-missing');pending='deploy' if desired.get('latestBuildAvailable') else 'build'
        if not desired.get('latestBuildAvailable'):reasons.append('completed-build-missing')
    else:
        observed_status=str(observed.get('status') or '').lower()
        if observed_status in {'failed','error','unhealthy','stopped','dead','exited'}:
            status='unhealthy';reasons.append('runtime-status:'+observed_status);pending='restart'
        elif str(observed.get('toolchainDigest') or '')!=str(desired.get('toolchainDigest') or '') or str(observed.get('buildEnvironmentDigest') or '')!=str(desired.get('buildEnvironmentDigest') or ''):
            status='pending-rebuild';pending='rebuild'
            if str(observed.get('toolchainDigest') or '')!=str(desired.get('toolchainDigest') or ''):reasons.append('toolchain-digest-changed')
            if str(observed.get('buildEnvironmentDigest') or '')!=str(desired.get('buildEnvironmentDigest') or ''):reasons.append('build-environment-changed')
        elif str(observed.get('runtimeEnvironmentDigest') or '')!=str(desired.get('runtimeEnvironmentDigest') or ''):
            status='pending-restart';pending='restart';reasons.append('runtime-environment-changed')
        elif desired.get('latestBuildJobId') and str(observed.get('buildJobId') or '')!=str(desired.get('latestBuildJobId') or ''):
            status='image-outdated';pending='redeploy';reasons.append('newer-completed-build-available')
        elif int(observed.get('configRevision') or 0)!=int(desired.get('configRevision') or 0) or str(observed.get('configDigest') or '')!=str(desired.get('configDigest') or '') or str(observed.get('environmentDigest') or '')!=str(desired.get('environmentDigest') or ''):
            status='configuration-drift';pending='redeploy';reasons.append('configuration-digest-mismatch')
    auto_allowed=bool(environment in AUTO_REPAIR_ENVIRONMENTS and status in {'pending-restart','image-outdated'} and environment!='production')
    return {'status':status,'reasons':sorted(set(reasons)),'pendingAction':pending,'autoRepairAllowed':auto_allowed,'productionAutoRepairAllowed':False,'effectsExecuted':False}


def reconcile_one(slug:str,environment:str)->dict[str,Any]:
    if not SLUG_RE.fullmatch(slug) or environment not in ENVIRONMENTS:raise ValueError('invalid_target')
    desired=desired_state(slug,environment);observed=_runtime(slug,environment);classification=evaluate(desired,observed,environment);checked=now()
    latest=str(desired.get('latestBuildJobId') or '');observed_build=str((observed or {}).get('buildJobId') or '')
    connection=db();connection.execute('''insert into runtime_reconciliation(project_slug,environment,status,desired_json,observed_json,reasons_json,pending_action,latest_build_job_id,observed_build_job_id,auto_repair_allowed,effects_executed,checked_at) values(?,?,?,?,?,?,?,?,?,?,0,?) on conflict(project_slug,environment) do update set status=excluded.status,desired_json=excluded.desired_json,observed_json=excluded.observed_json,reasons_json=excluded.reasons_json,pending_action=excluded.pending_action,latest_build_job_id=excluded.latest_build_job_id,observed_build_job_id=excluded.observed_build_job_id,auto_repair_allowed=excluded.auto_repair_allowed,effects_executed=0,checked_at=excluded.checked_at''',(slug,environment,classification['status'],canonical(desired),canonical(observed or {}),canonical(classification['reasons']),classification['pendingAction'],latest,observed_build,1 if classification['autoRepairAllowed'] else 0,checked));connection.commit();connection.close()
    return {'ok':True,'projectSlug':slug,'environment':environment,'desired':desired,'observed':observed,'latestBuildJobId':latest,'observedBuildJobId':observed_build,'checkedAt':checked,'secretValuesIncluded':False,'secretReferencesIncluded':False,**classification}


def reconcile_all()->dict[str,Any]:
    results=[]
    for slug in project_slugs():
        for environment in ENVIRONMENTS:
            try:results.append(reconcile_one(slug,environment))
            except Exception as error:results.append({'ok':False,'projectSlug':slug,'environment':environment,'status':'blocked','reasons':['reconcile-error:'+type(error).__name__],'effectsExecuted':False,'secretValuesIncluded':False})
    counts={}
    for item in results:counts[item.get('status','blocked')]=counts.get(item.get('status','blocked'),0)+1
    return {'ok':all(item.get('ok') for item in results),'projects':len(set(item['projectSlug'] for item in results)) if results else 0,'states':len(results),'counts':counts,'effectsExecuted':False,'secretValuesIncluded':False}


def recommended_workflow(status:str,pending_action:str,latest_build_job_id:str)->list[dict[str,Any]]:
    if status=='synchronized':return []
    if pending_action in {'build','rebuild'}:
        return [
          {'tool':'build.multiservice.plan','approvalRequired':False},
          {'tool':'approval.request-multiservice-build','approvalRequired':True},
          {'tool':'build.multiservice.execute','approvalRequired':True},
          {'tool':'deployment.multiservice.plan','approvalRequired':False},
          {'tool':'approval.request-multiservice-deployment','approvalRequired':True},
          {'tool':'deployment.multiservice.execute','approvalRequired':True},
        ]
    if pending_action in {'restart','redeploy','deploy'} and latest_build_job_id:
        return [
          {'tool':'deployment.multiservice.plan','approvalRequired':False,'buildJobId':latest_build_job_id},
          {'tool':'approval.request-multiservice-deployment','approvalRequired':True,'buildJobId':latest_build_job_id},
          {'tool':'deployment.multiservice.execute','approvalRequired':True,'buildJobId':latest_build_job_id},
        ]
    if pending_action=='configure':
        return [{'tool':'project.environment.validate','approvalRequired':False},{'tool':'project.environment.change.plan','approvalRequired':False},{'tool':'approval.request-environment-change','approvalRequired':True},{'tool':'project.environment.change.execute','approvalRequired':True}]
    return []


def reconciliation_plan(slug:str,environment:str,actor:str='internal',ttl_seconds:int=900)->dict[str,Any]:
    state=reconcile_one(slug,environment);workflow=recommended_workflow(state['status'],state['pendingAction'],state.get('latestBuildJobId') or '')
    material={'projectSlug':slug,'environment':environment,'status':state['status'],'pendingAction':state['pendingAction'],'reasons':state['reasons'],'latestBuildJobId':state.get('latestBuildJobId') or '','observedBuildJobId':state.get('observedBuildJobId') or '','checkedAt':state['checkedAt'],'workflow':workflow}
    plan_digest=hashlib.sha256(canonical(material).encode()).hexdigest();created=now();expires=created+max(60,min(int(ttl_seconds),86400));summary={'status':state['status'],'pendingAction':state['pendingAction'],'reasons':state['reasons'],'workflow':workflow,'effectCount':0,'effectsExecuted':False,'productionAutoRepairAllowed':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    connection=db();connection.execute('insert or replace into runtime_reconcile_plans(plan_digest,project_slug,environment,state_status,pending_action,state_checked_at,latest_build_job_id,observed_build_job_id,summary_json,created_by,created_at,expires_at) values(?,?,?,?,?,?,?,?,?,?,?,?)',(plan_digest,slug,environment,state['status'],state['pendingAction'],state['checkedAt'],state.get('latestBuildJobId') or None,state.get('observedBuildJobId') or None,canonical(summary),str(actor)[:128],created,expires));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'projectSlug':slug,'environment':environment,'planDigest':plan_digest,'status':state['status'],'pendingAction':state['pendingAction'],'reasons':state['reasons'],'latestBuildJobId':state.get('latestBuildJobId') or None,'observedBuildJobId':state.get('observedBuildJobId') or None,'workflow':workflow,'approvalRequired':bool(workflow),'expiresAt':expires,'effectsExecuted':False,'productionAutoRepairAllowed':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}


def get_plan(slug:str,plan_digest:str)->dict[str,Any]:
    if not re.fullmatch(r'[a-f0-9]{64}',str(plan_digest or '')):raise ValueError('invalid_plan_digest')
    connection=db();row=connection.execute('select * from runtime_reconcile_plans where plan_digest=? and project_slug=?',(plan_digest,slug)).fetchone();connection.close()
    if not row:raise LookupError('reconciliation_plan_not_found')
    summary=json.loads(row['summary_json'] or '{}')
    return {'ok':True,'sideEffectFree':True,'projectSlug':slug,'environment':row['environment'],'planDigest':row['plan_digest'],'status':row['state_status'],'pendingAction':row['pending_action'],'latestBuildJobId':row['latest_build_job_id'],'observedBuildJobId':row['observed_build_job_id'],'summary':summary,'createdBy':row['created_by'],'createdAt':int(row['created_at']),'expiresAt':int(row['expires_at']),'expired':int(row['expires_at'])<=now(),'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}


def saved_state(slug:str,environment:str='')->dict[str,Any]:
    connection=db();query='select * from runtime_reconciliation where project_slug=?';args=[slug]
    if environment:query+=' and environment=?';args.append(environment)
    query+=' order by environment';rows=connection.execute(query,tuple(args)).fetchall();connection.close();states=[]
    for raw in rows:
        row=dict(raw);states.append({'projectSlug':row['project_slug'],'environment':row['environment'],'status':row['status'],'desired':json.loads(row['desired_json'] or '{}'),'observed':json.loads(row['observed_json'] or '{}'),'reasons':json.loads(row['reasons_json'] or '[]'),'pendingAction':row['pending_action'],'latestBuildJobId':row['latest_build_job_id'],'observedBuildJobId':row['observed_build_job_id'],'autoRepairAllowed':bool(row['auto_repair_allowed']),'productionAutoRepairAllowed':False,'effectsExecuted':bool(row['effects_executed']),'checkedAt':int(row['checked_at']),'secretValuesIncluded':False,'secretReferencesIncluded':False})
    return {'ok':True,'projectSlug':slug,'environment':environment or None,'states':states,'count':len(states),'secretValuesIncluded':False,'secretReferencesIncluded':False}


def _authorized(headers)->bool:
    value=str(headers.get('Authorization') or '');expected='Bearer '+TOKEN if TOKEN else ''
    import hmac
    return bool(expected and hmac.compare_digest(value,expected))


class H(BaseHTTPRequestHandler):
    server_version='CloudIFRuntimeReconciler/1.0'
    def log_message(self,*args):return
    def sendj(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=='/health':return self.sendj(200,{'ok':True,'service':'cloudif-project-runtime-reconciler','effectsExecuted':False})
        if not _authorized(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
        plan_match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/reconcile-plans/([a-f0-9]{64})',parsed.path)
        if plan_match:
            try:return self.sendj(200,get_plan(*plan_match.groups()))
            except LookupError as error:return self.sendj(404,{'ok':False,'error':str(error)})
            except ValueError as error:return self.sendj(400,{'ok':False,'error':str(error)})
        match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/runtime-state',parsed.path)
        if match:
            query=urllib.parse.parse_qs(parsed.query);environment=(query.get('environment') or [''])[0]
            return self.sendj(200,saved_state(match.group(1),environment))
        return self.sendj(404,{'ok':False,'error':'not_found'})
    def do_POST(self):
        if not _authorized(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=='/v1/reconcile':return self.sendj(200,reconcile_all())
        plan_match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/reconcile-plan',parsed.path)
        if plan_match:
            length=int(self.headers.get('Content-Length','0') or 0);body=json.loads(self.rfile.read(length) or b'{}');environment=str(body.get('environment') or '');actor=str(body.get('actor') or 'internal')
            try:return self.sendj(200,reconciliation_plan(plan_match.group(1),environment,actor,int(body.get('ttlSeconds',body.get('ttl_seconds',900)) or 900)))
            except ValueError as error:return self.sendj(400,{'ok':False,'error':str(error)})
        match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/reconcile',parsed.path)
        if match:
            length=int(self.headers.get('Content-Length','0') or 0);body=json.loads(self.rfile.read(length) or b'{}');environment=str(body.get('environment') or '')
            try:return self.sendj(200,reconcile_one(match.group(1),environment))
            except ValueError as error:return self.sendj(400,{'ok':False,'error':str(error)})
        return self.sendj(404,{'ok':False,'error':'not_found'})


def background_loop():
    interval=max(30,min(int(os.environ.get('CLOUDIF_RUNTIME_RECONCILER_INTERVAL','120')),3600))
    while True:
        try:reconcile_all()
        except Exception:pass
        time.sleep(interval)


def main():
    init_db();threading.Thread(target=background_loop,daemon=True).start();ThreadingHTTPServer((HOST,PORT),H).serve_forever()


if __name__=='__main__':main()
