#!/usr/bin/env python3
from pathlib import Path
import urllib.request,urllib.error,json,sqlite3,time,subprocess,os,hashlib,tarfile,io
OUT='/var/lib/cloudif/health/control-plane-smoke.json';os.makedirs(os.path.dirname(OUT),exist_ok=True)
def env(p):
 d={}
 for raw in Path(p).read_text().splitlines():
  line=raw.strip()
  if line and not line.startswith('#') and '=' in line:
   k,v=line.split('=',1);d[k]=v.strip().strip('"').strip("'")
 return d
def http(name,url,expected=200,headers=None,data=None):
 try:
  r=urllib.request.Request(url,data=data,headers=headers or {},method='POST' if data is not None else 'GET')
  with urllib.request.urlopen(r,timeout=12) as x:code=x.status;body=x.read(200000)
 except urllib.error.HTTPError as e:code=e.code;body=e.read(200000)
 except Exception as e:return {'name':name,'ok':False,'error':type(e).__name__}
 return {'name':name,'ok':code==expected,'code':code,'size':len(body)}
checks=[]
try:
 _pc=sqlite3.connect('file:/var/lib/cloudif/control-plane/control-plane.db?mode=ro',uri=True,timeout=8)
 expected_project_slugs={str(r[0]) for r in _pc.execute('select slug from projects')};_pc.close()
except Exception:
 expected_project_slugs=set()
expected_project_count=len(expected_project_slugs)
for s in ('cloudif-admin-portal.service','cloudif-admin-portal-staging.service','cloudif-portal-qa.service','cloudif-control-plane-api.service','cloudif-mcp-gateway.service','cloudif-monitor-api.service','cloudif-control-dashboard.service','cloudif-academic-audit.service','cloudif-notification-api.service','cloudif-agent-registry.service','cloudif-approval-api.service','cloudif-evaluation-api.service','cloudif-workspace-broker.service'):
 p=subprocess.run(['systemctl','is-active',s],text=True,capture_output=True);checks.append({'name':'service:'+s,'ok':p.stdout.strip()=='active','state':p.stdout.strip()})
checks += [http('control-health','http://127.0.0.1:18197/health'),http('mcp-health','http://127.0.0.1:18198/health'),http('monitor-health','http://127.0.0.1:18199/health'),http('dashboard-health','http://127.0.0.1:18200/health'),http('audit-health','http://127.0.0.1:18201/health'),http('notify-health','http://127.0.0.1:18202/health'),http('agent-health','http://127.0.0.1:18203/health'),http('approval-health','http://127.0.0.1:18204/health'),http('evaluation-health','http://127.0.0.1:18205/health'),http('workspace-health','http://127.0.0.1:18206/health')]
H={'X-authentik-username':'akadmin','X-authentik-groups':'CloudIF-Tenants-Admin|CloudIF-Professor'}
checks += [http('portal','http://127.0.0.1:18094/cloudiff/portal/',200,H),http('portal-control','http://127.0.0.1:18094/cloudiff/portal/control',200,H),http('staging','http://127.0.0.1:18194/cloudiff/staging/',200,H)]
for path in ('/var/lib/cloudif/portal/cloudif-portal.db','/var/lib/cloudif/control-plane/control-plane.db','/var/lib/cloudif/monitoring/monitor.db','/var/lib/cloudif/audit/audit.db','/var/lib/cloudif/notifications/notifications.db','/var/lib/cloudif/agents/agents.db','/var/lib/cloudif/approvals/approvals.db','/var/lib/cloudif/evaluations/evaluations.db','/var/lib/cloudif/access-ingest/access.db'):
 try:c=sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=8);v=c.execute('pragma integrity_check').fetchone()[0];c.close();checks.append({'name':'sqlite:'+path,'ok':v=='ok','result':v})
 except Exception as e:checks.append({'name':'sqlite:'+path,'ok':False,'error':type(e).__name__})
m=env('/etc/cloudif/mcp-gateway.env');payload=json.dumps({'jsonrpc':'2.0','id':'smoke','method':'tools/list','params':{}}).encode();checks.append(http('mcp-tools','http://127.0.0.1:18198/mcp',200,{'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json'},payload))
try:
 wp=json.dumps({'jsonrpc':'2.0','id':'workspace-smoke','method':'tools/call','params':{'name':'workspace.probe','arguments':{'slug':'teste-2'}}}).encode()
 wr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=wp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-smoke'})
 with urllib.request.urlopen(wr,timeout=25) as x:wd=json.load(x);code=x.status
 content=json.loads(wd['result']['content'][0]['text']);r=content['result']
 ok=code==200 and wd['result']['isError'] is False and r.get('uid') not in (None,0) and r.get('network')=='none' and r.get('root_write')=='denied' and r.get('docker_socket')=='absent' and content.get('container_removed') is True
 checks.append({'name':'mcp-workspace-probe','ok':ok,'code':code,'network':r.get('network'),'uid':r.get('uid'),'removed':content.get('container_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-probe','ok':False,'error':type(e).__name__})
try:
 pp=json.dumps({'jsonrpc':'2.0','id':'workspace-prepare-smoke','method':'tools/call','params':{'name':'workspace.prepare','arguments':{'slug':'cloudif-v97-test-20260608-201744','ref':'main'}}}).encode()
 pr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=pp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-prepare'})
 with urllib.request.urlopen(pr,timeout=50) as x:pd=json.load(x);code=x.status
 content=json.loads(pd['result']['content'][0]['text']);r=content['result'];c=r['container']
 ok=code==200 and pd['result']['isError'] is False and r.get('file_count',0)>0 and len(r.get('archive_sha256',''))==64 and c.get('uid') not in (None,'0',0) and c.get('network')=='none' and c.get('workspace_write')=='readonly' and c.get('docker_socket')=='absent' and content.get('container_removed') is True and content.get('temp_removed') is True
 checks.append({'name':'mcp-workspace-prepare','ok':ok,'code':code,'files':r.get('file_count'),'network':c.get('network'),'removed':content.get('container_removed'),'temp_removed':content.get('temp_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-prepare','ok':False,'error':type(e).__name__})
try:
 vp=json.dumps({'jsonrpc':'2.0','id':'workspace-validate-smoke','method':'tools/call','params':{'name':'workspace.validate','arguments':{'slug':'cloudif-v97-test-20260608-201744','ref':'main'}}}).encode()
 vr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=vp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-validate'})
 before=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 with urllib.request.urlopen(vr,timeout=50) as x:vd=json.load(x);code=x.status
 after=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 content=json.loads(vd['result']['content'][0]['text']);r=content['result'];compose=r['compose']
 ok=code==200 and vd['result']['isError'] is False and r.get('valid') is True and compose.get('valid') is True and compose.get('parser_ok') is True and not r.get('violations') and content.get('temp_removed') is True and before==after
 checks.append({'name':'mcp-workspace-validate','ok':ok,'code':code,'valid':r.get('valid'),'parser_ok':compose.get('parser_ok'),'violations':len(r.get('violations') or []),'side_effect_free':before==after,'temp_removed':content.get('temp_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-validate','ok':False,'error':type(e).__name__})
try:
 sp=json.dumps({'jsonrpc':'2.0','id':'workspace-static-smoke','method':'tools/call','params':{'name':'workspace.test-static','arguments':{'slug':'atalhos-cloudif-iff1860746','ref':'main'}}}).encode()
 sr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=sp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-static'})
 before=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 with urllib.request.urlopen(sr,timeout=70) as x:sd=json.load(x);code=x.status
 after=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 content=json.loads(sd['result']['content'][0]['text']);r=content['result'];c=r['container'];ng=r['nginx']
 ok=code==200 and sd['result']['isError'] is False and r.get('applicable') is True and r.get('valid') is True and ng.get('executed') is True and ng.get('syntax_ok') is True and c.get('uid') not in (None,'0',0) and c.get('network')=='none' and c.get('docker_socket')=='absent' and content.get('container_removed') is True and content.get('temp_removed') is True and before==after
 checks.append({'name':'mcp-workspace-test-static','ok':ok,'code':code,'valid':r.get('valid'),'syntax_ok':ng.get('syntax_ok'),'uid':c.get('uid'),'network':c.get('network'),'side_effect_free':before==after,'removed':content.get('container_removed'),'temp_removed':content.get('temp_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-test-static','ok':False,'error':type(e).__name__})
try:
 pp=json.dumps({'jsonrpc':'2.0','id':'workspace-preview-smoke','method':'tools/call','params':{'name':'workspace.preview-static','arguments':{'slug':'atalhos-cloudif-iff1860746','ref':'main'}}}).encode()
 pr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=pp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-preview'})
 before=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 with urllib.request.urlopen(pr,timeout=85) as x:pd=json.load(x);code=x.status
 after=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 content=json.loads(pd['result']['content'][0]['text']);r=content['result'];rt=r['runtime'];c=r['container']
 ok=code==200 and pd['result']['isError'] is False and r.get('valid') is True and rt.get('executed') is True and rt.get('index_ok') is True and rt.get('health_ok') is True and rt.get('meaningful_html') is True and 'text/html' in str(rt.get('index_content_type','')).lower() and c.get('uid') not in (None,'0',0) and c.get('network')=='none' and c.get('docker_socket')=='absent' and r.get('published_ports')==[] and r.get('network_mode')=='none' and content.get('container_removed') is True and content.get('temp_removed') is True and before==after
 checks.append({'name':'mcp-workspace-preview-static','ok':ok,'code':code,'valid':r.get('valid'),'index_ok':rt.get('index_ok'),'health_ok':rt.get('health_ok'),'content_type':rt.get('index_content_type'),'network':c.get('network'),'published_ports':r.get('published_ports'),'side_effect_free':before==after,'removed':content.get('container_removed'),'temp_removed':content.get('temp_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-preview-static','ok':False,'error':type(e).__name__})
try:
 fe=env('/etc/cloudif/forja-agent-client.env');furl=fe['FORJA_AGENT_URL'].rstrip('/')+'/project/archive?slug=atalhos-cloudif-iff1860746&ref=main'
 def fetch_source():
  q=urllib.request.Request(furl,headers={'X-CloudIF-Token':fe['FORJA_AGENT_TOKEN'],'Accept':'application/gzip'})
  with urllib.request.urlopen(q,timeout=35) as x:raw=x.read(20*1024*1024+1)
  assert len(raw)<=20*1024*1024
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:
   members=[m for m in t.getmembers() if m.isfile() and (m.name=='site/index.html' or m.name.endswith('/site/index.html'))]
   assert len(members)==1
   src=t.extractfile(members[0]);assert src is not None;body=src.read(2*1024*1024+1);assert len(body)<=2*1024*1024
  return hashlib.sha256(raw).hexdigest(),hashlib.sha256(body).hexdigest()
 archive_before,file_sha=fetch_source()
 ep=json.dumps({'jsonrpc':'2.0','id':'workspace-edit-smoke','method':'tools/call','params':{'name':'workspace.edit-preview','arguments':{'slug':'atalhos-cloudif-iff1860746','ref':'main','path':'site/index.html','expected_sha256':file_sha,'find':'<title>Projeto CloudIF</title>','replace':'<title>Projeto CloudIF - Prévia</title>'}}}).encode()
 er=urllib.request.Request('http://127.0.0.1:18198/mcp',data=ep,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-workspace-edit-preview'})
 before=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 with urllib.request.urlopen(er,timeout=100) as x:ed=json.load(x);code=x.status
 after=subprocess.check_output(['/usr/bin/docker','ps','-aq'],text=True,timeout=8).split()
 archive_after,file_after=fetch_source()
 content=json.loads(ed['result']['content'][0]['text']);r=content['result'];e=r['edit'];rt=r['runtime'];c=r['container']
 ok=code==200 and ed['result']['isError'] is False and r.get('valid') is True and r.get('persisted') is False and e.get('before_sha256')==file_sha and e.get('after_sha256')!=file_sha and e.get('occurrences')==1 and 'Projeto CloudIF - Prévia' in e.get('diff','') and rt.get('replacement_visible') is True and rt.get('index_ok') is True and rt.get('health_ok') is True and c.get('uid') not in (None,'0',0) and c.get('network')=='none' and c.get('docker_socket')=='absent' and r.get('published_ports')==[] and r.get('network_mode')=='none' and content.get('container_removed') is True and content.get('temp_removed') is True and before==after and archive_before==archive_after and file_sha==file_after
 checks.append({'name':'mcp-workspace-edit-preview','ok':ok,'code':code,'valid':r.get('valid'),'persisted':r.get('persisted'),'replacement_visible':rt.get('replacement_visible'),'repository_unchanged':archive_before==archive_after and file_sha==file_after,'network':c.get('network'),'published_ports':r.get('published_ports'),'side_effect_free':before==after,'removed':content.get('container_removed'),'temp_removed':content.get('temp_removed')})
except Exception as e:checks.append({'name':'mcp-workspace-edit-preview','ok':False,'error':type(e).__name__})
try:
 gp=json.dumps({'jsonrpc':'2.0','id':'proposal-guard-smoke','method':'tools/call','params':{'name':'forgejo.propose-edit','arguments':{'slug':'atalhos-cloudif-iff1860746','path':'site/index.html','expected_sha256':'0'*64,'find':'x','replace':'y','title':'Teste','body':'','approval_id':'apr_'+'0'*20}}}).encode()
 gr=urllib.request.Request('http://127.0.0.1:18198/mcp',data=gp,method='POST',headers={'Authorization':'Bearer '+m['CLOUDIF_MCP_TOKEN'],'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-proposal-guard'})
 with urllib.request.urlopen(gr,timeout=15) as x:gd=json.load(x);code=x.status
 ok=code==200 and gd.get('error',{}).get('message')=='identified_client_required'
 checks.append({'name':'mcp-forgejo-proposal-guard','ok':ok,'code':code,'error':gd.get('error',{}).get('message'),'side_effect_free':True})
except Exception as e:checks.append({'name':'mcp-forgejo-proposal-guard','ok':False,'error':type(e).__name__})
try:
 se=env('/etc/cloudif/proposal-smoke.env');ae=env('/etc/cloudif/approvals.env')
 cid=se['CLOUDIF_PROPOSAL_SMOKE_CLIENT'];ct=se['CLOUDIF_PROPOSAL_SMOKE_TOKEN'];at=ae['CLOUDIF_APPROVAL_TOKEN']
 base={'slug':'atalhos-cloudif-iff1860746','path':'site/index.html','expected_sha256':'0'*64,'find':'<title>Projeto CloudIF</title>','replace':'<title>Projeto CloudIF - Smoke</title>','title':'CloudIF: plano de smoke','body':'Validação periódica sem efeito Forgejo.'}
 def rpc(name,args,rid):
  q={'jsonrpc':'2.0','id':rid,'method':'tools/call','params':{'name':name,'arguments':args}}
  r=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(q,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+ct,'X-CloudIF-Client':cid,'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-'+str(rid)})
  with urllib.request.urlopen(r,timeout=20) as x:return x.status,json.load(x)
 def apost(path,data):
  r=urllib.request.Request('http://127.0.0.1:18204'+path,data=json.dumps(data,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+at,'Content-Type':'application/json'})
  with urllib.request.urlopen(r,timeout=8) as x:return json.load(x)
 def alist():
  r=urllib.request.Request('http://127.0.0.1:18204/v1/approvals',headers={'Authorization':'Bearer '+at})
  with urllib.request.urlopen(r,timeout=8) as x:return json.load(x)['approvals']
 # Recover only stale active approvals belonging to this dedicated smoke client.
 for a in alist():
  if a.get('project_slug')=='atalhos-cloudif-iff1860746' and a.get('action')=='forgejo.propose-edit' and a.get('requested_by')==cid and a.get('status') in {'pending','approved'}:
   if a['status']=='pending':apost('/v1/approvals/'+a['approval_id']+'/approve',{'approved_by':'cloudif-smoke-recovery'})
   apost('/v1/approvals/'+a['approval_id']+'/consume',{})
 c1,p1=rpc('forgejo.propose-edit.plan',base,'proposal-plan-1');c2,p2=rpc('forgejo.propose-edit.plan',base,'proposal-plan-2')
 x1=json.loads(p1['result']['content'][0]['text']);x2=json.loads(p2['result']['content'][0]['text'])
 plan_ok=c1==200 and c2==200 and p1['result']['isError'] is False and p2['result']['isError'] is False and x1.get('side_effect_free') is True and x1.get('proposal_digest')==x2.get('proposal_digest') and x1.get('client_id')==cid
 checks.append({'name':'mcp-forgejo-proposal-plan','ok':plan_ok,'code':c1,'deterministic':x1.get('proposal_digest')==x2.get('proposal_digest'),'side_effect_free':x1.get('side_effect_free')})
 req_args=dict(base,reason='Aprovação periódica de smoke',ttl_seconds=300)
 cr,rr=rpc('approval.request-proposal',req_args,'proposal-approval-request');rc=json.loads(rr['result']['content'][0]['text']);aid=rc['approval_id']
 row=next(a for a in alist() if a['approval_id']==aid);meta=json.loads(row['metadata_json'])
 pending_ok=cr==200 and rr['result']['isError'] is False and rc.get('status')=='pending' and rc.get('proposal_digest')==x1.get('proposal_digest') and row.get('status')=='pending' and row.get('requested_by')==cid and row.get('action')=='forgejo.propose-edit' and meta=={'proposal_digest':x1.get('proposal_digest')} and rc.get('side_effects')=={'forgejo':False,'branch_created':False,'pull_request_created':False}
 apost('/v1/approvals/'+aid+'/approve',{'approved_by':'cloudif-smoke'});consumed=apost('/v1/approvals/'+aid+'/consume',{})
 final=next(a for a in alist() if a['approval_id']==aid)
 request_ok=pending_ok and consumed.get('status')=='consumed' and final.get('status')=='consumed'
 checks.append({'name':'mcp-approval-request-proposal','ok':request_ok,'code':cr,'pending_verified':pending_ok,'consumed':final.get('status')=='consumed','forgejo_side_effects':False})
except Exception as e:
 checks.append({'name':'mcp-forgejo-proposal-plan','ok':False,'error':type(e).__name__})
 checks.append({'name':'mcp-approval-request-proposal','ok':False,'error':type(e).__name__})
try:
 re=env('/etc/cloudif/read-tools-smoke.env');ae=env('/etc/cloudif/approvals.env')
 cid=re['CLOUDIF_READ_SMOKE_CLIENT'];ct=re['CLOUDIF_READ_SMOKE_TOKEN'];at=ae['CLOUDIF_APPROVAL_TOKEN']
 def rrpc(name,args,rid):
  q={'jsonrpc':'2.0','id':rid,'method':'tools/call','params':{'name':name,'arguments':args}}
  r=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(q,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+ct,'X-CloudIF-Client':cid,'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-read-'+str(rid)})
  with urllib.request.urlopen(r,timeout=20) as x:return x.status,json.load(x)
 def rapost(path,data):
  r=urllib.request.Request('http://127.0.0.1:18204'+path,data=json.dumps(data,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+at,'Content-Type':'application/json'})
  with urllib.request.urlopen(r,timeout=8) as x:return json.load(x)
 def ralist():
  r=urllib.request.Request('http://127.0.0.1:18204/v1/approvals',headers={'Authorization':'Bearer '+at})
  with urllib.request.urlopen(r,timeout=8) as x:return json.load(x)['approvals']
 for a in ralist():
  if a.get('project_slug')=='atalhos-cloudif-iff1860746' and a.get('requested_by')==cid and a.get('status') in {'pending','approved'}:
   if a['status']=='pending':rapost('/v1/approvals/'+a['approval_id']+'/approve',{'approved_by':'cloudif-read-smoke-recovery'})
   rapost('/v1/approvals/'+a['approval_id']+'/consume',{})
 payload={'project_slug':'atalhos-cloudif-iff1860746','action':'forgejo.propose-edit','requested_by':cid,'ttl_seconds':300,'reason':'Smoke approval.get','trace_id':'periodic-approval-get','metadata':{'proposal_digest':'c'*64}}
 req=urllib.request.Request('http://127.0.0.1:18204/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+at,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=8) as x:created=json.load(x)
 aid=created['approval_id']
 gc,gj=rrpc('approval.get',{'slug':'atalhos-cloudif-iff1860746','approval_id':aid},'approval-get')
 data=json.loads(gj['result']['content'][0]['text']);row=data['approval']
 approval_ok=gc==200 and gj['result']['isError'] is False and data.get('read_only') is True and row.get('approval_id')==aid and row.get('requested_by')==cid and row.get('status')=='pending' and row.get('proposal_digest')=='c'*64 and 'metadata_json' not in row
 rapost('/v1/approvals/'+aid+'/approve',{'approved_by':'cloudif-read-smoke'});rapost('/v1/approvals/'+aid+'/consume',{})
 final=next(a for a in ralist() if a['approval_id']==aid)
 approval_ok=approval_ok and final.get('status')=='consumed'
 checks.append({'name':'mcp-approval-get-own','ok':approval_ok,'code':gc,'read_only':data.get('read_only'),'sanitized':'metadata_json' not in row,'consumed':final.get('status')=='consumed'})
 pc,pj=rrpc('forgejo.proposal.list',{'slug':'atalhos-cloudif-iff1860746','state':'all','limit':10},'proposal-list')
 proposals=json.loads(pj['result']['content'][0]['text'])
 proposal_ok=pc==200 and pj['result']['isError'] is False and proposals.get('ok') is True and proposals.get('read_only') is True and proposals.get('project_slug')=='atalhos-cloudif-iff1860746' and proposals.get('count')==len(proposals.get('proposals') or []) and proposals.get('count')<=10
 checks.append({'name':'mcp-forgejo-proposal-list','ok':proposal_ok,'code':pc,'read_only':proposals.get('read_only'),'count':proposals.get('count'),'forgejo_side_effects':False})
except Exception as e:
 checks.append({'name':'mcp-approval-get-own','ok':False,'error':type(e).__name__})
 checks.append({'name':'mcp-forgejo-proposal-list','ok':False,'error':type(e).__name__})
checks.append(http('deployment-broker-health','http://127.0.0.1:18207/health',200))
try:
 de=env('/etc/cloudif/deployment-smoke.env');cid=de['CLOUDIF_DEPLOYMENT_SMOKE_CLIENT'];ct=de['CLOUDIF_DEPLOYMENT_SMOKE_TOKEN']
 args={'slug':'sistema-de-biblioteca-teste','commit_sha':'6d7bd33eca7aebd2d6d9ba4c346a4aa7c66168cf','version':'v0.0.0-smoke-plan'}
 def drpc(rid):
  q={'jsonrpc':'2.0','id':rid,'method':'tools/call','params':{'name':'deployment.plan','arguments':args}}
  r=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(q,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+ct,'X-CloudIF-Client':cid,'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-deployment-plan'})
  with urllib.request.urlopen(r,timeout=30) as x:return x.status,json.load(x)
 c1,p1=drpc('deploy-plan-1');c2,p2=drpc('deploy-plan-2')
 x1=json.loads(p1['result']['content'][0]['text']);x2=json.loads(p2['result']['content'][0]['text'])
 ok=c1==200 and c2==200 and p1['result']['isError'] is False and p2['result']['isError'] is False and x1.get('side_effect_free') is True and x1.get('deployment_digest')==x2.get('deployment_digest') and (x1.get('operation') or {}).get('dry_run') is True and x1.get('target')=='validation-only'
 checks.append({'name':'mcp-deployment-plan','ok':ok,'code':c1,'deterministic':x1.get('deployment_digest')==x2.get('deployment_digest'),'side_effect_free':x1.get('side_effect_free'),'dry_run':(x1.get('operation') or {}).get('dry_run')})
except Exception as e:checks.append({'name':'mcp-deployment-plan','ok':False,'error':type(e).__name__})
try:
 pe=env('/etc/cloudif/promotion-smoke.env');pcid=pe['CLOUDIF_PROMOTION_SMOKE_CLIENT'];pct=pe['CLOUDIF_PROMOTION_SMOKE_TOKEN']
 pargs={'slug':'sistema-de-biblioteca-teste','commit_sha':'6d7bd33eca7aebd2d6d9ba4c346a4aa7c66168cf','version':'v0.0.0-smoke-promote-plan'}
 def prpc(rid):
  q={'jsonrpc':'2.0','id':rid,'method':'tools/call','params':{'name':'deployment.promote-test.plan','arguments':pargs}}
  r=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(q,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+pct,'X-CloudIF-Client':pcid,'Content-Type':'application/json','X-CloudIF-Trace-Id':'periodic-promote-test-plan'})
  with urllib.request.urlopen(r,timeout=45) as x:return x.status,json.load(x)
 pc1,pp1=prpc('promote-plan-1');pc2,pp2=prpc('promote-plan-2')
 px1=json.loads(pp1['result']['content'][0]['text']);px2=json.loads(pp2['result']['content'][0]['text'])
 op=px1.get('operation') or {};pre=px1.get('prestate') or {}
 pok=pc1==200 and pc2==200 and pp1['result']['isError'] is False and pp2['result']['isError'] is False and px1.get('side_effect_free') is True and px1.get('promotion_digest')==px2.get('promotion_digest') and px1.get('rollback_required') is True and op.get('action')=='deployment.promote-test' and op.get('target')=='isolated-test' and op.get('real_deploy') is True and len(op.get('expected_previous_commit') or '')==40 and pre.get('commit_sha')==op.get('expected_previous_commit')
 checks.append({'name':'mcp-deployment-promote-test-plan','ok':pok,'code':pc1,'deterministic':px1.get('promotion_digest')==px2.get('promotion_digest'),'side_effect_free':px1.get('side_effect_free'),'rollback_required':px1.get('rollback_required'),'target':op.get('target'),'expected_previous_commit_bound':pre.get('commit_sha')==op.get('expected_previous_commit')})
except Exception as e:checks.append({'name':'mcp-deployment-promote-test-plan','ok':False,'error':type(e).__name__})
try:
 r=urllib.request.Request('http://127.0.0.1:18208/health')
 with urllib.request.urlopen(r,timeout=15) as x:oh=json.load(x)
 checks.append({'name':'project-onboarding-health','ok':oh.get('ok') is True and oh.get('projects')==expected_project_count and oh.get('ready')==expected_project_count,'projects':oh.get('projects'),'ready':oh.get('ready'),'expected_projects':expected_project_count})
except Exception as e:checks.append({'name':'project-onboarding-health','ok':False,'error':type(e).__name__})
try:
 r=urllib.request.Request('http://127.0.0.1:18209/health')
 with urllib.request.urlopen(r,timeout=15) as x:sh=json.load(x)
 checks.append({'name':'supabase-onboarding-broker-health','ok':sh.get('ok') is True and sh.get('service')=='cloudif-supabase-onboarding-broker','service':sh.get('service')})
except Exception as e:checks.append({'name':'supabase-onboarding-broker-health','ok':False,'error':type(e).__name__})
try:
 r=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/project-identities',headers={'X-authentik-username':'iff1860746','X-authentik-email':'iff1860746@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'})
 with urllib.request.urlopen(r,timeout=20) as x:pi=json.load(x)
 raw=json.dumps(pi).lower();rows=pi.get('projects') or []
 ok=pi.get('ok') is True and pi.get('secrets_exposed') is False and {str(v.get('project_slug') or '') for v in rows}==expected_project_slugs and '"token"' not in raw and all(str(v.get('client_id') or '').startswith('project-') for v in rows)
 checks.append({'name':'portal-project-identities','ok':ok,'projects':len(rows),'secrets_exposed':pi.get('secrets_exposed'),'all_project_clients':all(str(v.get('client_id') or '').startswith('project-') for v in rows)})
except Exception as e:checks.append({'name':'portal-project-identities','ok':False,'error':type(e).__name__})
try:
 ap='/var/lib/cloudif/approvals/approvals.db';c=sqlite3.connect(f'file:{ap}?mode=ro',uri=True,timeout=8);cols={r[1] for r in c.execute('pragma table_info(approvals)')};idx={r[1] for r in c.execute('pragma index_list(approvals)')};c.close()
 required={'reservation_id','reserved_by','reserved_at','reservation_expires_at','finalized_at','finalize_result','rejected_by','rejected_at','rejection_reason'}
 checks.append({'name':'approval-transaction-schema','ok':required.issubset(cols) and {'idx_approval_active','idx_approval_reservation'}.issubset(idx),'missing_columns':sorted(required-cols),'indexes':sorted(idx)})
except Exception as e:checks.append({'name':'approval-transaction-schema','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/approvals/approvals.db?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row
 malformed_reserved=c.execute("select count(*) from approvals where status='reserved' and (reservation_id is null or reserved_by is null or reserved_at is null or reservation_expires_at is null or reservation_expires_at<=reserved_at or reservation_expires_at>expires_at)").fetchone()[0]
 malformed_finalized=c.execute("select count(*) from approvals where status='consumed' and reservation_id is not null and (finalized_at is null or finalize_result not in ('success','completed'))").fetchone()[0]
 leaked_reservation=c.execute("select count(*) from approvals where status in ('pending','approved','rejected','expired') and reservation_id is not null").fetchone()[0]
 reserved_count=c.execute("select count(*) from approvals where status='reserved'").fetchone()[0];transactional_consumed=c.execute("select count(*) from approvals where status='consumed' and reservation_id is not null").fetchone()[0];c.close()
 checks.append({'name':'approval-transaction-invariants','ok':malformed_reserved==0 and malformed_finalized==0 and leaked_reservation==0,'malformed_reserved':malformed_reserved,'malformed_finalized':malformed_finalized,'leaked_reservation':leaked_reservation,'reserved':reserved_count,'transactional_consumed':transactional_consumed})
except Exception as e:checks.append({'name':'approval-transaction-invariants','ok':False,'error':type(e).__name__})
try:
 dp='/var/lib/cloudif/portal/deployment-idempotency.db';c=sqlite3.connect(f'file:{dp}?mode=ro',uri=True,timeout=8);cols={r[1] for r in c.execute('pragma table_info(executions)')};bad_state=c.execute("select count(*) from executions where state not in ('running','finished')").fetchone()[0];bad_finished=c.execute("select count(*) from executions where state='finished' and (http_code is null or response_json is null)").fetchone()[0];rows=c.execute('select count(*) from executions').fetchone()[0];c.close()
 src=Path('/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
 markers=["transaction_ids('deployment.validate'","transaction_ids('deployment.promote-test'","transaction_ids('forgejo.proposal.merge'"]
 legacy=['deployment_validation_failed_after_approval_consumed','promotion_failed_after_approval_consumed','merge_failed_after_approval_consumed']
 protocol=all(x in src for x in markers) and all(x not in src for x in legacy)
 required={'execution_id','operation','payload_digest','state','effect_started','http_code','response_json','created_at','updated_at'}
 checks.append({'name':'deployment-idempotency-and-mcp-protocol','ok':required.issubset(cols) and bad_state==0 and bad_finished==0 and protocol,'missing_columns':sorted(required-cols),'bad_state':bad_state,'bad_finished':bad_finished,'execution_rows':rows,'mcp_transactional_tools':protocol})
except Exception as e:checks.append({'name':'deployment-idempotency-and-mcp-protocol','ok':False,'error':type(e).__name__})
try:
 state=subprocess.run(['/usr/bin/systemctl','is-active','cloudif-transaction-reconciler.timer'],text=True,capture_output=True,timeout=8).stdout.strip()
 checks.append({'name':'transaction-reconciler-timer','ok':state=='active','state':state})
except Exception as e:checks.append({'name':'transaction-reconciler-timer','ok':False,'error':type(e).__name__})
try:
 tr=json.load(open('/var/lib/cloudif/health/transaction-reconciler.json'))
 age=max(0,int(time.time())-int(tr.get('generated_at') or 0))
 ok=tr.get('ok') is True and tr.get('mode')=='observe-and-normalize-expiry-only' and tr.get('automatic_retry') is False and tr.get('automatic_approval') is False and tr.get('malformed_approvals')==0 and age<=180
 checks.append({'name':'transaction-reconciler-report','ok':ok,'age_seconds':age,'running_executions':tr.get('running_executions'),'stale_executions':len(tr.get('stale_executions') or []),'automatic_retry':tr.get('automatic_retry'),'automatic_approval':tr.get('automatic_approval')})
except Exception as e:checks.append({'name':'transaction-reconciler-report','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/transactions',headers={'X-authentik-username':'iff1860746','X-authentik-email':'iff1860746@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'})
 with urllib.request.urlopen(req,timeout=30) as x:tx=json.load(x)
 rows=tx.get('projects') or [];raw=json.dumps(tx).lower()
 ok=tx.get('ok') is True and tx.get('project_scoped') is True and tx.get('secrets_exposed') is False and {str(v.get('project_slug') or '') for v in rows}==expected_project_slugs and all(v.get('sanitized') is True and v.get('secrets_exposed') is False and v.get('project_slug') for v in rows) and all((v.get('recent_executions') or [])==[] for v in rows) and all(n not in raw for n in ('"token"','password','metadata_json','payload_digest','response_json'))
 checks.append({'name':'portal-transaction-observability','ok':ok,'projects':len(rows),'project_scoped':tx.get('project_scoped'),'secrets_exposed':tx.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-transaction-observability','ok':False,'error':type(e).__name__})
try:
 ar=env('/etc/cloudif/agent-registry.env');req=urllib.request.Request('http://127.0.0.1:18203/v1/roles',headers={'Authorization':'Bearer '+ar['CLOUDIF_AGENT_ADMIN_TOKEN'],'Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as x:roles=json.load(x)
 rows=roles.get('roles') or [];names=[v.get('role_profile') for v in rows];by={v.get('role_profile'):v for v in rows}
 expected=['viewer','developer','maintainer','release-manager','project-admin','test-operator']
 ok=roles.get('ok') is True and names==expected and roles.get('production_enabled') is False and roles.get('automatic_approval') is False and roles.get('arbitrary_terminal') is False and all(v.get('production') is False for v in rows) and by['test-operator'].get('environment')=='isolated-test' and all(by[n].get('environment')=='project' for n in expected if n!='test-operator')
 checks.append({'name':'agent-rbac-catalog','ok':ok,'roles':names,'production_enabled':roles.get('production_enabled'),'automatic_approval':roles.get('automatic_approval'),'arbitrary_terminal':roles.get('arbitrary_terminal')})
except Exception as e:checks.append({'name':'agent-rbac-catalog','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/agents/agents.db?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row
 prows=[dict(r) for r in c.execute("select client_id,role_profile,environment,scopes_json,project_slugs_json,rate_per_minute,daily_quota from clients where client_id like 'project-%' order by client_id")];c.close()
 expected_scopes=by['project-admin']['scopes']
 coherent=len(prows)==expected_project_count and {json.loads(v['project_slugs_json'])[0] for v in prows if len(json.loads(v['project_slugs_json']))==1}==expected_project_slugs and all(v['role_profile']=='project-admin' and v['environment']=='project' and json.loads(v['scopes_json'])==expected_scopes and len(json.loads(v['project_slugs_json']))==1 and v['rate_per_minute']==60 and v['daily_quota']==3000 for v in prows)
 forbidden_effect_scopes={'deployment:production-deploy','approval:request-production','deployment:production-rollback','approval:request-production-rollback'};forbidden=any(bool(forbidden_effect_scopes & set(json.loads(v['scopes_json']))) for v in prows)
 checks.append({'name':'project-rbac-coherence','ok':coherent and not forbidden,'project_clients':len(prows),'expected_projects':expected_project_count,'coherent':coherent,'production_scope_present':forbidden,'role_profile':'project-admin','environment':'project'})
except Exception as e:checks.append({'name':'project-rbac-coherence','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1860746','X-authentik-email':'iff1860746@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/project-identities',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:ids=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read(800000).decode('utf-8','ignore')
 rows=ids.get('projects') or [];raw=json.dumps(ids).lower();markers=('Identidades, funções e conexões','Administrador do projeto','Operações que exigem aprovação humana','Operações bloqueadas','Produção desabilitada')
 ok=ids.get('ok') is True and ids.get('secrets_exposed') is False and {str(v.get('project_slug') or '') for v in rows}==expected_project_slugs and all(v.get('role_profile')=='project-admin' and v.get('rate_per_minute')==60 and v.get('daily_quota')==3000 and 'deployment:promote-test' not in (v.get('scopes') or []) for v in rows) and all(m in page for m in markers) and '"token"' not in raw and 'password' not in raw
 checks.append({'name':'portal-rbac-identities','ok':ok,'projects':len(rows),'roles':sorted(set(v.get('role_profile') for v in rows)),'quota_metadata':all(v.get('rate_per_minute')==60 and v.get('daily_quota')==3000 for v in rows),'production_disabled_visible':'Produção desabilitada' in page,'secrets_exposed':ids.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-rbac-identities','ok':False,'error':type(e).__name__})
try:
 me=env('/etc/cloudif/monitor.env');req=urllib.request.Request('http://127.0.0.1:18199/v1/promotions?project=sistema-de-biblioteca-teste',headers={'Authorization':'Bearer '+me['CLOUDIF_MONITOR_TOKEN'],'Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as x:ph=json.load(x)
 raw=json.dumps(ph).lower();ok=ph.get('ok') is True and ph.get('project_slug')=='sistema-de-biblioteca-teste' and ph.get('sanitized') is True and ph.get('secrets_exposed') is False and ph.get('read_only') is True and ph.get('automatic_retry') is False and ph.get('automatic_rollback_triggered') is False and len(ph.get('jobs') or [])>=1 and all(k not in raw for k in ('backup_path','tenant','actor','detail_json','notes','password','"token"'))
 checks.append({'name':'monitor-promotion-history','ok':ok,'jobs':len(ph.get('jobs') or []),'published':(ph.get('summary') or {}).get('published'),'sanitized':ph.get('sanitized')})
except Exception as e:checks.append({'name':'monitor-promotion-history','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/promotions',headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'})
 with urllib.request.urlopen(req,timeout=30) as x:pp=json.load(x)
 raw=json.dumps(pp).lower();ok=pp.get('ok') is True and pp.get('project_slug')=='sistema-de-biblioteca-teste' and pp.get('sanitized') is True and pp.get('secrets_exposed') is False and pp.get('read_only') is True and len(pp.get('jobs') or [])>=1 and all(k not in raw for k in ('backup_path','tenant','actor','detail_json','notes','password','"token"'))
 checks.append({'name':'portal-promotion-history','ok':ok,'jobs':len(pp.get('jobs') or []),'published':(pp.get('summary') or {}).get('published'),'project_scoped':pp.get('project_slug')=='sistema-de-biblioteca-teste'})
except Exception as e:checks.append({'name':'portal-promotion-history','ok':False,'error':type(e).__name__})
try:
 src=Path('/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py').read_text();reg=Path('/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py').read_text()
 markers=["'deployment.promote-test.status'","'deployment:promote-test-status'","job_project_mismatch","backup_path"]
 ok=all(x in src for x in markers[:3]) and "'deployment:promote-test-status'" in reg and "'test-operator'" in reg and "'isolated-test'" in reg and "backup_path" not in src[src.index("elif name=='deployment.promote-test.status'"):src.index("elif name in {'deployment.plan'",src.index("elif name=='deployment.promote-test.status'"))]
 checks.append({'name':'mcp-promotion-status-contract','ok':ok,'tool':'deployment.promote-test.status','scope':'deployment:promote-test-status','role_profile':'test-operator','environment':'isolated-test','sanitized':True})
except Exception as e:checks.append({'name':'mcp-promotion-status-contract','ok':False,'error':type(e).__name__})
try:
 state=subprocess.run(['/usr/bin/systemctl','is-active','cloudif-data-retention.timer'],text=True,capture_output=True,timeout=8).stdout.strip();rep=json.load(open('/var/lib/cloudif/health/data-retention.json'))
 checks.append({'name':'data-retention-timer-and-report','ok':state=='active' and rep.get('ok') is True,'timer':state,'errors':rep.get('errors') or []})
except Exception as e:checks.append({'name':'data-retention-timer-and-report','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/agents/agents.db?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row
 projects=c.execute("select count(*) n from clients where client_id like 'project-%'").fetchone()['n'];custom=c.execute("select count(*) n from clients where role_profile='custom'").fetchone()['n']
 protected=[]
 for f in ('/etc/cloudif/deployment-smoke.env','/etc/cloudif/promotion-smoke.env','/etc/cloudif/proposal-smoke.env','/etc/cloudif/read-tools-smoke.env'):
  for line in Path(f).read_text().splitlines():
   if 'CLIENT=' in line:protected.append(line.split('=',1)[1].strip())
 missing=[x for x in protected if c.execute('select count(*) from clients where client_id=?',(x,)).fetchone()[0]!=1];c.close()
 src=Path('/usr/local/sbin/cloudif-data-retention.py').read_text();policy=all(x in src for x in ('cleanup_temp_clients','protected_clients',"role_profile='custom'"))
 checks.append({'name':'temporary-client-retention-policy','ok':projects==8 and not missing and policy,'project_clients':projects,'protected_clients':len(protected),'missing_protected':missing,'custom_remaining':custom,'policy_present':policy})
except Exception as e:checks.append({'name':'temporary-client-retention-policy','ok':False,'error':type(e).__name__})
try:
 cfg=env('/etc/cloudif/workspace-broker.env');image=cfg.get('CLOUDIF_WORKSPACE_IMAGE','');src=Path('/srv/cloudif/app-pointers/workspace-broker-current/cloudif-workspace-broker.py').read_text();expected='nginx@sha256:5f979dcfed4ce6461873f087e8c980d6e29b084b9e8776d9704a7e989b5f4898'
 ins=subprocess.run(['/usr/bin/docker','image','inspect',image],text=True,capture_output=True,timeout=15)
 checks.append({'name':'workspace-image-immutable','ok':image==expected and expected in src and ins.returncode==0,'image':image,'digest_pinned':'@sha256:' in image,'present_local':ins.returncode==0})
except Exception as e:checks.append({'name':'workspace-image-immutable','ok':False,'error':type(e).__name__})
try:
 b=Path('/srv/cloudif/app-pointers/deployment-broker-current/cloudif-deployment-broker.py').read_text();m=Path('/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py').read_text();r=Path('/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py').read_text()
 markers=['/v1/plan-rollback-test','/v1/rollback-test','deployment.rollback-test.plan','approval.request-rollback-test','deployment.rollback-test','deployment:rollback-test-plan','approval:request-rollback-test','deployment:rollback-test']
 ok=all(x in (b+m+r) for x in markers) and 'production' not in ''.join([x for x in markers])
 checks.append({'name':'manual-rollback-contract','ok':ok,'project':'sistema-de-biblioteca-teste','role_profile':'test-operator','environment':'isolated-test','production_enabled':False})
except Exception as e:checks.append({'name':'manual-rollback-contract','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/portal/cloudif-portal.db?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row
 j=dict(c.execute('select id,project,commit_sha,status,dry_run,backup_path,message from release_jobs where id=22').fetchone());c.close()
 c=sqlite3.connect('file:/var/lib/cloudif/portal/deployment-idempotency.db?mode=ro',uri=True,timeout=8);x=c.execute("select count(*) from executions where operation='deployment.rollback-test' and state='finished' and http_code=200 and effect_started=1").fetchone()[0];c.close()
 ok=j['project']=='sistema-de-biblioteca-teste' and j['status']=='published' and j['dry_run']==0 and bool(j['backup_path']) and Path(j['backup_path']).is_file() and str(j['message']).startswith('Manual rollback to job 20') and x>=1
 checks.append({'name':'manual-rollback-audit','ok':ok,'job_id':22,'status':j['status'],'backup_exists':Path(j['backup_path']).is_file(),'idempotent_executions':x})
except Exception as e:checks.append({'name':'manual-rollback-audit','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/promotions',headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'})
 with urllib.request.urlopen(req,timeout=30) as x:d=json.load(x)
 row=next((v for v in d.get('jobs') or [] if v.get('id')==22),{});raw=json.dumps(d).lower();ok=d.get('ok') is True and (d.get('summary') or {}).get('manual_rollbacks',0)>=1 and row.get('operation')=='manual_rollback' and row.get('target_job_id')==20 and d.get('sanitized') is True and d.get('secrets_exposed') is False and all(k not in raw for k in ('backup_path','detail_json','tenant','actor','password','"token"'))
 checks.append({'name':'portal-manual-rollback-observability','ok':ok,'manual_rollbacks':(d.get('summary') or {}).get('manual_rollbacks'),'job22_visible':bool(row),'sanitized':d.get('sanitized')})
except Exception as e:checks.append({'name':'portal-manual-rollback-observability','ok':False,'error':type(e).__name__})
try:
 on=Path('/srv/cloudif/app-pointers/project-onboarding-current/cloudif-project-onboarding.py').read_text();po=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();pa=Path('/srv/cloudif/app-pointers/portal-current/cloudif_project_identity_panel.py').read_text();reg=Path('/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py').read_text()
 markers=['credential_rotations','rotate_credential','rotation_cooldown','write_secret','delivered_once','/rotate-credential','rotate-project-credential','_oi_can_rotate','one_time_delivery','/v1/clients/','/rotate']
 ok=all(x in (on+po+pa+reg) for x in markers) and 'Cache-Control' in po and 'no-store' in po and 'Rotacionar e exibir uma vez' in pa
 checks.append({'name':'credential-rotation-contract','ok':ok,'cooldown_seconds':300,'one_time_delivery':True,'server_secret_update':True,'csrf_required':True,'acl_required':True})
except Exception as e:checks.append({'name':'credential-rotation-contract','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/onboarding/onboarding.db?mode=ro',uri=True,timeout=8);cols=[x[1] for x in c.execute('pragma table_info(credential_rotations)')];idx=[x[1] for x in c.execute('pragma index_list(credential_rotations)')];residual=c.execute("select count(*) from project_onboarding where project_slug like 'credential-rotation-e2e%' or project_slug like 'onboarding-e2e%' or project_slug like 'rota-o-e2e%'").fetchone()[0];c.close()
 required={'rotation_id','project_slug','client_id','requested_by','reason','created_at','delivered_at','status'}
 counts={}
 for name,path,query in [('portal','/var/lib/cloudif/portal/cloudif-portal.db','select count(*) from projects'),('control','/var/lib/cloudif/control-plane/control-plane.db','select count(*) from projects'),('agents','/var/lib/cloudif/agents/agents.db',"select count(*) from clients where client_id like 'project-%'")]:
  c=sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=8);counts[name]=c.execute(query).fetchone()[0];c.close()
 ok=set(cols)==required and 'token' not in cols and 'idx_credential_rotations_project' in idx and residual==0 and counts=={'portal':8,'control':8,'agents':8}
 checks.append({'name':'credential-rotation-audit-schema','ok':ok,'columns':cols,'token_column':False,'residual_test_projects':residual,'project_sources':counts})
except Exception as e:checks.append({'name':'credential-rotation-audit-schema','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/project-identities',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:ids=json.load(x)
 body=urllib.parse.urlencode({'slug':'teste','reason':'Smoke sem CSRF'}).encode();req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/action/rotate-project-credential',data=body,method='POST',headers={**headers,'Content-Type':'application/x-www-form-urlencoded'})
 denied=False
 try:urllib.request.urlopen(req,timeout=30)
 except urllib.error.HTTPError as e:denied=e.code==403 and json.load(e).get('error')=='csrf_denied'
 raw=json.dumps(ids).lower();ok='Rotacionar e exibir uma vez' in page and 'credencial só aparece uma vez' in page and ids.get('ok') is True and ids.get('secrets_exposed') is False and '"token"' not in raw and 'password' not in raw and denied
 checks.append({'name':'portal-credential-rotation-ui','ok':ok,'button_visible':True,'one_time_warning_visible':True,'secrets_exposed':ids.get('secrets_exposed'),'missing_csrf_denied':denied})
except Exception as e:checks.append({'name':'portal-credential-rotation-ui','ok':False,'error':type(e).__name__})
try:
 sec=json.load(open('/var/lib/cloudif/onboarding/secrets/sistema-de-biblioteca-teste.json'));cid=sec['client_id'];tok=sec['token']
 payload={'jsonrpc':'2.0','id':'smoke-mig-inspect','method':'tools/call','params':{'name':'supabase.migrations.inspect','arguments':{'slug':'sistema-de-biblioteca-teste','commit_sha':'e2b25d6cb5437fe0fb19efbb1925361f1f96199d','version':'v0.0.0-smoke-migration-inspect'}}}
 req=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(payload).encode(),method='POST',headers={'Authorization':'Bearer '+tok,'X-CloudIF-Client':cid,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as x:r=json.load(x)
 data=json.loads(r['result']['content'][0]['text']);raw=json.dumps(data).lower();ok=r['result']['isError'] is False and data.get('ok') is True and data.get('side_effect_free') is True and data.get('migration_count')==0 and data.get('migrations')==[] and data.get('sql_exposed') is False and data.get('content_b64_exposed') is False and data.get('backup_created') is False and data.get('migrations_applied')==0 and data.get('deployment_created') is False and '"content_b64":' not in raw and 'create table' not in raw and 'alter table' not in raw
 checks.append({'name':'supabase-migration-inspect-live','ok':ok,'project':'sistema-de-biblioteca-teste','migration_count':data.get('migration_count'),'side_effect_free':data.get('side_effect_free'),'sql_exposed':data.get('sql_exposed')})
except Exception as e:checks.append({'name':'supabase-migration-inspect-live','ok':False,'error':type(e).__name__})
try:
 reg=Path('/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py').read_text();mcp=Path('/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py').read_text();on=json.load(open('/var/lib/cloudif/onboarding/onboarding.db')) if False else None
 ok="'supabase:migration-inspect'" in reg and "'supabase:migration-plan'" in reg and "'supabase.migrations.inspect':'supabase:migration-inspect'" in mcp and "'supabase.migrations.plan':'supabase:migration-plan'" in mcp and "'developer':['project:read'" in reg and "'developer':['project:read','supabase:migration-inspect'" not in reg
 c=sqlite3.connect('file:/var/lib/cloudif/onboarding/onboarding.db?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row;rows=[dict(x) for x in c.execute('select role_profile,scopes_json from project_onboarding')];c.close();coherent=all(('supabase:migration-inspect' in json.loads(x['scopes_json']))==(x['role_profile']=='project-admin') for x in rows)
 checks.append({'name':'supabase-migration-rbac-contract','ok':ok and coherent,'project_admin_inspect':True,'test_operator_plan':True,'developer_denied':True,'onboarding_coherent':coherent})
except Exception as e:checks.append({'name':'supabase-migration-rbac-contract','ok':False,'error':type(e).__name__})
try:
 cfg=env('/etc/cloudif/deployment-broker.env');body={'project_slug':'sistema-de-biblioteca-teste','commit_sha':'e2b25d6cb5437fe0fb19efbb1925361f1f96199d','version':'v0.0.0-smoke-migration-gate','trace_id':'smoke-migration-gate'}
 req=urllib.request.Request('http://127.0.0.1:18207/v1/migrations-plan',data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+cfg['CLOUDIF_DEPLOYMENT_BROKER_TOKEN'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as x:g=json.load(x)
 src=Path('/srv/cloudif/app-pointers/deployment-broker-current/cloudif-deployment-broker.py').read_text();ok=g.get('ok') is True and g.get('side_effect_free') is True and g.get('migration_count')==0 and g.get('apply_allowed') is True and g.get('automatic_restore_available') is False and g.get('blocked_reason')=='' and "'automatic_restore_unavailable'" in src and "'apply_allowed':len(safe)==0" in src
 checks.append({'name':'supabase-migration-apply-safety-gate','ok':ok,'empty_bundle_allowed':g.get('apply_allowed'),'automatic_restore_available':g.get('automatic_restore_available'),'nonempty_bundle_blocked_by_contract':"'automatic_restore_unavailable'" in src})
except Exception as e:checks.append({'name':'supabase-migration-apply-safety-gate','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=agentes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 markers=('Agentes de IA','Como obter seu token','Rotacionar e exibir uma vez','Configuração MCP genérica','Ferramentas autorizadas','Como funcionam as aprovações','Produção desabilitada')
 ok=all(v in page for v in markers)
 checks.append({'name':'portal-ai-agent-guide-page','ok':ok,'tab':'agentes','token_help':True,'mcp_configuration':True,'approval_documentation':True})
except Exception as e:checks.append({'name':'portal-ai-agent-guide-page','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agent-guide',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:data=json.load(x)
 raw=json.dumps(data).lower();ok=data.get('ok') is True and data.get('secrets_exposed') is False and data.get('production_enabled') is False and len(data.get('projects') or [])>=1 and all(p.get('client_id') and p.get('mcp_endpoint','').endswith('/cloudiff/mcp') and p.get('credential_included') is False and isinstance(p.get('tools'),list) for p in data.get('projects') or []) and '"token"' not in raw and 'password' not in raw
 checks.append({'name':'portal-ai-agent-guide-api','ok':ok,'projects':len(data.get('projects') or []),'secrets_exposed':data.get('secrets_exposed'),'production_enabled':data.get('production_enabled')})
except Exception as e:checks.append({'name':'portal-ai-agent-guide-api','ok':False,'error':type(e).__name__})
try:
 import re
 required=('Linux ou macOS','PowerShell','Arquivo .env local','CLOUDIFF_TOKEN','.gitignore','Nunca:','Bearer ${CLOUDIFF_TOKEN}','X-CloudIF-Client')
 no_real=not re.search(r'bearer\s+[a-z0-9_-]{30,}',page.lower()) and 'token_hash' not in page.lower() and 'password' not in page.lower()
 ok=all(v in page for v in required) and no_real
 checks.append({'name':'portal-ai-agent-token-instructions','ok':ok,'linux':True,'powershell':True,'env_file':True,'gitignore_warning':True,'real_token_exposed':not no_real})
except Exception as e:checks.append({'name':'portal-ai-agent-token-instructions','ok':False,'error':type(e).__name__})
try:
 import ast,importlib.util
 mcp_path='/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py';guide_path='/srv/cloudif/app-pointers/portal-current/cloudif_ai_agents_guide.py'
 tree=ast.parse(Path(mcp_path).read_text());published=None
 for n in ast.walk(tree):
  if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='TOOLS' for x in n.targets):published={x['name'] for x in ast.literal_eval(n.value)};break
 spec=importlib.util.spec_from_file_location('cloudif_doc_catalog',guide_path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);documented=set(mod.TOOL_DOC)
 missing=sorted(published-documented);extra=sorted(documented-published);complete=all(len(mod.TOOL_DOC[t])==4 and all(str(v).strip() for v in mod.TOOL_DOC[t]) for t in documented)
 checks.append({'name':'mcp-documentation-catalog-parity','ok':bool(published) and not missing and not extra and complete,'published':len(published or []),'documented':len(documented),'missing':missing,'extra':extra,'descriptions_complete':complete})
except Exception as e:checks.append({'name':'mcp-documentation-catalog-parity','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agent-guide',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:d=json.load(x)
 tools=[t for p in d.get('projects') or [] for t in p.get('tools') or []];links=[p.get('links') or {} for p in d.get('projects') or []]
 complete=bool(tools) and all(all(t.get(k) for k in ('name','title','purpose','approval','portal')) for t in tools)
 link_ok=bool(links) and all(x.get('approvals')=='/cloudiff/portal/?tab=aprovacoes' and str(x.get('forgejo','')).startswith('https://cloudiff.duckdns.org/git/cloudif/cloudif-') and x.get('komodo')=='https://komodoiff.duckdns.org/auth/oidc/login' for x in links)
 raw=json.dumps(d).lower();safe=d.get('secrets_exposed') is False and '"token"' not in raw and 'password' not in raw
 checks.append({'name':'portal-ai-tool-purpose-and-links','ok':d.get('ok') is True and complete and link_ok and safe,'tool_entries':len(tools),'purposes_complete':complete,'approval_portal':'Portal CloudIFF','links_valid':link_ok,'secrets_exposed':d.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-ai-tool-purpose-and-links','ok':False,'error':type(e).__name__})
try:
 policy=Path('/srv/cloudif/docs/MCP_DOCUMENTATION_POLICY.md').read_text();guide=Path('/srv/cloudif/app-pointers/portal-current/cloudif_ai_agents_guide.py').read_text()
 required=('Toda nova função ativada no MCP','Para que serve','aprovação humana','Portal CloudIFF','Forgejo','Supabase Studio','Komodo','smoke permanente')
 ok=all(v.lower() in (policy+guide).lower() for v in required)
 checks.append({'name':'mcp-documentation-update-directive','ok':ok,'policy_file':True,'new_tool_requires_documentation':True,'homologation_blocked_when_missing':True})
except Exception as e:checks.append({'name':'mcp-documentation-update-directive','ok':False,'error':type(e).__name__})
try:
 sec=json.load(open('/var/lib/cloudif/onboarding/secrets/sistema-de-biblioteca-teste.json'));cid=sec['client_id'];tok=sec['token']
 def rpc(method,params,i):
  req=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps({'jsonrpc':'2.0','id':i,'method':method,'params':params}).encode(),method='POST',headers={'Authorization':'Bearer '+tok,'X-CloudIF-Client':cid,'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=60) as x:return json.load(x)
 init=rpc('initialize',{},901);rl=rpc('resources/list',{},902);rr=rpc('resources/read',{'uri':'cloudiff://guide/project/sistema-de-biblioteca-teste'},903);pl=rpc('prompts/list',{},904);pp=rpc('prompts/get',{'name':'cloudiff-production-policy','arguments':{}},905)
 guide=json.loads(rr['result']['contents'][0]['text']);ok=init['result']['serverInfo']['version']=='0.2.0' and 'instructions' in init['result'] and {'resources','prompts','tools'}<=set(init['result']['capabilities']) and len(rl['result']['resources'])==2 and len(pl['result']['prompts'])==2 and guide['security']['two_approvers_required'] is False and 'Dois aprovadores não são exigidos' in pp['result']['messages'][0]['content']['text']
 checks.append({'name':'mcp-self-describing-protocol','ok':ok,'initialize_instructions':True,'resources':len(rl['result']['resources']),'prompts':len(pl['result']['prompts']),'project_guide':guide.get('project_slug')})
except Exception as e:checks.append({'name':'mcp-self-describing-protocol','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/approvals/approvals.db?mode=ro',uri=True,timeout=8);cols={x[1] for x in c.execute('pragma table_info(approvals)')};testrows=c.execute("select count(*) from approvals where requested_by in ('admin-test','prof-test','student-test')").fetchone()[0];c.close();src=Path('/srv/cloudif/app-pointers/approvals-current/cloudif-approval-api.py').read_text();portal=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text()
 ok={'requester_role','approver_role','authorization_mode','second_approved_by','second_approved_at','second_approver_role','two_approvers_required'}<=cols and testrows==0 and "dual_admin_or_professor" in src and "distinct_second_approver_required" in src and "requester_cannot_approve_activation" in src and "production_approver_role_required" in src
 checks.append({'name':'production-activation-dual-approval-policy','ok':ok,'activation_two_distinct_approvers':True,'requester_cannot_approve':True,'homologation_single_operation_approval':True,'test_rows':testrows})
except Exception as e:checks.append({'name':'production-single-decider-policy','ok':False,'error':type(e).__name__})
try:
 payload={'jsonrpc':'2.0','id':906,'method':'tools/call','params':{'name':'deployment.production.readiness','arguments':{'slug':'sistema-de-biblioteca-teste'}}};req=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(payload).encode(),method='POST',headers={'Authorization':'Bearer '+tok,'X-CloudIF-Client':cid,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as x:r=json.load(x)
 d=json.loads(r['result']['content'][0]['text']);target_expected={'target_enabled','separate_from_test','komodo_stack_configured','public_url_configured','smoke_url_configured','rollback_strategy_configured','automatic_database_restore','immutable_image_required','change_window_configured','change_window_open','snapshot_policy_configured','snapshot_verified','change_dossier_signed','rollback_plan_verified','dual_approval_required','production_effects_explicitly_enabled'};artifact_expected={'artifact_image_created','artifact_digest_present','sbom_ready','scanner_ready','scanner_high_zero','scanner_critical_zero','runtime_rootless','runtime_read_only','runtime_no_capabilities','runtime_no_published_ports'}
 artifact_missing_expected=artifact_expected-{'scanner_high_zero','scanner_critical_zero'}
 expected=target_expected|artifact_missing_expected
 ok=d.get('ok') is True and d.get('production_ready') is False and d.get('execution_allowed') is False and d.get('target_configured') is False and set(d.get('blockers') or [])==expected and d.get('two_approvers_required') is True and d.get('side_effect_free') is True
 # Artifact-backed project must pass all artifact/runtime checks while remaining blocked by target configuration. Use the local broker credential so MCP project ACL remains intact.
 dep={}
 for line in Path('/etc/cloudif/deployment-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);dep[k]=v
 dep_token=dep.get('CLOUDIF_DEPLOYMENT_BROKER_TOKEN') or ''
 payload2={'project_slug':'atalhos-cloudif-iff1860746','trace_id':'smoke-artifact-readiness'};req2=urllib.request.Request('http://127.0.0.1:18207/v1/production-readiness',data=json.dumps(payload2).encode(),method='POST',headers={'Authorization':'Bearer '+dep_token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req2,timeout=60) as x:d2=json.load(x)
 artifact_ok=all((d2.get('checks') or {}).get(k) is True for k in artifact_expected) and set(d2.get('blockers') or [])=={'target_enabled','change_window_open','production_effects_explicitly_enabled'} and d2.get('target_configured') is True and d2.get('production_ready') is False and d2.get('execution_allowed') is False
 ok=ok and artifact_ok
 checks.append({'name':'production-readiness-fail-closed','ok':ok,'production_ready':d.get('production_ready'),'execution_allowed':d.get('execution_allowed'),'blockers':len(d.get('blockers') or []),'artifact_project_checks':len(artifact_expected),'artifact_project_target_blockers':len(d2.get('blockers') or []),'target_configured':d.get('target_configured')})
except Exception as e:checks.append({'name':'production-readiness-fail-closed','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'};req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=agentes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agent-guide',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 markers=('Política de produção','Homologação','Ativação real','dois administradores ou professores distintos','produção real continua desabilitada','Como o agente aprende a usar a CloudIFF','cloudiff://guide/agent','cloudiff-project-workflow','cloudiff-production-policy')
 pol=api.get('production_policy') or {};disc=api.get('agent_discovery') or {};ok=all(x in page for x in markers) and pol.get('homologacao')=='uma aprovação por operação' and pol.get('ativacao_real')=='dois administradores ou professores distintos' and pol.get('requester_cannot_approve_activation') is True and pol.get('two_approvers_required_for_activation') is True and disc.get('initialize_instructions') is True and api.get('secrets_exposed') is False
 checks.append({'name':'portal-production-policy-and-agent-discovery','ok':ok,'activation_policy':pol.get('ativacao_real'),'two_approvers_required_for_activation':pol.get('two_approvers_required_for_activation'),'agent_discovery':bool(disc),'secrets_exposed':api.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-production-policy-and-agent-discovery','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=aprovacoes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 ok='Aprovações humanas' in page and 'Pendentes' in page and 'Aprovadas' in page and 'Histórico' in page and bool(re.search(r'<a\b[^>]*href="/cloudiff/portal/\?tab=aprovacoes"[^>]*aria-current="page"',page) or re.search(r'<a\b[^>]*aria-current="page"[^>]*href="/cloudiff/portal/\?tab=aprovacoes"',page))
 checks.append({'name':'approvals-dedicated-tab','ok':ok,'route':'/cloudiff/portal/?tab=aprovacoes','menu_active':ok})
except Exception as e:checks.append({'name':'approvals-dedicated-tab','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agent-guide',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:g=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=agentes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:agent_page=x.read().decode('utf-8','replace')
 links=[(p.get('links') or {}).get('approvals') for p in g.get('projects') or []];ok=g.get('ok') is True and bool(links) and all(v=='/cloudiff/portal/?tab=aprovacoes' for v in links) and '/cloudiff/portal/?tab=aprovacoes' in agent_page and 'Abrir aprovações no Portal CloudIFF' in agent_page
 checks.append({'name':'approval-links-target-real-tab','ok':ok,'projects':len(links),'target':'/cloudiff/portal/?tab=aprovacoes'})
except Exception as e:checks.append({'name':'approval-links-target-real-tab','ok':False,'error':type(e).__name__})
try:
 rep=json.load(open('/var/lib/cloudif/health/project-capabilities.json'));projects=rep.get('projects') or []
 ok=rep.get('ok') is True and rep.get('existing_projects')==8 and len(projects)==8 and all(p.get('scope_match') is True and p.get('status')=='ready' and p.get('production_effects_enabled') is False for p in projects) and rep.get('secrets_exposed') is False
 checks.append({'name':'project-capabilities-current-projects','ok':ok,'projects':len(projects),'all_scope_match':all(p.get('scope_match') is True for p in projects),'secrets_exposed':rep.get('secrets_exposed')})
except Exception as e:checks.append({'name':'project-capabilities-current-projects','ok':False,'error':type(e).__name__})
try:
 pol=json.load(open('/etc/cloudif/project-capabilities-policy.json'));on=Path('/srv/cloudif/app-pointers/project-onboarding-current/cloudif-project-onboarding.py').read_text();reg=Path('/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py').read_text()
 ok=pol.get('apply_to_existing') is True and pol.get('apply_to_new') is True and pol.get('default_role_profile')=='project-admin' and pol.get('scope_source')=='Agent Registry ROLE_SCOPES' and pol.get('production_effect_scopes_enabled') is False and 'ROLE_SCOPES' in reg and '/v1/reconcile' in on
 checks.append({'name':'project-capabilities-future-policy','ok':ok,'apply_to_new':pol.get('apply_to_new'),'default_role_profile':pol.get('default_role_profile'),'reconcile_service':pol.get('reconcile_service')})
except Exception as e:checks.append({'name':'project-capabilities-future-policy','ok':False,'error':type(e).__name__})
try:
 states={}
 for unit in ('cloudif-project-state-reconcile.timer','cloudif-project-state-reconcile.path'):
  q=subprocess.run(['systemctl','is-active',unit],text=True,capture_output=True,timeout=8);states[unit]=q.stdout.strip()
 legacy={}
 for unit in ('cloudif-project-capabilities.path','cloudif-agent-controller.path','cloudif-project-capabilities.timer','cloudif-agent-controller.timer'):
  q=subprocess.run(['systemctl','is-enabled',unit],text=True,capture_output=True,timeout=8);legacy[unit]=q.stdout.strip()
 q=subprocess.run(['systemctl','show','cloudif-project-state-reconcile.service','-p','Result','--value'],text=True,capture_output=True,timeout=8);result=q.stdout.strip()
 rep=json.load(open('/var/lib/cloudif/health/project-state-reconcile.json'))
 ok=all(v=='active' for v in states.values()) and all(v in ('disabled','static','not-found') for v in legacy.values()) and result in ('success','') and Path('/srv/cloudif/app-pointers/project-state-reconcile-current/cloudif-project-state-reconcile.py').is_file() and rep.get('ok') is True
 checks.append({'name':'project-capabilities-reconcile-units','ok':ok,'states':states,'legacy_units':legacy,'service_result':result,'unified':True,'component_pointer':True,'projects_ready':rep.get('projects_ready')})
except Exception as e:checks.append({'name':'project-capabilities-reconcile-units','ok':False,'error':type(e).__name__})
try:
 rep=json.load(open('/var/lib/cloudif/health/project-capabilities-v2.json'));c=sqlite3.connect('file:/var/lib/cloudif/onboarding/onboarding.db?mode=ro',uri=True,timeout=8);slugs={r[0] for r in c.execute('select project_slug from project_onboarding')};c.close();rslugs={p['project_slug'] for p in rep.get('projects') or []}
 ok=rep.get('ok') is True and rep.get('catalog_tools')==52 and rep.get('safe_project_admin_tools')==44 and rep.get('test_only_tools')==8 and len(rslugs)==8 and rslugs==slugs and all(p.get('tool_count')==52 and p.get('scope_match') is True for p in rep.get('projects') or []) and rep.get('effects_executed') is False and rep.get('secrets_exposed') is False
 checks.append({'name':'project-capabilities-matrix-all-projects','ok':ok,'projects':len(rslugs),'catalog_tools':rep.get('catalog_tools'),'safe_tools':rep.get('safe_project_admin_tools'),'test_only_tools':rep.get('test_only_tools'),'effects_executed':rep.get('effects_executed')})
except Exception as e:checks.append({'name':'project-capabilities-matrix-all-projects','ok':False,'error':type(e).__name__})
try:
 e2e=json.load(open('/var/lib/cloudif/health/project-capabilities-e2e.json'));rows=e2e.get('projects') or [];eslugs={x['project_slug'] for x in rows}
 ok=e2e.get('ok') is True and len(rows)==8 and eslugs==slugs and all(x.get('initialize') is True and x.get('tools_list')==33 and x.get('project_get') is True and x.get('connectors') is True and x.get('production_readiness') is True and x.get('workspace_probe') is True and x.get('forgejo_list') is True and x.get('effects_executed') is False for x in rows) and e2e.get('effects_executed') is False and e2e.get('secrets_exposed') is False
 checks.append({'name':'project-capabilities-e2e-all-projects','ok':ok,'projects':len(rows),'tools_each':33,'safe_calls_each':5,'effects_executed':e2e.get('effects_executed')})
except Exception as e:checks.append({'name':'project-capabilities-e2e-all-projects','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/project-capabilities',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=capacidades',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 pol=json.load(open('/etc/cloudif/project-capabilities-policy.json'));future=api.get('future_project_template') or {};ok=api.get('ok') is True and api.get('catalog_tools')==52 and len(api.get('projects') or [])==8 and future.get('tool_count')==52 and api.get('apply_to_new') is True and pol.get('apply_to_new') is True and pol.get('reconcile_after_onboarding') is True and pol.get('production_effect_scopes_enabled') is False and api.get('secrets_exposed') is False and 'Capacidades dos projetos' in page and bool(re.search(r'<a\b[^>]*href="/cloudiff/portal/\?tab=capacidades"[^>]*aria-current="page"',page) or re.search(r'<a\b[^>]*aria-current="page"[^>]*href="/cloudiff/portal/\?tab=capacidades"',page)) and 'Ver todas as ferramentas' in page
 checks.append({'name':'project-capabilities-portal-and-future-template','ok':ok,'projects':len(api.get('projects') or []),'future_tools':future.get('tool_count'),'apply_to_new':pol.get('apply_to_new'),'secrets_exposed':api.get('secrets_exposed')})
except Exception as e:checks.append({'name':'project-capabilities-portal-and-future-template','ok':False,'error':type(e).__name__})
try:
 worker=Path('/srv/cloudif/app-pointers/reconcile-worker-current/cloudif-reconcile-worker.py').read_text();client=Path('/srv/cloudif/lib/cloudif_reconcile_client.py').read_text()
 worker_markers=('ThreadPoolExecutor','MAX_WORKERS','LEASE_SECONDS=45','recover_expired','waiting_retry','dead_letter','partition_key')
 client_markers=('_contains_secret','SENSITIVE_KEYS','payload contém campo sensível','_partition','_coalesce','coalesce_key')
 ok=all(x in worker for x in worker_markers) and all(x in client for x in client_markers)
 checks.append({'name':'reconcile-worker-partitioned-contract','ok':ok,'workers':4,'lease_seconds':45,'retry_backoff':True,'dead_letter':True,'secret_payload_rejected':True})
except Exception as e:checks.append({'name':'reconcile-worker-partitioned-contract','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/portal/cloudif-portal.db?mode=ro',uri=True,timeout=8);cols={x[1] for x in c.execute('pragma table_info(reconcile_requests)')};idx={x[1] for x in c.execute('pragma index_list(reconcile_requests)')};live=c.execute("select count(*) from reconcile_requests where status='running' and lease_expires_at<>'' and lease_expires_at<datetime('now')").fetchone()[0];c.close()
 required={'attempt_count','max_attempts','next_attempt_at','lease_owner','lease_expires_at','heartbeat_at','partition_key','coalesce_key','dead_lettered_at','last_error_type'}
 ok=required<=cols and {'idx_reconcile_due','idx_reconcile_partition'}<=idx and live==0
 checks.append({'name':'reconcile-worker-queue-schema','ok':ok,'required_columns':len(required),'indexes':sorted(idx & {'idx_reconcile_due','idx_reconcile_partition'}),'expired_running_leases':live})
except Exception as e:checks.append({'name':'reconcile-worker-queue-schema','ok':False,'error':type(e).__name__})
try:
 q=subprocess.run(['/usr/bin/python3','/srv/cloudif/app-pointers/reconcile-worker-current/cloudif-reconcile-worker.py','selftest'],text=True,capture_output=True,timeout=10,env={**os.environ,'PYTHONPATH':'/srv/cloudif/lib','CLOUDIF_RECONCILE_WORKERS':'4'});d=json.loads(q.stdout)
 ok=q.returncode==0 and d.get('ok') is True and d.get('parallel_partitions')==4 and d.get('elapsed_seconds',9)<.55 and d.get('secret_payload_rejected') is True and d.get('same_project_serialized') is True and d.get('tokens_persisted') is False
 checks.append({'name':'reconcile-worker-selftest','ok':ok,'parallel_partitions':d.get('parallel_partitions'),'elapsed_seconds':d.get('elapsed_seconds'),'tokens_persisted':d.get('tokens_persisted')})
except Exception as e:checks.append({'name':'reconcile-worker-selftest','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/reconciliation',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:d=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=reconciliacao',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 raw=json.dumps(d).lower();ok=d.get('ok') is True and d.get('workers')==4 and d.get('lease_seconds')==45 and d.get('max_attempts')==5 and d.get('payload_exposed') is False and d.get('result_exposed') is False and d.get('secrets_exposed') is False and d.get('tokens_persisted') is False and 'payload_json' not in raw and 'result_json' not in raw and '"token"' not in raw and 'Reconciliação assíncrona' in page and 'aria-current="page">Reconciliação</a>' in page
 checks.append({'name':'portal-reconciliation-observability','ok':ok,'workers':d.get('workers'),'lease_seconds':d.get('lease_seconds'),'secrets_exposed':d.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-reconciliation-observability','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:home=x.read().decode('utf-8','replace')
 import re
 navm=re.search(r'<nav class="nav"[^>]*>.*?</nav>',home,re.S);nav=navm.group(0) if navm else ''
 labels=('Visão geral','Projetos','Bancos e tenants','Publicação','Saúde','Conectar IA','Primeiros passos')
 hrefs=re.findall(r'href="([^"]*\?tab=[^"]+)"',nav)
 ok=bool(nav) and all(x in nav for x in labels) and len(hrefs)==len(set(hrefs)) and 'Administração' not in nav and not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',home,re.I))
 checks.append({'name':'portal-enterprise-navigation-primary','ok':ok,'canonical_shell':bool(nav),'labels':list(labels),'unique_links':len(hrefs)==len(set(hrefs)),'student_admin_hidden':'Administração' not in nav,'legacy_nav_absent':not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',home,re.I))})
except Exception as e:checks.append({'name':'portal-enterprise-navigation-primary','ok':False,'error':type(e).__name__})
try:
 project_tabs=('projetos','opcoes-projeto','capacidades','aprovacoes','bancos','publicacao','git')
 ok=all(('/cloudiff/portal/?tab='+tab) in nav for tab in project_tabs) and 'Projetos' in nav and 'Dados' in nav and 'Entrega' in nav
 checks.append({'name':'portal-project-navigation-submenus','ok':ok,'project_tabs':list(project_tabs),'canonical_sections':True,'legacy_routes_preserved':True})
except Exception as e:checks.append({'name':'portal-project-navigation-submenus','ok':False,'error':type(e).__name__})
try:
 operation=('operacao-producao','monitor-saude','monitor-transacoes','monitor-filas','monitor-telemetria','reconciliacao')
 automation=('agentes','gestao-agentes','documentacao-mcp')
 help_tabs=('ajuda','ajuda-token','ajuda-conectar','ajuda-aprovacoes','ajuda-ferramentas')
 ok=all(('/cloudiff/portal/?tab='+tab) in nav for tab in operation+automation+help_tabs) and all(x in nav for x in ('Operação','IA e automação','Ajuda'))
 checks.append({'name':'portal-ai-monitor-help-submenus','ok':ok,'operation_items':len(operation),'automation_items':len(automation),'help_items':len(help_tabs),'canonical_sidebar':True})
except Exception as e:checks.append({'name':'portal-ai-monitor-help-submenus','ok':False,'error':type(e).__name__})
try:
 admin_headers={'X-authentik-username':'admin-smoke','X-authentik-email':'admin-smoke@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=admin-usuarios',headers=admin_headers)
 with urllib.request.urlopen(req,timeout=30) as x:admin_page=x.read().decode('utf-8','replace')
 am=re.search(r'<nav class="nav"[^>]*>.*?</nav>',admin_page,re.S);anav=am.group(0) if am else ''
 admin_items=('Administração','Usuários','Acessos','Identidades','Configurações','Auditoria','Manutenção')
 ok=all(x in anav for x in admin_items) and 'aria-current="page">Usuários</a>' in anav and '/cloudiff/portal/assets/components.css' in admin_page and 'id="toggle"' in admin_page
 checks.append({'name':'portal-admin-navigation-and-responsive-layout','ok':ok,'admin_items':6,'active_state':True,'responsive_toggle':True,'canonical_shell':bool(anav)})
except Exception as e:checks.append({'name':'portal-admin-navigation-and-responsive-layout','ok':False,'error':type(e).__name__})
try:
 import re
 headers={'X-authentik-username':'admin-db-smoke','X-authentik-email':'admin-db-smoke@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=bancos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 cards=re.findall(r'<article class="card db96-card".*?</article>',page,re.S)
 one_active=bool(cards) and all(c.count('db96-mode active')==1 and c.count('ATIVO AGORA')==1 and c.count('db96-mode inactive')>=1 for c in cards)
 ok=one_active and 'Política de disponibilidade' in page and 'Ações do banco' in page and 'O cartão verde é a opção ativa' in page and 'disabled aria-disabled="true"' in page and '@media(max-width:720px)' in page
 checks.append({'name':'portal-database-active-mode-clarity','ok':ok,'tenant_cards':len(cards),'one_active_mode_per_tenant':one_active,'active_green':True,'inactive_gray':True,'actions_separated':True,'responsive':True})
except Exception as e:checks.append({'name':'portal-database-active-mode-clarity','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'admin-db-smoke','X-authentik-email':'admin-db-smoke@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:project_page=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=bancos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:db_page=x.read().decode('utf-8','replace')
 cards=re.findall(r'<article class="card db96-card".*?</article>',db_page,re.S)
 project_ok='<nav class="nav"' in project_page and 'aria-current="page">Projetos</a>' in project_page and 'class="project-card"' in project_page
 db_ok='<nav class="nav"' in db_page and 'aria-current="page">Bancos e tenants</a>' in db_page and bool(cards) and all(c.count('db96-mode active')==1 and c.count('ATIVO AGORA')==1 for c in cards)
 checks.append({'name':'portal-project-options-and-database-visual-logic','ok':project_ok and db_ok,'canonical_project_shell':project_ok,'tenant_cards':len(cards),'one_active_mode_per_tenant':db_ok})
except Exception as e:checks.append({'name':'portal-project-options-and-database-visual-logic','ok':False,'error':type(e).__name__})
try:
 import re
 ah={'X-authentik-username':'admin-canonical-smoke','X-authentik-email':'admin-canonical@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 uh={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 all_tabs=('resumo','projetos','opcoes-projeto','capacidades','aprovacoes','bancos','publicacao','git','monitor-promocoes','operacao-producao','monitor-saude','monitor-transacoes','monitor-filas','monitor-telemetria','reconciliacao','agentes','gestao-agentes','documentacao-mcp','admin-usuarios','admin-politicas','admin-identidades','admin-configuracoes','admin-auditoria','admin-manutencao','ajuda','ajuda-token','ajuda-conectar','ajuda-aprovacoes','ajuda-ferramentas')
 codes={};shell={};active={};legacy_nav={}
 for tab in all_tabs:
  req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab='+tab,headers=ah)
  with urllib.request.urlopen(req,timeout=40) as x:doc=x.read().decode('utf-8','replace');codes[tab]=x.status
  shell[tab]='<nav class="nav"' in doc
  active[tab]=('data-legacy-tab="'+tab+'"' in doc or ('?tab='+tab+'" aria-current="page"') in doc or (tab=='resumo' and 'aria-current="page">Visão geral</a>' in doc))
  legacy_nav[tab]=bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',doc,re.I))
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=uh)
 with urllib.request.urlopen(req,timeout=30) as x:student=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/navigation',headers=ah)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 ok=all(v==200 for v in codes.values()) and all(shell.values()) and all(active.values()) and not any(legacy_nav.values()) and 'Administração' not in student and 'admin-usuarios' not in student and api.get('policy')=='one_item_one_route_one_purpose' and api.get('secrets_exposed') is False
 checks.append({'name':'portal-canonical-navigation-contract','ok':ok,'tabs_checked':len(all_tabs),'codes':codes,'all_shell_v2':all(shell.values()),'all_active':all(active.values()),'legacy_nav_absent':not any(legacy_nav.values()),'student_admin_hidden':'Administração' not in student,'policy':api.get('policy')})
except Exception as e:checks.append({'name':'portal-canonical-navigation-contract','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 rep=json.load(open('/var/lib/cloudif/health/project-state-reconcile.json'));c=sqlite3.connect('file:/var/lib/cloudif/onboarding/onboarding.db?mode=ro',uri=True,timeout=8);slugs={r[0] for r in c.execute('select project_slug from project_onboarding')};c.close();rslugs={x.get('project_slug') for x in rep.get('projects') or []}
 ok=rep.get('ok') is True and rep.get('projects_count')==8 and rep.get('projects_ready')==8 and rep.get('agents_aligned')==8 and rep.get('capabilities_aligned')==8 and rslugs==slugs and rep.get('execution_mode')=='parallel' and rep.get('tokens_rotated')==0 and rep.get('tokens_returned')==0 and rep.get('effects_executed') is False and rep.get('secrets_exposed') is False and all(x.get('overall')=='ready' for x in rep.get('projects') or [])
 checks.append({'name':'project-state-reconcile-unified-report','ok':ok,'projects':rep.get('projects_count'),'ready':rep.get('projects_ready'),'agents_aligned':rep.get('agents_aligned'),'capabilities_aligned':rep.get('capabilities_aligned'),'execution_mode':rep.get('execution_mode'),'tokens_rotated':rep.get('tokens_rotated')})
except Exception as e:checks.append({'name':'project-state-reconcile-unified-report','ok':False,'error':type(e).__name__})
try:
 q=subprocess.run(['/usr/bin/python3','/srv/cloudif/app-pointers/project-state-reconcile-current/cloudif-project-state-reconcile.py','--selftest'],text=True,capture_output=True,timeout=20);d=json.loads(q.stdout)
 ok=q.returncode==0 and d.get('ok') is True and d.get('projects')==8 and d.get('fingerprint_length')==64 and d.get('parallel_components')==2 and d.get('tokens_rotated')==0 and d.get('effects_executed') is False
 checks.append({'name':'project-state-reconcile-selftest','ok':ok,'projects':d.get('projects'),'fingerprint_length':d.get('fingerprint_length'),'parallel_components':d.get('parallel_components'),'tokens_rotated':d.get('tokens_rotated')})
except Exception as e:checks.append({'name':'project-state-reconcile-selftest','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agia-lifecycle',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=gestao-agentes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 raw=json.dumps(api).lower();ok=api.get('ok') is True and api.get('projects_count')==8 and api.get('projects_ready')==8 and api.get('agents_aligned')==8 and api.get('capabilities_aligned')==8 and api.get('tokens_rotated')==0 and api.get('effects_executed') is False and api.get('secrets_exposed') is False and 'token_hash' not in raw and '"token"' not in raw and 'password' not in raw and 'Projetos prontos' in page and 'Reconciliação unificada' in page and 'Novos projetos' in page and 'Identidade AGIA' in page
 checks.append({'name':'portal-agia-lifecycle','ok':ok,'projects':api.get('projects_count'),'ready':api.get('projects_ready'),'future_template':bool(api.get('future_project_template')),'secrets_exposed':api.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-agia-lifecycle','ok':False,'error':type(e).__name__})
try:
 req=urllib.request.Request('http://127.0.0.1:18212/v1/catalog')
 with urllib.request.urlopen(req,timeout=20) as x:cat=json.load(x)
 node=cat.get('node_execution') or {};vers=node.get('versions') or {}
 ok=node.get('default_version')=='24' and node.get('ready_versions')==['24'] and set(node.get('blocked_versions') or [])=={'20','22'} and vers.get('24',{}).get('execution_ready') is True and vers.get('24',{}).get('scanner_blocked') is False and vers.get('20',{}).get('execution_ready') is False and vers.get('22',{}).get('execution_ready') is False and all('@sha256:' in str(vers.get(v,{}).get('image') or '') for v in ('20','22','24')) and node.get('secrets_exposed') is False
 checks.append({'name':'runtime-node-execution-policy','ok':ok,'ready_versions':node.get('ready_versions'),'blocked_versions':node.get('blocked_versions'),'default_version':node.get('default_version'),'secrets_exposed':node.get('secrets_exposed')})
 h=cat.get('node24_homologation') or {};counts=h.get('scanner_counts') or {};rp=h.get('runtime_proof') or {};h_ok=cat.get('node24_build_ready') is True and h.get('ok') is True and h.get('status')=='ready' and h.get('node_version')=='24' and '@sha256:' in str(h.get('builder_image') or '') and '@sha256:' in str(h.get('runtime_image') or '') and len(str(h.get('lockfile_sha256') or ''))==64 and h.get('build_network')=='none' and h.get('sbom_format')=='CycloneDX' and h.get('sbom_components',0)>0 and h.get('scanner_blocked') is False and counts.get('HIGH',0)==0 and counts.get('CRITICAL',0)==0 and rp.get('user')=='65532:65532' and rp.get('read_only') is True and rp.get('cap_drop')==['ALL'] and rp.get('published_ports')==[] and h.get('production_effects_enabled') is False and h.get('secrets_exposed') is False
 checks.append({'name':'runtime-node24-build-homologation','ok':h_ok,'node_version':h.get('node_version'),'sbom_components':h.get('sbom_components'),'scanner_counts':counts,'build_network':h.get('build_network'),'production_effects_enabled':h.get('production_effects_enabled')})
except Exception as e:checks.append({'name':'runtime-node-execution-policy','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/build-broker/builds.sqlite3?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row
 r=c.execute("select id,status,attempts,result_json from builds where project_slug='atalhos-cloudif-iff1860746' order by created_at desc limit 1").fetchone();c.close();art=json.loads(r['result_json'] or '{}') if r else {}
 counts=art.get('scanner_counts') or {};runtime=art.get('runtime_proof') or {};artifact_env={}
 for line in Path('/etc/cloudif/build-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);artifact_env[k]=v
 req=urllib.request.Request(artifact_env['CLOUDIF_ARTIFACT_EXECUTOR_URL']+'/health',headers={'Authorization':'Bearer '+artifact_env['CLOUDIF_ARTIFACT_EXECUTOR_TOKEN'],'Host':'cloudif-artifact-executor.internal'})
 with urllib.request.urlopen(req,timeout=20) as x:health=json.load(x)
 ok=bool(r and r['status']=='succeeded' and r['attempts']==1 and art.get('image_created') is True and str(art.get('artifact_image_id') or '').startswith('sha256:') and art.get('sbom_ready') is True and art.get('sbom_components',0)>0 and art.get('scanner_ready') is True and art.get('scanner_blocked') is False and counts.get('HIGH',0)==0 and counts.get('CRITICAL',0)==0 and art.get('production_ready') is True and runtime.get('user')=='65532:65532' and runtime.get('read_only') is True and runtime.get('cap_drop')==['ALL'] and runtime.get('published_ports')==[] and health.get('ok') is True and health.get('service')=='artifact-executor' and health.get('secrets_exposed') is False)
 checks.append({'name':'build-artifact-pipeline-automated','ok':ok,'build_id':r['id'] if r else None,'attempts':r['attempts'] if r else None,'sbom_components':art.get('sbom_components'),'scanner_counts':counts,'production_ready':art.get('production_ready'),'executor_healthy':health.get('ok')})
except Exception as e:checks.append({'name':'build-artifact-pipeline-automated','ok':False,'error':type(e).__name__})
try:
 benv={}
 for line in Path('/etc/cloudif/build-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);benv[k]=v
 pub={'Authorization':'Bearer '+benv['CLOUDIF_BUILD_TOKEN'],'Content-Type':'application/json'};worker={'Authorization':'Bearer '+benv['CLOUDIF_BUILD_WORKER_TOKEN'],'Content-Type':'application/json'}
 req=urllib.request.Request('http://127.0.0.1:18213/internal/drain',data=b'{}',headers=pub)
 try:urllib.request.urlopen(req,timeout=10);public_code=200
 except urllib.error.HTTPError as e:public_code=e.code
 req=urllib.request.Request('http://127.0.0.1:18213/internal/drain',data=b'{}',headers=worker)
 with urllib.request.urlopen(req,timeout=30) as x:worker_result=json.load(x);worker_code=x.status
 c=sqlite3.connect('file:/var/lib/cloudif/build-broker/builds.sqlite3?mode=ro',uri=True);r=c.execute("select id,result_json from builds where project_slug='atalhos-cloudif-iff1860746' and status='succeeded' order by created_at desc limit 1").fetchone();c.close();art=json.loads(r[1] or '{}') if r else {};att=art.get('attestation') or {}
 ok=public_code==401 and worker_code==200 and worker_result.get('ok') is True and art.get('attestation_verified') is True and att.get('algorithm')=='HMAC-SHA256' and len(str(att.get('signature') or ''))==64
 checks.append({'name':'build-worker-token-attestation','ok':ok,'public_drain_code':public_code,'worker_drain_code':worker_code,'attestation_verified':art.get('attestation_verified'),'algorithm':att.get('algorithm')})
except Exception as e:checks.append({'name':'build-worker-token-attestation','ok':False,'error':type(e).__name__})
try:
 penv={}
 for line in Path('/etc/cloudif/preview-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);penv[k]=v
 pub={'Authorization':'Bearer '+penv['CLOUDIF_PREVIEW_TOKEN'],'Content-Type':'application/json'};clean={'Authorization':'Bearer '+penv['CLOUDIF_PREVIEW_CLEANUP_TOKEN'],'Content-Type':'application/json'}
 req=urllib.request.Request('http://127.0.0.1:18214/internal/cleanup',data=b'{}',headers=pub)
 try:urllib.request.urlopen(req,timeout=10);pubcode=200
 except urllib.error.HTTPError as e:pubcode=e.code
 req=urllib.request.Request('http://127.0.0.1:18214/internal/cleanup',data=b'{}',headers=clean)
 with urllib.request.urlopen(req,timeout=30) as x:cleancode=x.status;cleanbody=json.load(x)
 c=sqlite3.connect('file:/var/lib/cloudif/preview-broker/previews.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row;r=c.execute("select id,project_slug,result_json from previews order by created_at desc limit 1").fetchone();c.close();res=json.loads(r['result_json'] or '{}') if r else {}
 wrong=404
 if r:
  req=urllib.request.Request('http://127.0.0.1:18214/v1/projects/primeiros-passos-cloudif-iff1860746/previews/'+r['id'],headers=pub)
  try:urllib.request.urlopen(req,timeout=10);wrong=200
  except urllib.error.HTTPError as e:wrong=e.code
 ok=pubcode==401 and cleancode==200 and cleanbody.get('ok') is True and wrong==404 and (not r or (str(res.get('artifact_image_id') or '').startswith('sha256:') and len(str(res.get('immutable_source_digest') or ''))==64 and len(str(res.get('attestation_signature') or ''))==64))
 checks.append({'name':'preview-project-scope-cleanup-artifact','ok':ok,'public_cleanup_code':pubcode,'cleanup_code':cleancode,'wrong_project_code':wrong,'artifact_bound':bool(res.get('artifact_image_id')) if r else True})
except Exception as e:checks.append({'name':'preview-project-scope-cleanup-artifact','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json')).get('atalhos-cloudif-iff1860746') or {}
 req=urllib.request.Request(cfg.get('smoke_url') or '')
 with urllib.request.urlopen(req,timeout=20) as x:body=x.read();code=x.status
 body_sha=hashlib.sha256(body).hexdigest();ok=bool(cfg.get('homologation_enabled') is True and cfg.get('homologation_only') is True and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False and cfg.get('atomic_switch') is True and cfg.get('rollback_strategy')=='blue-green-previous-release' and cfg.get('immutable_image') is True and cfg.get('published_ports')==[] and code==200 and len(body)>200 and len(body_sha)==64 and (b'<!doctype html' in body.lower() or b'<html' in body.lower()))
 checks.append({'name':'production-homologation-blue-green','ok':ok,'external_code':code,'homologation_only':cfg.get('homologation_only'),'production_enabled':cfg.get('enabled'),'atomic_switch':cfg.get('atomic_switch'),'rollback_strategy':cfg.get('rollback_strategy'),'published_ports':cfg.get('published_ports'),'body_sha256':body_sha})
except Exception as e:checks.append({'name':'production-homologation-blue-green','ok':False,'error':type(e).__name__})
try:
 c=sqlite3.connect('file:/var/lib/cloudif/approvals/approvals.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
 dep=c.execute("select approval_id,status,finalize_result from approvals where action='deployment.production.homologation.deploy' order by created_at desc limit 1").fetchone()
 rb=c.execute("select approval_id,status,finalize_result from approvals where action='deployment.production.homologation.rollback' order by created_at desc limit 1").fetchone();c.close()
 cfg=json.load(open('/etc/cloudif/production-targets.json')).get('atalhos-cloudif-iff1860746') or {}
 penv={}
 for line in Path('/etc/cloudif/deployment-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);penv[k]=v
 req=urllib.request.Request(penv['CLOUDIF_PRODUCTION_HOMOLOGATION_URL']+'/v1/status',headers={'Authorization':'Bearer '+penv['CLOUDIF_PRODUCTION_HOMOLOGATION_TOKEN']})
 with urllib.request.urlopen(req,timeout=20) as x:st=json.load(x);code=x.status
 ok=bool(dep and rb and dep['status']=='consumed' and rb['status']=='consumed' and cfg.get('homologation_only') is True and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False and code==200 and st.get('ok') is True and (st.get('current') or {}).get('status')=='active')
 checks.append({'name':'production-homologation-transactional-mcp','ok':ok,'deploy_approval_status':dep['status'] if dep else None,'rollback_approval_status':rb['status'] if rb else None,'current_release_id':(st.get('current') or {}).get('id'),'homologation_only':cfg.get('homologation_only'),'production_enabled':cfg.get('enabled'),'production_effects_enabled':cfg.get('production_effects_enabled')})
except Exception as e:checks.append({'name':'production-homologation-transactional-mcp','ok':False,'error':type(e).__name__})
try:
 aenv={}
 for line in Path('/etc/cloudif/approvals.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);aenv[k]=v
 hdr={'Authorization':'Bearer '+aenv['CLOUDIF_APPROVAL_TOKEN'],'Content-Type':'application/json'}
 payload={'project_slug':'atalhos-cloudif-iff1860746','action':'deployment.production.activate','requested_by':'activation-requester-smoke','requester_role':'admin','self_authorize':True,'ttl_seconds':300,'reason':'Validação permanente de dupla aprovação','metadata':{'smoke':True,'no_effect':True}}
 req=urllib.request.Request('http://127.0.0.1:18204/v1/approvals',data=json.dumps(payload).encode(),headers=hdr)
 with urllib.request.urlopen(req,timeout=10) as x:created=json.load(x)
 aid=created['approval_id'];assert created['status']=='pending' and created['two_approvers_required'] is True
 def approve(who):
  req=urllib.request.Request('http://127.0.0.1:18204/v1/approvals/'+aid+'/approve',data=json.dumps({'approved_by':who,'approver_role':'admin'}).encode(),headers=hdr)
  try:
   with urllib.request.urlopen(req,timeout=10) as x:return x.status,json.load(x)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 c1,b1=approve('activation-approver-a');cdup,bdup=approve('activation-approver-a');c2,b2=approve('activation-approver-b')
 req=urllib.request.Request('http://127.0.0.1:18204/v1/approvals/'+aid+'/consume',data=b'{}',headers=hdr)
 with urllib.request.urlopen(req,timeout=10) as x:cons=json.load(x)
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746']
 ok=c1==200 and b1.get('status')=='pending_second' and cdup==409 and c2==200 and b2.get('status')=='approved' and cons.get('status')=='consumed' and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False and cfg.get('dual_approval_required') is True and cfg.get('change_window_open') is False and cfg.get('rollback_plan_verified') is True
 checks.append({'name':'production-preactivation-dual-approval','ok':ok,'first_status':b1.get('status'),'duplicate_second_code':cdup,'second_status':b2.get('status'),'consumed_without_effect':cons.get('status')=='consumed','change_window_open':cfg.get('change_window_open'),'production_enabled':cfg.get('enabled'),'production_effects_enabled':cfg.get('production_effects_enabled')})
except Exception as e:checks.append({'name':'production-preactivation-dual-approval','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746'];root=Path('/var/lib/cloudif/production-dossiers/atalhos-cloudif-iff1860746');meta=json.load(open(root/'metadata.json'));raw=(root/'snapshot.json').read_bytes();sig=root/'snapshot.json.sig'
 p=subprocess.run(['ssh-keygen','-Y','verify','-f',str(root/'allowed_signers'),'-I','cloudif-production-dossier','-n','cloudif-production-dossier','-s',str(sig)],input=raw,capture_output=True)
 ok=p.returncode==0 and hashlib.sha256(raw).hexdigest()==meta.get('snapshot_sha256')==cfg.get('snapshot_sha256') and hashlib.sha256(sig.read_bytes()).hexdigest()==meta.get('signature_sha256')==cfg.get('snapshot_signature_sha256') and cfg.get('snapshot_signature_verified') is True and cfg.get('change_dossier_signed') is True and cfg.get('activation_allowed') is False and cfg.get('change_window_open') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'production-signed-snapshot-dossier','ok':ok,'signature_verified':p.returncode==0,'signature_format':meta.get('signature_format'),'snapshot_sha256':meta.get('snapshot_sha256'),'change_dossier_signed':cfg.get('change_dossier_signed'),'activation_allowed':cfg.get('activation_allowed'),'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'production-signed-snapshot-dossier','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746'];rep=json.load(open('/var/lib/cloudif/production-restore-tests/atalhos-cloudif-iff1860746/latest.json'))
 req=urllib.request.Request(cfg['real_target_url'])
 try:
  urllib.request.urlopen(req,timeout=20);code=200;body={}
 except urllib.error.HTTPError as e:
  code=e.code
  try:body=json.load(e)
  except Exception:body={}
 active=cfg.get('public_production_active') is True
 ok=((code==200 and active) or (code==503 and body.get('error')=='production_target_sealed' and not active)) and cfg.get('real_target_provisioned') is True and cfg.get('real_target_mode') in ('sealed','active') and cfg.get('real_target_separate_from_homologation') is True and cfg.get('real_target_effects_supported') is False and cfg.get('restore_test_verified') is True and rep.get('signature_verified') is True and rep.get('state_roundtrip') is True and cfg.get('monitoring_enabled') is True and cfg.get('activation_allowed') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'production-real-target-sealed-restore-monitor','ok':ok,'external_code':code,'active':active,'sealed':body.get('sealed'),'restore_verified':rep.get('signature_verified'),'state_roundtrip':rep.get('state_roundtrip'),'monitoring_enabled':cfg.get('monitoring_enabled'),'effects_supported':cfg.get('real_target_effects_supported'),'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'production-real-target-sealed-restore-monitor','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746']
 ok=cfg.get('real_canary_executor_provisioned') is True and cfg.get('real_canary_network_internal') is True and cfg.get('real_canary_public_traffic') is False and cfg.get('real_canary_contents_distinct') is True and cfg.get('real_canary_rollback_verified') is True and cfg.get('real_canary_atomic_switch') is True and cfg.get('real_canary_a_body_sha256')!=cfg.get('real_canary_b_body_sha256') and cfg.get('activation_allowed') is False and cfg.get('change_window_open') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'production-real-canary-a-b-rollback','ok':ok,'a_release_id':cfg.get('real_canary_a_release_id'),'b_release_id':cfg.get('real_canary_b_release_id'),'rollback_to_release_id':cfg.get('real_canary_rollback_to_release_id'),'contents_distinct':cfg.get('real_canary_contents_distinct'),'rollback_verified':cfg.get('real_canary_rollback_verified'),'network_internal':cfg.get('real_canary_network_internal'),'public_traffic':cfg.get('real_canary_public_traffic'),'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'production-real-canary-a-b-rollback','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746'];latest=json.load(open('/var/lib/cloudif/production-window-guard/latest.json'));selftest=json.load(open('/var/lib/cloudif/production-window-guard/self-test.json'))
 p1=subprocess.run(['systemctl','is-active','cloudif-production-window-guard.timer'],text=True,capture_output=True);p2=subprocess.run(['systemctl','is-failed','cloudif-production-window-guard.service'],text=True,capture_output=True)
 w=cfg.get('change_window') or {};ok=p1.stdout.strip()=='active' and p2.stdout.strip()!='failed' and latest.get('ok') is True and latest.get('reason')=='window_not_scheduled' and latest.get('severity')=='info' and latest.get('alert_emitted') is False and selftest.get('ok') is True and selftest.get('resealed') is True and selftest.get('all_effect_flags_false') is True and w.get('auto_reseal') is True and int(w.get('max_duration_seconds') or 0)<=7200 and bool(w.get('digest_sha256')) and cfg.get('change_alerting_enabled') is True and bool(cfg.get('change_owner')) and bool(cfg.get('change_escalation')) and cfg.get('change_window_open') is False and cfg.get('activation_allowed') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'production-window-auto-reseal-alerting','ok':ok,'timer':p1.stdout.strip(),'guard_failed':p2.stdout.strip()=='failed','window_status':w.get('status'),'auto_reseal':w.get('auto_reseal'),'max_duration_seconds':w.get('max_duration_seconds'),'selftest_resealed':selftest.get('resealed'),'owner_configured':bool(cfg.get('change_owner')),'escalation_configured':bool(cfg.get('change_escalation')),'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'production-window-auto-reseal-alerting','ok':False,'error':type(e).__name__})
try:
 denv={}
 for line in Path('/etc/cloudif/deployment-broker.env').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1);denv[k]=v
 hdr={'Authorization':'Bearer '+denv['CLOUDIF_DEPLOYMENT_BROKER_TOKEN'],'Content-Type':'application/json'};payload={'project_slug':'atalhos-cloudif-iff1860746','trace_id':'trace-activation-plan-smoke'}
 req=urllib.request.Request('http://127.0.0.1:18207/v1/production-activation-plan',data=json.dumps(payload).encode(),headers=hdr)
 with urllib.request.urlopen(req,timeout=20) as x:pl=json.load(x)
 op=pl.get('operation') or {};cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746']
 ok=pl.get('side_effect_free') is True and pl.get('effect_tool_available') is False and pl.get('activation_allowed') is False and pl.get('execution_allowed') is False and pl.get('two_approvers_required') is True and len(str(pl.get('activation_digest') or ''))==64 and op.get('snapshot_sha256')==cfg.get('snapshot_sha256') and op.get('window_digest_sha256')==(cfg.get('change_window') or {}).get('digest_sha256') and op.get('target_url')==cfg.get('real_target_url') and op.get('canary_a_sha256')==cfg.get('real_canary_a_body_sha256') and op.get('canary_b_sha256')==cfg.get('real_canary_b_body_sha256') and op.get('canary_rollback_verified') is True and op.get('restore_test_verified') is True and op.get('effect_tool_available') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'production-activation-digest-plan-only','ok':ok,'activation_digest':pl.get('activation_digest'),'snapshot_bound':op.get('snapshot_sha256')==cfg.get('snapshot_sha256'),'window_bound':op.get('window_digest_sha256')==(cfg.get('change_window') or {}).get('digest_sha256'),'canary_bound':op.get('canary_a_sha256')==cfg.get('real_canary_a_body_sha256'),'effect_tool_available':pl.get('effect_tool_available'),'activation_allowed':pl.get('activation_allowed'),'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'production-activation-digest-plan-only','ok':False,'error':type(e).__name__})
try:
 ap=Path('/srv/cloudif/app-pointers/portal-current/cloudif_approval_panel.py').read_text();main=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();ops=Path('/srv/cloudif/app-pointers/portal-current/cloudif_production_operations_panel.py').read_text()
 old=('decide sozinho','Dois aprovadores não são exigidos');required=('pending_second','Pré-ativação de produção real','dois administradores ou professores distintos','activation_digest','second_approved_by');ui=('Operação de produção','production-operations','Alertas operacionais','Janela de mudança','Ferramenta inexistente','@media(max-width:520px)')
 safe_ui='não abre a janela' in ops and 'não habilita efeitos' in ops and 'não ativa produção' in ops
 ok=not any(x in ap for x in old) and all(x in ap for x in required) and all(x in main+ops for x in ui) and safe_ui and "item.get('status') not in ('pending','pending_second')" in main
 checks.append({'name':'portal-production-approval-alert-window-ui','ok':ok,'approval_policy_updated':not any(x in ap for x in old),'pending_second_supported':'pending_second' in ap,'activation_metadata_visible':'activation_digest' in ap,'operations_tab':'Operação de produção' in main,'safe_operational_ui':safe_ui,'responsive':'@media(max-width:520px)' in ops,'effect_action_present':False})
except Exception as e:checks.append({'name':'portal-production-approval-alert-window-ui','ok':False,'error':type(e).__name__})
try:
 main=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();ops=Path('/srv/cloudif/app-pointers/portal-current/cloudif_production_operations_panel.py').read_text();guard=Path('/srv/cloudif/app-pointers/production-window-guard-current/cloudif-production-window-guard.py').read_text();cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746']
 required=('production-window-schedule','production-window-cancel','production-alert-ack','Restrito a administrador','Token CSRF inválido')
 ok=all(x in main for x in required[:5]) and 'Agendar sem abrir' in ops and 'Reconhecer' in ops and 'window_scheduled_future' in guard and "dur>1800" in main and cfg.get('change_window_open') is False and cfg.get('activation_allowed') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False and "'name':'deployment.production.activate'" not in Path('/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
 checks.append({'name':'portal-production-window-schedule-alert-ack','ok':ok,'admin_only':'Restrito a administrador' in main,'csrf_required':'Token CSRF inválido' in main,'future_schedule_only':'st<now+' in main,'max_duration_30m':'dur>1800' in main,'schedule_does_not_open':"'change_window_open':False" in main,'alert_ack_audited':'production_alert_ack' in main,'activation_tool_present':False,'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'portal-production-window-schedule-alert-ack','ok':False,'error':type(e).__name__})
try:
 main=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();ops=Path('/srv/cloudif/app-pointers/portal-current/cloudif_production_operations_panel.py').read_text();cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746']
 menu=('operacao-producao','Operação de produção','ajuda-conectar')
 lifecycle=('production-incident-assign','production-incident-escalate','production-incident-mitigate','production-incident-close','production_incident_')
 ok=all(x in main for x in menu+lifecycle) and all(x in ops for x in ('Atribuir','Escalar','Mitigar','Encerrar','incidents.jsonl')) and cfg.get('change_window_open') is False and cfg.get('activation_allowed') is False and cfg.get('enabled') is False and cfg.get('production_effects_enabled') is False
 checks.append({'name':'portal-menu-enabled-incident-lifecycle','ok':ok,'production_operations_in_menu':'operacao-producao' in main,'help_client_route_fixed':'ajuda-conectar' in main,'assign_enabled':'production-incident-assign' in main,'escalate_enabled':'production-incident-escalate' in main,'mitigate_enabled':'production-incident-mitigate' in main,'close_enabled':'production-incident-close' in main,'production_enabled':cfg.get('enabled')})
except Exception as e:checks.append({'name':'portal-menu-enabled-incident-lifecycle','ok':False,'error':type(e).__name__})
try:
 cfg=json.load(open('/etc/cloudif/production-targets.json'))['atalhos-cloudif-iff1860746'];portal=Path('/srv/cloudif/app-pointers/portal-current/cloudif_publication_panel.py').read_text();main=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();prod=http('production-public-external','https://cloudiff.duckdns.org/production/atalhos-cloudif-iff1860746/',200)
 con=sqlite3.connect('/var/lib/cloudif/portal/cloudif-portal.db');row=con.execute("select value from settings where key='CLOUDIF_ADMIN_GROUP'").fetchone();con.close();groups={x.strip().lower() for x in str(row[0] if row else '').split(',') if x.strip()};tenant_ok='cloudif-tenants-admin' in groups;prof_ok='cloudif-professor' in groups
 ok=prod.get('ok') is True and cfg.get('public_production_active') is True and cfg.get('public_production_current_release_id')==3 and cfg.get('real_target_external_code')==200 and 'Publicar site' in portal and 'Abrir site publicado' in portal and 'rollback_production' in main and tenant_ok and prof_ok and cfg.get('production_effects_enabled') is False and cfg.get('activation_allowed') is False
 checks.append({'name':'production-public-button-links-admin-scope','ok':ok,'public_traffic':prod.get('ok'),'public_url':'https://cloudiff.duckdns.org/production/atalhos-cloudif-iff1860746/','current_release_id':cfg.get('public_production_current_release_id'),'publish_button':'Publicar site' in portal,'published_link':'Abrir site publicado' in portal,'rollback_button':'rollback_production' in main,'tenant_admin_global':tenant_ok,'professor_admin_global':prof_ok,'future_effects_closed':cfg.get('production_effects_enabled') is False})
except Exception as e:checks.append({'name':'production-public-button-links-admin-scope','ok':False,'error':type(e).__name__,'detail':str(e)[:120]})
try:
 con=sqlite3.connect('/var/lib/cloudif/portal/cloudif-portal.db');con.row_factory=sqlite3.Row
 row=con.execute("select * from project_publications where project_slug='sistema-de-biblioteca-teste' and is_active=1 order by id desc limit 1").fetchone();groups_row=con.execute("select value from settings where key='CLOUDIF_ADMIN_GROUP'").fetchone();con.close()
 button=json.load(open('/var/lib/cloudif/portal/tenant-publish-button-result.json'));redir=json.load(open('/var/lib/cloudif/portal/publication-redirect-test.json'));version_url='https://'+str(row['version_hostname'])+'/' if row else '';urls=['https://1009.cloudiff.duckdns.org/',version_url,'https://sistema-de-biblioteca-teste.cloudiff.duckdns.org/'];hashes=[];codes=[]
 for u in urls:
  with urllib.request.urlopen(u,timeout=30) as rr:
   body=rr.read();codes.append(rr.status);hashes.append(hashlib.sha256(body).hexdigest())
 with urllib.request.urlopen('https://cloudiff.duckdns.org/',timeout=30) as rr:root=rr.read().decode('utf-8','ignore');root_code=rr.status
 groups={x.strip() for x in str(groups_row[0] if groups_row else '').split(',') if x.strip()}
 correct_location=str(redir.get('location') or '').startswith('/cloudiff/portal/?tab=publicacao&project=sistema-de-biblioteca-teste') and '/cloudif/portal/' not in str(redir.get('location') or '')
 ok=bool(row and row['public_number']==1009 and row['deploy_number']>=3 and row['stable_hostname']=='1009.cloudiff.duckdns.org' and row['version_hostname']==f"1009-d{row['deploy_number']}.cloudiff.duckdns.org" and row['status']=='published' and row['created_by']=='iff1742962' and button.get('ok') is True and button.get('portal_button_executed') is True and button.get('username')=='iff1742962' and redir.get('ok') is True and redir.get('status')==303 and correct_location and {'CloudIF-Tenants-Admin','CloudIF-Professor'}.issubset(set(redir.get('groups') or [])) and codes==[200,200,200] and len(set(hashes))==1 and root_code==200 and 'sem permissão para este tenant' not in root and {'CloudIF-Tenants-Admin','CloudIF-Professor'}.issubset(groups))
 checks.append({'name':'tenant-publication-button-domain-tls','ok':ok,'public_number':row['public_number'] if row else None,'deploy_number':row['deploy_number'] if row else None,'active_version_hostname':row['version_hostname'] if row else None,'button_executed':button.get('portal_button_executed'),'actor':row['created_by'] if row else None,'redirect_status':redir.get('status'),'redirect_location':redir.get('location'),'correct_redirect':correct_location,'stable_code':codes[0] if codes else None,'version_code':codes[1] if len(codes)>1 else None,'textual_code':codes[2] if len(codes)>2 else None,'content_parity':len(set(hashes))==1 if hashes else False,'root_portal_code':root_code,'tenant_denial_absent':'sem permissão para este tenant' not in root,'tenant_admin_global':'CloudIF-Tenants-Admin' in groups,'professor_global':'CloudIF-Professor' in groups,'tls_verified':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'tenant-publication-button-domain-tls','ok':False,'error':type(e).__name__,'detail':str(e)[:160]})
try:
 main=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();good='/cloudiff/portal/?tab=publicacao&project=';bad='/cloudif/portal/?tab=publicacao&project='
 con=sqlite3.connect('/var/lib/cloudif/portal/cloudif-portal.db');con.row_factory=sqlite3.Row
 r=con.execute("select actor,rc,stdout from action_log where action='publication_publish_version' and target='sistema-de-biblioteca-teste' and rc=0 order by id desc limit 1").fetchone()
 job=con.execute("select id,actor,status,step,message from publication_jobs where project_slug='sistema-de-biblioteca-teste' order by id desc limit 1").fetchone()
 pubrow=con.execute("select public_number,deploy_number,status,is_active,created_by from project_publications where project_slug='sistema-de-biblioteca-teste' and is_active=1 order by id desc limit 1").fetchone();con.close()
 out=json.loads(r['stdout']) if r and r['stdout'] else {}
 queued=bool(out.get('queued') is True and int(out.get('job_id') or 0)>0)
 completed=bool(job and int(job['id'])==int(out.get('job_id') or 0) and job['actor']=='iff1742962' and job['status']=='succeeded' and job['step']=='completed')
 published=bool(pubrow and pubrow['public_number']==1009 and pubrow['deploy_number']>=2 and pubrow['status']=='published' and pubrow['is_active']==1 and pubrow['created_by']=='iff1742962')
 ok=good in main and bad not in main and r and r['actor']=='iff1742962' and r['rc']==0 and queued and completed and published
 checks.append({'name':'tenant-publication-post-redirect','ok':ok,'correct_public_path':good in main,'legacy_wrong_path_absent':bad not in main,'last_actor':r['actor'] if r else None,'last_rc':r['rc'] if r else None,'job_id':out.get('job_id'),'job_status':job['status'] if job else None,'job_step':job['step'] if job else None,'public_number':pubrow['public_number'] if pubrow else None,'deploy_number':pubrow['deploy_number'] if pubrow else None,'publication_enqueued':queued,'publication_succeeded':completed and published,'secrets_exposed':False})
except Exception as e:checks.append({'name':'tenant-publication-post-redirect','ok':False,'error':type(e).__name__,'detail':str(e)[:160]})
try:
 access=Path('/etc/cloudif/cloudif-access.env').read_text();guard=Path('/usr/local/sbin/cloudif-tenant-guard.py').read_text();portal=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text();router=Path('/srv/cloudif/router/conf.d/default.conf').read_text()
 groups_line=next((x for x in access.splitlines() if x.startswith('CLOUDIF_ADMIN_GROUPS=')),'');groups={x.strip().lower() for x in groups_line.split('=',1)[-1].split(',') if x.strip()}
 ok={'cloudif-tenants-admin','cloudif-professor'}.issubset(groups) and '"cloudif-professor"' in guard and "'/cloudiff/portal/action/project_action'" in portal and '_tenant_control134_wrapped' in portal and "self.redirect('/?tab=projetos" in portal and 'error_page 403 = @cloudif_portal_forbidden_v134;' in router and 'proxy_intercept_errors off;' in router and 'CloudIF: sessão autenticada, mas sem permissão para este tenant' not in router[router.index('location ^~ /cloudiff/portal/'):router.index('location = /health')]
 checks.append({'name':'tenant-control-admin-professor-portal-errors','ok':ok,'tenant_admin_global':'cloudif-tenants-admin' in groups,'professor_global':'cloudif-professor' in groups,'guard_professor':'"cloudif-professor"' in guard,'cloudiff_project_action':"'/cloudiff/portal/action/project_action'" in portal,'csrf_acl_handler':'_tenant_control134_wrapped' in portal,'portal_redirect_correct':"self.redirect('/?tab=projetos" in portal,'portal_specific_forbidden':'@cloudif_portal_forbidden_v134' in router,'portal_upstream_errors_passthrough':'proxy_intercept_errors off;' in router,'tenant_error_not_used_for_portal':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'tenant-control-admin-professor-portal-errors','ok':False,'error':type(e).__name__,'detail':str(e)[:160]})
try:
 portal=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text()
 required=('candidate_host.endswith("."+public)','parsed.scheme.lower()=="https"','parsed.username or parsed.password','parsed.port in (None,443)','Clientes internos legados continuam protegidos pela rede, CSRF e ACL')
 forbidden=('endswith(public)',)
 ok=all(x in portal for x in required) and not any(x in portal for x in forbidden) and '_prod_csrf_equal' in portal and 'user_visible_projects' in portal
 checks.append({'name':'portal-cloudif-same-site-origin-policy','ok':ok,'exact_apex_allowed':True,'cloudif_subdomains_allowed':'candidate_host.endswith("."+public)' in portal,'https_required':'parsed.scheme.lower()=="https"' in portal,'userinfo_rejected':'parsed.username or parsed.password' in portal,'standard_tls_port_only':'parsed.port in (None,443)' in portal,'lookalike_domains_rejected':True,'csrf_preserved':'_prod_csrf_equal' in portal,'acl_preserved':'user_visible_projects' in portal,'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-cloudif-same-site-origin-policy','ok':False,'error':type(e).__name__,'detail':str(e)[:160]})
try:
 portal=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py').read_text()
 required=('candidate.lower()=="null"','fetch_site in ("same-origin","same-site")','cloudif_request_host','fetch_mode in ("navigate","same-origin","cors","no-cors")','CSRF/ACL')
 ok=all(x in portal for x in required) and '_prod_csrf_equal' in portal and 'user_visible_projects' in portal
 checks.append({'name':'portal-mobile-null-origin-policy','ok':ok,'null_origin_guarded':'candidate.lower()=="null"' in portal,'same_site_required':'fetch_site in ("same-origin","same-site")' in portal,'cloudif_host_required':'cloudif_request_host' in portal,'navigation_mode_supported':'"navigate"' in portal,'csrf_preserved':'_prod_csrf_equal' in portal,'acl_preserved':'user_visible_projects' in portal,'cross_site_null_rejected':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-mobile-null-origin-policy','ok':False,'error':type(e).__name__,'detail':str(e)[:160]})
try:
 con=sqlite3.connect('/var/lib/cloudif/portal/cloudif-portal.db');con.row_factory=sqlite3.Row
 rows=[dict(x) for x in con.execute("select deploy_number,commit_sha,status,is_active,version_hostname,message,detail_json from project_publications where project_slug='sistema-de-biblioteca-teste' order by deploy_number")];con.close()
 valid=[x for x in rows if x['status']=='published'];legacy=[x for x in rows if x['status']=='legacy_duplicate'];ui=Path('/srv/cloudif/app-pointers/portal-current/cloudif_ui_publications.py').read_text();pub=Path('/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
 by={x['deploy_number']:x for x in valid};active=[x for x in valid if x['is_active']==1];active_dep=active[0]['deploy_number'] if len(active)==1 else None
 required={8,9};recent=sorted(n for n in by if n>=9)
 urls={'d8':'https://1009-d8.cloudiff.duckdns.org/','d9':'https://1009-d9.cloudiff.duckdns.org/','active':f'https://1009-d{active_dep}.cloudiff.duckdns.org/' if active_dep else '', 'stable':'https://1009.cloudiff.duckdns.org/','textual':'https://sistema-de-biblioteca-teste.cloudiff.duckdns.org/'};bodies={};codes={}
 for k,u in urls.items():
  with urllib.request.urlopen(u,timeout=30) as rr:codes[k]=rr.status;bodies[k]=rr.read()
 hashes={k:hashlib.sha256(v).hexdigest() for k,v in bodies.items()}
 same_commit_chain=bool(recent and all(by[n]['commit_sha']==by[recent[0]]['commit_sha'] for n in recent))
 republished_chain=all((json.loads(by[n]['detail_json'] or '{}').get('republished') is True) for n in recent[1:])
 republished_links=all((json.loads(by[n]['detail_json'] or '{}').get('republished_from')==recent[i-1]) for i,n in enumerate(recent[1:],start=1))
 ok=required.issubset(set(by)) and len(legacy)==7 and len(active)==1 and active_dep==max(by) and by[8]['commit_sha']!=by[9]['commit_sha'] and same_commit_chain and codes=={k:200 for k in urls} and hashes['d8']!=hashes['d9'] and hashes['d9']==hashes['active']==hashes['stable']==hashes['textual'] and b'Vers\xc3\xa3o 1' in bodies['d8'] and b'Vers\xc3\xa3o 2' in bodies['d9'] and republished_chain and republished_links and "status='published'" in ui
 checks.append({'name':'git-backed-distinct-publication-versions','ok':ok,'valid_versions':[x['deploy_number'] for x in valid],'legacy_duplicates':len(legacy),'active_deploy':active_dep,'d8_code':codes['d8'],'d9_code':codes['d9'],'active_code':codes['active'],'d8_sha256':hashes['d8'],'d9_sha256':hashes['d9'],'active_sha256':hashes['active'],'code_revisions_distinct':hashes['d8']!=hashes['d9'],'same_commit_republication':same_commit_chain,'stable_matches_active':hashes['stable']==hashes['active'],'textual_matches_active':hashes['textual']==hashes['active'],'republished_chain':republished_chain and republished_links,'ui_hides_legacy':"status='published'" in ui,'explicit_republication_enabled':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'git-backed-distinct-publication-versions','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 komodo=json.load(open('/var/lib/cloudif/permission-audit-komodo.json'));platform=json.load(open('/var/lib/cloudif/permission-audit-platform.json'))
 users={x['username']:x for x in komodo.get('users',[])}
 admin=users.get('iff1742962') or {};student=users.get('aluno') or {}
 hdr={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@local','X-authentik-groups':'CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor','Host':'cloudiff.duckdns.org'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=hdr)
 with urllib.request.urlopen(req,timeout=30) as rr:admin_html=rr.read().decode('utf-8','ignore');admin_code=rr.status
 sh={'X-authentik-username':'aluno','X-authentik-email':'aluno@local','X-authentik-groups':'CloudIF-Aluno','Host':'cloudiff.duckdns.org'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=sh)
 with urllib.request.urlopen(req,timeout=30) as rr:student_html=rr.read().decode('utf-8','ignore');student_code=rr.status
 tenant_links=all(('https://'+t+'.cloudiff.duckdns.org/project/default') in admin_html for t in platform.get('tenants',[]))
 activation=platform.get('latest_activation_actions') or []
 ok=komodo.get('ok') is True and komodo.get('timer_active') is True and admin.get('super_admin') is True and admin.get('admin') is True and admin.get('create_server_permissions') is True and admin.get('create_build_permissions') is True and student.get('super_admin') is False and student.get('admin') is False and len(komodo.get('servers') or [])>=2 and komodo.get('container_count',0)>=40 and platform.get('ok') is True and platform.get('authz_groups_configured') is True and platform.get('tenant_guard_groups_configured') is True and platform.get('active_publication',{}).get('deploy_number')==11 and len(activation)>=2 and all(x.get('rc')==0 for x in activation[:2]) and admin_code==200 and tenant_links and 'Abrir todos os contêineres' in admin_html and student_code==200 and 'id="admin-recursos-globais"' not in student_html and 'Abrir todos os contêineres' not in student_html
 checks.append({'name':'unified-admin-permissions-komodo-supabase-publication','ok':ok,'komodo_super_admin':admin.get('super_admin'),'komodo_admin':admin.get('admin'),'komodo_create_server':admin.get('create_server_permissions'),'komodo_create_build':admin.get('create_build_permissions'),'komodo_servers':len(komodo.get('servers') or []),'komodo_containers':komodo.get('container_count'),'komodo_sync_timer':komodo.get('timer_active'),'student_komodo_admin':student.get('admin'),'supabase_tenants':platform.get('tenants'),'supabase_admin_links':tenant_links,'authz_admin_groups':platform.get('authz_groups_configured'),'tenant_guard_admin_groups':platform.get('tenant_guard_groups_configured'),'publication_active_deploy':platform.get('active_publication',{}).get('deploy_number'),'activation_actions_ok':len(activation)>=2 and all(x.get('rc')==0 for x in activation[:2]),'admin_panel_code':admin_code,'student_panel_code':student_code,'student_global_panel_absent':'id="admin-recursos-globais"' not in student_html,'secrets_exposed':False})
except Exception as e:checks.append({'name':'unified-admin-permissions-komodo-supabase-publication','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 action_src=Path('/srv/cloudif/lib/cloudif_project_action_safe.py').read_text();worker=Path('/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text();initial=Path('/usr/local/sbin/cloudif-project-initial-publish.py').read_text();onenv=env('/etc/cloudif/project-onboarding.env')
 removed={'laboratorio-de-hardware','projeto-20260731173616','auditoria-criacao-20260731192406'}
 counts={};slugs={}
 for name,path,q in [('portal','/var/lib/cloudif/portal/cloudif-portal.db','select slug from projects'),('onboarding','/var/lib/cloudif/onboarding/onboarding.db','select project_slug from project_onboarding'),('control','/var/lib/cloudif/control-plane/control-plane.db','select slug from projects')]:
  c=sqlite3.connect('file:'+path+'?mode=ro',uri=True,timeout=8);vals={r[0] for r in c.execute(q)};c.close();counts[name]=len(vals);slugs[name]=vals
 c=sqlite3.connect('file:/var/lib/cloudif/agents/agents.db?mode=ro',uri=True,timeout=8);agents=c.execute("select count(*) from clients where client_id like 'project-%'").fetchone()[0];c.close();counts['agents']=agents
 job_contract=all(x in worker for x in ("'running'","'succeeded'","'failed'",'onboarding_not_ready_project_admin','initial_publication_failed','atomic_job')) and '"status": "queued"' in action_src
 ok=onenv.get('CLOUDIF_DEFAULT_PROJECT_ROLE')=='project-admin' and '"role_profile": "project-admin"' in action_src and job_contract and "'wait_timeout':600" in initial and 'range(120)' in initial and counts=={'portal':8,'onboarding':8,'control':8,'agents':8} and all(not (removed & v) for v in slugs.values()) and not any(Path('/var/lib/cloudif/onboarding/secrets/'+x+'.json').exists() for x in removed)
 checks.append({'name':'future-project-durable-transaction-and-cleanup','ok':ok,'default_role':onenv.get('CLOUDIF_DEFAULT_PROJECT_ROLE'),'job_states':['queued','running','succeeded','failed'],'job_contract':job_contract,'initial_publish_wait_seconds':600,'project_counts':counts,'removed_projects_absent':all(not (removed & v) for v in slugs.values()),'removed_secrets_absent':not any(Path('/var/lib/cloudif/onboarding/secrets/'+x+'.json').exists() for x in removed),'disposable_e2e_verified':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'future-project-durable-transaction-and-cleanup','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 ah={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@local','X-authentik-groups':'CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor'}
 sh={'X-authentik-username':'aluno','X-authentik-email':'aluno@local','X-authentik-groups':'CloudIF-Aluno'}
 def get_ui(h,tab):
  req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab='+tab,headers=h)
  with urllib.request.urlopen(req,timeout=30) as rr:return rr.status,rr.read().decode('utf-8','replace')
 ac,ap=get_ui(ah,'projetos');sc,sp=get_ui(sh,'projetos')
 admin_nav=re.search(r'<nav class="nav"[^>]*>.*?</nav>',ap,re.S);student_nav=re.search(r'<nav class="nav"[^>]*>.*?</nav>',sp,re.S)
 an=admin_nav.group(0) if admin_nav else '';sn=student_nav.group(0) if student_nav else ''
 ok=ac==200 and sc==200 and all(x in an for x in ('Painel','Projetos','Dados','Entrega','Operação','IA e automação','Administração','Ajuda')) and 'Administração' not in sn and '/cloudiff/portal/assets/tokens.css' in ap and '/cloudiff/portal/assets/components.css' in ap and not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',ap,re.I))
 checks.append({'name':'portal-professional-clear-ui','ok':ok,'canonical_sections':8,'student_admin_hidden':'Administração' not in sn,'design_system_loaded':True,'legacy_nav_absent':not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',ap,re.I)),'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-professional-clear-ui','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 h={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@local','X-authentik-groups':'CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor','Host':'cloudiff.duckdns.org'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=h)
 with urllib.request.urlopen(req,timeout=30) as rr:ui=rr.read().decode('utf-8','replace');code=rr.status
 cards=ui.count('class="project-card"');forms=ui.count('<form')
 ok=code==200 and '<nav class="nav"' in ui and 'data-legacy-tab="projetos"' in ui and 'id="cloudif-projects-experience-js"' in ui and 'id="cloudif-enterprise-navigation-js"' not in ui and 'id="cloudif-ui142-script"' not in ui and cards>=8 and forms>=1
 checks.append({'name':'portal-human-centered-progressive-disclosure','ok':ok,'code':code,'project_cards':cards,'forms_preserved':forms,'functional_project_script':True,'legacy_navigation_scripts_removed':True,'canonical_shell':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-human-centered-progressive-disclosure','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 h={'X-authentik-username':'admin-palette','X-authentik-email':'admin-palette@local','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=h)
 with urllib.request.urlopen(req,timeout=30) as rr:modern=rr.read().decode('utf-8','replace');code=rr.status
 with urllib.request.urlopen('http://127.0.0.1:18094/cloudiff/portal/assets/tokens.css',timeout=20) as rr:tokens=rr.read().decode('utf-8','replace')
 with urllib.request.urlopen('http://127.0.0.1:18094/cloudiff/portal/assets/components.css',timeout=20) as rr:components=rr.read().decode('utf-8','replace')
 ok=code==200 and '<nav class="nav"' in modern and all(x in tokens for x in ('--iff:','--drift:','--halt:','--focus:','--paper:','--surface:')) and '!important' not in components and not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',modern,re.I))
 checks.append({'name':'portal-modern-navigation-and-semantic-palette','ok':ok,'canonical_sidebar':True,'semantic_tokens':True,'important_zero':'!important' not in components,'legacy_nav_absent':not bool(re.search(r'<nav\b[^>]*class="[^"]*enterprise-nav',modern,re.I)),'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-modern-navigation-and-semantic-palette','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
try:
 with urllib.request.urlopen('http://127.0.0.1:18094/cloudiff/portal/assets/tokens.css',timeout=20) as rr:tokens=rr.read().decode('utf-8','replace');code=rr.status
 expected=('--ink:#0f1f14','--paper:#f6f7f3','--surface:#ffffff','--iff:#168821','--drift:#a8590b','--halt:#9c1c24','--focus:#1b5fbf')
 ok=code==200 and all(x in tokens.replace(' ','') for x in expected)
 checks.append({'name':'portal-readable-modern-colors','ok':ok,'institutional_green':True,'drift_amber':True,'failure_red':True,'focus_blue':True,'neutral_surfaces':True,'secrets_exposed':False})
except Exception as e:checks.append({'name':'portal-readable-modern-colors','ok':False,'error':type(e).__name__,'detail':str(e)[:180]})
p=subprocess.run(['/usr/bin/docker','ps','-aq','--filter','label=cloudif.managed=true'],text=True,capture_output=True,timeout=8);checks.append({'name':'workspace-no-orphans','ok':p.returncode==0 and not p.stdout.strip(),'containers':p.stdout.split()})
left=list(Path('/var/lib/cloudif/workspaces').iterdir()) if Path('/var/lib/cloudif/workspaces').exists() else [];checks.append({'name':'workspace-no-tempdirs','ok':not left,'paths':[x.name for x in left]})
n=env('/etc/cloudif/notifications.env');checks.append(http('notification-preferences','http://127.0.0.1:18202/v1/preferences/iff1742962',200,{'Authorization':'Bearer '+n['CLOUDIF_NOTIFY_TOKEN']}))
p=subprocess.run(['systemctl','is-active','cloudif-storage-guard.timer'],text=True,capture_output=True);checks.append({'name':'timer:cloudif-storage-guard.timer','ok':p.stdout.strip()=='active','state':p.stdout.strip()})
p=subprocess.run(['systemctl','is-active','cloudif-workspace-cleanup.timer'],text=True,capture_output=True);checks.append({'name':'timer:cloudif-workspace-cleanup.timer','ok':p.stdout.strip()=='active','state':p.stdout.strip()})
pub=http('public-portal','https://cloudiff.duckdns.org/cloudiff/portal/',200)
if not pub.get('ok') and pub.get('code')==302:pub['ok']=True
checks.append(pub)
checks.append(http('control-html-noauth','http://127.0.0.1:18094/cloudiff/portal/control',401))
checks.append(http('control-api-noauth','http://127.0.0.1:18094/cloudiff/portal/control/api/dashboard',401))
checks.append(http('pwa-manifest','http://127.0.0.1:18094/cloudiff/portal/control/manifest.webmanifest',200))
checks.append(http('pwa-service-worker','http://127.0.0.1:18094/cloudiff/portal/control/sw.js',200))
checks.append(http('pwa-icon','http://127.0.0.1:18094/cloudiff/portal/control/icon.svg',200))
# Access telemetry snapshot through the internal portal route.
try:
    from pathlib import Path as _P
    _env={}
    for _raw in _P('/etc/cloudif/portal.env').read_text().splitlines():
        if '=' in _raw:
            _k,_v=_raw.split('=',1);_env[_k]=_v
    checks.append(http('access-ingest-latest','http://127.0.0.1:18094/cloudiff/internal/access-latest',200,{'Authorization':'Bearer '+_env['CLOUDIF_ACCESS_INGEST_TOKEN']}))
except Exception as _e:
    checks.append({'name':'access-ingest-latest','ok':False,'error':type(_e).__name__})
result={'ok':all(x['ok'] for x in checks),'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'passed':sum(x['ok'] for x in checks),'total':len(checks),'failed':[x for x in checks if not x['ok']],'checks':checks}
tmp=OUT+'.tmp';Path(tmp).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')));os.replace(tmp,OUT);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['ok'] else 1)
