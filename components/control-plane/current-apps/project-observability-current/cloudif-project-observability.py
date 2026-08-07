#!/usr/bin/env python3
from __future__ import annotations

import hmac
import json
import os
import re
import sqlite3
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_PORT','18233'))
TOKEN=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_TOKEN','')
RUNTIME_DB=Path(os.environ.get('CLOUDIF_RUNTIME_RECONCILER_DB','/var/lib/cloudif/runtime-reconciler/state.db'))
CONFIG_DB=Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_DB','/var/lib/cloudif/project-config/config.db'))
BUILD_DB=Path(os.environ.get('CLOUDIF_BUILD_DB','/var/lib/cloudif/build-broker/builds.sqlite3'))
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
KNOWN_RECONCILE_STATES=('synchronized','pending-rebuild','pending-restart','missing-variable','image-outdated','configuration-drift','unhealthy','blocked')


def now()->int:return int(time.time())
def _ro(path:Path)->sqlite3.Connection|None:
    if not path.exists():return None
    connection=sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=20);connection.row_factory=sqlite3.Row;connection.execute('pragma busy_timeout=20000');return connection


def _rows(connection:sqlite3.Connection|None,query:str,args=())->list[sqlite3.Row]:
    if connection is None:return []
    try:return connection.execute(query,args).fetchall()
    except sqlite3.Error:return []


def _table_exists(connection:sqlite3.Connection|None,name:str)->bool:
    if connection is None:return False
    try:return bool(connection.execute("select 1 from sqlite_master where type='table' and name=?",(name,)).fetchone())
    except sqlite3.Error:return False


def _table_columns(connection:sqlite3.Connection|None,name:str)->set[str]:
    if not _table_exists(connection,name):return set()
    try:return {str(row[1]) for row in connection.execute(f'pragma table_info({name})').fetchall()}
    except sqlite3.Error:return set()


def _safe_json(value:Any,default):
    if isinstance(value,type(default)):return value
    if not isinstance(value,str):return default
    try:parsed=json.loads(value);return parsed if isinstance(parsed,type(default)) else default
    except Exception:return default


def _project_filter(slug:str)->tuple[str,tuple[Any,...]]:
    return (' where project_slug=?',(slug,)) if slug else ('',())


def runtime_summary(slug:str='')->dict[str,Any]:
    connection=_ro(RUNTIME_DB);where,args=_project_filter(slug);rows=_rows(connection,'select * from runtime_reconciliation'+where,args);connection.close() if connection else None
    counts={status:0 for status in KNOWN_RECONCILE_STATES};environments={};missing=0;alerts=[]
    for raw in rows:
        row=dict(raw);status=str(row.get('status') or 'blocked');environment=str(row.get('environment') or '');project=str(row.get('project_slug') or '')
        counts[status]=counts.get(status,0)+1;environments.setdefault(environment,{})[status]=environments.setdefault(environment,{}).get(status,0)+1
        desired=_safe_json(row.get('desired_json'),{});missing_items=desired.get('missingVariables') or [];missing+=len(missing_items)
        if status!='synchronized':
            severity='critical' if environment=='production' and status in {'missing-variable','unhealthy','blocked'} else 'high' if environment=='production' else 'warning'
            alerts.append({'code':'runtime-'+status,'severity':severity,'projectSlug':project,'environment':environment,'status':status,'pendingAction':str(row.get('pending_action') or 'none'),'reasons':_safe_json(row.get('reasons_json'),[]),'checkedAt':int(row.get('checked_at') or 0)})
    return {'states':counts,'environments':environments,'missingVariables':missing,'driftCount':sum(count for status,count in counts.items() if status!='synchronized'),'alerts':alerts,'stateRows':len(rows)}


def environment_summary(slug:str='')->dict[str,Any]:
    connection=_ro(CONFIG_DB);where,args=_project_filter(slug)
    history=len(_rows(connection,'select event_id from environment_history'+where,args)) if _table_exists(connection,'environment_history') else 0
    plans=len(_rows(connection,'select plan_digest from environment_plans'+where,args)) if _table_exists(connection,'environment_plans') else 0
    entries=len(_rows(connection,'select name from environment_entries'+where,args)) if _table_exists(connection,'environment_entries') else 0
    events={};materials={};expired=0;expiring=0;alerts=[];ts=now();week=ts+7*86400
    if _table_exists(connection,'environment_secret_events'):
        for row in _rows(connection,'select event_type,count(*) as count from environment_secret_events'+where+(' group by event_type' if where else ' group by event_type'),args):events[str(row['event_type'])]=int(row['count'])
    if _table_exists(connection,'environment_secret_materials'):
        rows=_rows(connection,'select project_slug,environment,service,name,status,expires_at,secret_reference from environment_secret_materials'+where,args)
        for raw in rows:
            row=dict(raw);status=str(row.get('status') or 'unknown');expires=int(row.get('expires_at') or 0);derived='expired' if status=='active' and expires and expires<=ts else status;materials[derived]=materials.get(derived,0)+1
            if status=='active' and expires and expires<=ts:
                expired+=1;alerts.append({'code':'secret-expired','severity':'critical' if row['environment']=='production' else 'high','projectSlug':row['project_slug'],'environment':row['environment'],'service':row['service'],'name':row['name'],'expiresAt':expires})
            elif status=='active' and expires and expires<2147483647 and expires<=week:
                expiring+=1;alerts.append({'code':'secret-expiring','severity':'high' if row['environment']=='production' else 'warning','projectSlug':row['project_slug'],'environment':row['environment'],'service':row['service'],'name':row['name'],'expiresAt':expires})
    connection.close() if connection else None
    return {'historyEvents':history,'plans':plans,'entries':entries,'secretEvents':events,'secretMaterials':materials,'expiredSecrets':expired,'expiringSecrets':expiring,'alerts':alerts}


def build_summary(slug:str='')->dict[str,Any]:
    connection=_ro(BUILD_DB);jobs={};toolchains={};alerts=[]
    if _table_exists(connection,'multiservice_jobs'):
        cols=_table_columns(connection,'multiservice_jobs');query='select * from multiservice_jobs';rows=_rows(connection,query)
        for raw in rows:
            row=dict(raw);project=str(row.get('project_slug') or '')
            if slug and project and project!=slug:continue
            status=str(row.get('status') or 'unknown');jobs[status]=jobs.get(status,0)+1
            if status in {'failed','blocked'}:alerts.append({'code':'build-'+status,'severity':'high','projectSlug':project,'status':status,'jobId':str(row.get('job_id') or row.get('id') or '')})
    # Discover the canonical toolchain build table by columns, avoiding coupling to one migration name.
    if connection:
        try:tables=[str(row[0]) for row in connection.execute("select name from sqlite_master where type='table'").fetchall()]
        except sqlite3.Error:tables=[]
        for table in tables:
            if table=='multiservice_jobs':continue
            cols=_table_columns(connection,table)
            if 'status' not in cols or not ({'toolchain_digest','image_digest','project_slug'} & cols):continue
            for raw in _rows(connection,f'select * from {table}'):
                row=dict(raw);project=str(row.get('project_slug') or '')
                if slug and project and project!=slug:continue
                status=str(row.get('status') or 'unknown');toolchains[status]=toolchains.get(status,0)+1
                if status in {'failed','blocked','quarantined'}:alerts.append({'code':'toolchain-'+status,'severity':'high','projectSlug':project,'status':status,'recordId':str(row.get('build_id') or row.get('job_id') or row.get('id') or '')})
            if toolchains:break
    connection.close() if connection else None
    return {'buildJobs':jobs,'toolchainBuilds':toolchains,'alerts':alerts}


def snapshot(slug:str='')->dict[str,Any]:
    if slug and not SLUG_RE.fullmatch(slug):raise ValueError('invalid_project_slug')
    runtime=runtime_summary(slug);environment=environment_summary(slug);build=build_summary(slug);alerts=runtime['alerts']+environment['alerts']+build['alerts'];alerts.sort(key=lambda item:({'critical':0,'high':1,'warning':2,'info':3}.get(item.get('severity'),9),item.get('projectSlug',''),item.get('environment',''),item.get('code','')))
    return {'ok':True,'projectSlug':slug or None,'generatedAt':now(),'runtime':{k:v for k,v in runtime.items() if k!='alerts'},'environment':{k:v for k,v in environment.items() if k!='alerts'},'build':{k:v for k,v in build.items() if k!='alerts'},'alerts':alerts,'alertCount':len(alerts),'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}


def _label(value:str)->str:return value.replace('\\','\\\\').replace('"','\\"').replace('\n',' ')
def metrics_text(slug:str='')->str:
    data=snapshot(slug);lines=['# HELP cloudiff_runtime_reconciliation_states Current reconciler states.','# TYPE cloudiff_runtime_reconciliation_states gauge']
    for status,count in sorted(data['runtime']['states'].items()):lines.append(f'cloudiff_runtime_reconciliation_states{{status="{_label(status)}"}} {int(count)}')
    lines.extend(['# HELP cloudiff_configuration_drift_total Current non-synchronized runtime states.','# TYPE cloudiff_configuration_drift_total gauge',f"cloudiff_configuration_drift_total {int(data['runtime']['driftCount'])}",'# HELP cloudiff_missing_variables_total Current required variables missing.','# TYPE cloudiff_missing_variables_total gauge',f"cloudiff_missing_variables_total {int(data['runtime']['missingVariables'])}",'# HELP cloudiff_environment_changes_total Recorded environment change events.','# TYPE cloudiff_environment_changes_total gauge',f"cloudiff_environment_changes_total {int(data['environment']['historyEvents'])}",'# HELP cloudiff_secret_materials Current secret material states.','# TYPE cloudiff_secret_materials gauge'])
    for status,count in sorted(data['environment']['secretMaterials'].items()):lines.append(f'cloudiff_secret_materials{{status="{_label(status)}"}} {int(count)}')
    lines.extend(['# HELP cloudiff_secret_events_total Secret lifecycle audit events.','# TYPE cloudiff_secret_events_total gauge'])
    for event,count in sorted(data['environment']['secretEvents'].items()):lines.append(f'cloudiff_secret_events_total{{event="{_label(event)}"}} {int(count)}')
    lines.extend(['# HELP cloudiff_build_jobs_total Build jobs by status.','# TYPE cloudiff_build_jobs_total gauge'])
    for status,count in sorted(data['build']['buildJobs'].items()):lines.append(f'cloudiff_build_jobs_total{{status="{_label(status)}"}} {int(count)}')
    lines.extend(['# HELP cloudiff_toolchain_builds_total Toolchain build records by status.','# TYPE cloudiff_toolchain_builds_total gauge'])
    for status,count in sorted(data['build']['toolchainBuilds'].items()):lines.append(f'cloudiff_toolchain_builds_total{{status="{_label(status)}"}} {int(count)}')
    lines.extend(['# HELP cloudiff_project_alerts Current platform alerts.','# TYPE cloudiff_project_alerts gauge',f"cloudiff_project_alerts {int(data['alertCount'])}"])
    return '\n'.join(lines)+'\n'


def _auth(headers)->bool:
    presented=str(headers.get('Authorization') or '');expected='Bearer '+TOKEN if TOKEN else '';return bool(expected and hmac.compare_digest(presented,expected))


class H(BaseHTTPRequestHandler):
    server_version='CloudIFProjectObservability/1.0'
    def log_message(self,*args):return
    def sendj(self,status,payload):
        raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=='/health':return self.sendj(200,{'ok':True,'service':'cloudif-project-observability','effectsExecuted':False})
        if not _auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
        query=urllib.parse.parse_qs(parsed.query);slug=str((query.get('slug') or [''])[0])
        try:
            if parsed.path=='/v1/snapshot':return self.sendj(200,snapshot(slug))
            if parsed.path=='/v1/alerts':
                data=snapshot(slug);return self.sendj(200,{'ok':True,'projectSlug':data['projectSlug'],'generatedAt':data['generatedAt'],'alerts':data['alerts'],'count':data['alertCount'],'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False})
            if parsed.path=='/metrics':
                raw=metrics_text(slug).encode();self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        except ValueError as error:return self.sendj(400,{'ok':False,'error':str(error)})
        return self.sendj(404,{'ok':False,'error':'not_found'})


def main():ThreadingHTTPServer((HOST,PORT),H).serve_forever()
if __name__=='__main__':main()
