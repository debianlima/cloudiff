#!/usr/bin/env python3
import os,sqlite3,json,urllib.request,time
DB=os.environ.get('CLOUDIF_ACCESS_DB','/var/lib/cloudif/access-telemetry/access.db')
URL=os.environ.get('CLOUDIF_ACCESS_INGEST_URL','http://10.62.92.7:18094/cloudiff/internal/access-ingest')
TOKEN=os.environ['CLOUDIF_ACCESS_INGEST_TOKEN'];DAYS=max(1,min(int(os.environ.get('CLOUDIF_ACCESS_PUSH_DAYS','7')),90))
def q(sql,args=()):
 c=sqlite3.connect(f'file:{DB}?mode=ro&immutable=1',uri=True,timeout=20);c.row_factory=sqlite3.Row
 try:return [dict(r) for r in c.execute(sql,args)]
 finally:c.close()
summary=q("select coalesce(sum(requests),0) requests,count(distinct visitor_hash) unique_visitors,coalesce(sum(bytes),0) bytes,count(distinct host) hosts,sum(case when source='public' then requests else 0 end) public_requests,sum(case when source='internal' then requests else 0 end) internal_requests from access_daily where day>=date('now',?)",(f'-{DAYS-1} days',))[0]
hosts=q("select host,sum(requests) requests,count(distinct visitor_hash) unique_visitors,sum(bytes) bytes,sum(case when status_class like '4%' or status_class like '5%' then requests else 0 end) errors,max(last_seen) last_seen from access_daily where day>=date('now',?) group by host order by requests desc",(f'-{DAYS-1} days',))
routes=q("select host,route,sum(requests) requests,count(distinct visitor_hash) unique_visitors,sum(bytes) bytes,max(last_seen) last_seen from access_daily where day>=date('now',?) group by host,route order by requests desc limit 500",(f'-{DAYS-1} days',))
payload=json.dumps({'source_host':'mauricio','window_days':DAYS,'summary':summary,'hosts':hosts,'routes':routes},ensure_ascii=False,separators=(',',':')).encode()
r=urllib.request.Request(URL,data=payload,method='POST',headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json','User-Agent':'cloudif-access-push/1.0'})
with urllib.request.urlopen(r,timeout=20) as x:
 body=json.loads(x.read().decode());assert x.status==202 and body.get('ok')
print(json.dumps({'ok':True,'requests':summary['requests'],'hosts':len(hosts),'routes':len(routes),'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}))
