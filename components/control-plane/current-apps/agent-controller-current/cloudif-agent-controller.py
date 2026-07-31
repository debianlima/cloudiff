#!/usr/bin/env python3
import datetime as dt,hashlib,json,os,sqlite3,tempfile,urllib.request,urllib.error
ON='/var/lib/cloudif/onboarding/onboarding.db';PORTAL='/var/lib/cloudif/portal/cloudif-portal.db';OUT='/var/lib/cloudif/health/agent-controller.json';ENV='/etc/cloudif/project-onboarding.env';BASE='http://127.0.0.1:18203'
def now():return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def env(path):
 out={}
 for line in open(path):
  line=line.strip()
  if line and not line.startswith('#') and '=' in line:
   k,v=line.split('=',1);out[k]=v
 return out
def api(method,path,token,payload=None):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();q=urllib.request.Request(BASE+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(q,timeout=30) as x:return x.status,json.load(x)
 except urllib.error.HTTPError as e:
  try:return e.code,json.load(e)
  except Exception:return e.code,{}
def atomic(path,data,mode=0o600):
 os.makedirs(os.path.dirname(path),exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.agent-',dir=os.path.dirname(path))
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(tmp,mode);os.replace(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
def partition(event_type,username,project,tenant):
 if project:return 'project:'+project
 if tenant:return 'tenant:'+tenant
 if username:return 'user:'+username.lower()
 return 'global:'+event_type
def coalesce(event_type,username,project,tenant):return hashlib.sha256((event_type+'|'+username+'|'+project+'|'+tenant).encode()).hexdigest()
def backfill_queue():
 c=sqlite3.connect(PORTAL);c.row_factory=sqlite3.Row;rows=list(c.execute("select request_id,event_type,username,project,tenant,partition_key,coalesce_key from reconcile_requests where partition_key='' or coalesce_key=''"));updated=0
 for r in rows:
  part=partition(r['event_type'] or '',r['username'] or '',r['project'] or '',r['tenant'] or '');coal=coalesce(r['event_type'] or '',r['username'] or '',r['project'] or '',r['tenant'] or '')
  c.execute('update reconcile_requests set partition_key=?,coalesce_key=? where request_id=?',(part,coal,r['request_id']));updated+=1
 c.commit();c.close();return updated
def main():
 cfg=env(ENV);token=cfg['CLOUDIF_AGENT_ADMIN_TOKEN'];code,reg=api('GET','/v1/clients',token);assert code==200 and reg.get('ok');clients={x['client_id']:x for x in reg['clients']}
 c=sqlite3.connect('file:'+ON+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute('select project_slug,client_id,owner_user,tenant,role_profile,environment,rate_per_minute,daily_quota,scopes_json,status from project_onboarding order by project_slug')];c.close()
 results=[];corrected=0;unchanged=0
 for r in rows:
  desired={'name':'Projeto CloudIFF: '+r['project_slug'],'owner_user':r['owner_user'] or '','tenant':r['tenant'] or '','role_profile':r['role_profile'],'environment':r['environment'],'project_slugs':[r['project_slug']],'rate_per_minute':60 if r['role_profile']=='project-admin' else int(r['rate_per_minute'] or 60),'daily_quota':3000 if r['role_profile']=='project-admin' else int(r['daily_quota'] or 3000)};cur=clients.get(r['client_id']);drift=[]
  if not cur:results.append({'project_slug':r['project_slug'],'client_id':r['client_id'],'status':'missing','drift':['client_missing'],'token_rotated':False});continue
  comparisons={'name':desired['name'],'owner_user':desired['owner_user'],'tenant':desired['tenant'],'role_profile':desired['role_profile'],'environment':desired['environment'],'rate_per_minute':desired['rate_per_minute'],'daily_quota':desired['daily_quota']}
  for k,v in comparisons.items():
   if cur.get(k)!=v:drift.append(k)
  if json.loads(cur['project_slugs_json'])!=desired['project_slugs']:drift.append('project_slugs')
  if json.loads(cur['scopes_json'])!=json.loads(r['scopes_json']):drift.append('scopes')
  if drift:
   code,data=api('POST','/v1/clients/'+r['client_id']+'/reconcile',token,desired);assert code==200 and data.get('ok') and data.get('token_hash_preserved') and data.get('token_returned') is False;corrected+=1;status='corrected'
  else:data={'token_hash_preserved':True,'token_returned':False};unchanged+=1;status='aligned'
  results.append({'project_slug':r['project_slug'],'client_id':r['client_id'],'status':status,'drift':drift,'token_hash_preserved':data.get('token_hash_preserved'),'token_rotated':False,'token_returned':False})
 backfilled=backfill_queue();out={'ok':len(results)==len(rows) and all(x['status'] in ('aligned','corrected') for x in results),'generated_at':now(),'projects':len(rows),'aligned':unchanged,'corrected':corrected,'missing':sum(1 for x in results if x['status']=='missing'),'queue_rows_backfilled':backfilled,'tokens_rotated':0,'tokens_returned':0,'secrets_exposed':False,'results':results};atomic(OUT,out);print(json.dumps({k:out[k] for k in ('ok','projects','aligned','corrected','missing','queue_rows_backfilled','tokens_rotated')},separators=(',',':')))
if __name__=='__main__':main()
