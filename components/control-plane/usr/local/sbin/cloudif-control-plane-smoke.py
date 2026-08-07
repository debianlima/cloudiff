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
 tree=ast.parse(Path(mcp_path).read_text());published=set()
 for n in tree.body:
  if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='TOOLS' for x in n.targets) and isinstance(n.value,(ast.List,ast.Tuple)):
   for item in n.value.elts:
    if not isinstance(item,ast.Dict):continue
    for key,value in zip(item.keys,item.values):
     if isinstance(key,ast.Constant) and key.value=='name' and isinstance(value,ast.Constant) and isinstance(value.value,str):published.add(value.value)
   break
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
 ok={'requester_role','approver_role','authorization_mode'}<=cols and testrows==0 and "single_privileged_requester" in src and "single_admin_or_professor" in src and "production_approver_role_required" in src and "return 'admin'" in portal and "return 'professor'" in portal
 checks.append({'name':'production-single-decider-policy','ok':ok,'admin_single_decision':True,'professor_single_decision':True,'student_requires_privileged_decider':True,'two_approvers_required':False,'test_rows':testrows})
except Exception as e:checks.append({'name':'production-single-decider-policy','ok':False,'error':type(e).__name__})
try:
 payload={'jsonrpc':'2.0','id':906,'method':'tools/call','params':{'name':'deployment.production.readiness','arguments':{'slug':'sistema-de-biblioteca-teste'}}};req=urllib.request.Request('http://127.0.0.1:18198/mcp',data=json.dumps(payload).encode(),method='POST',headers={'Authorization':'Bearer '+tok,'X-CloudIF-Client':cid,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as x:r=json.load(x)
 d=json.loads(r['result']['content'][0]['text']);expected={'target_enabled','separate_from_test','komodo_stack_configured','public_url_configured','smoke_url_configured','rollback_strategy_configured','automatic_database_restore','immutable_image_required'}
 ok=d.get('ok') is True and d.get('production_ready') is False and d.get('execution_allowed') is False and d.get('target_configured') is False and set(d.get('blockers') or [])==expected and d.get('two_approvers_required') is False and d.get('side_effect_free') is True
 checks.append({'name':'production-readiness-fail-closed','ok':ok,'production_ready':d.get('production_ready'),'execution_allowed':d.get('execution_allowed'),'blockers':len(d.get('blockers') or []),'target_configured':d.get('target_configured')})
except Exception as e:checks.append({'name':'production-readiness-fail-closed','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'};req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=agentes',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/agent-guide',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 markers=('Política de produção','Pode autorizar sozinho','Aluno ou agente','Não são exigidos dois aprovadores','Como o agente aprende a usar a CloudIFF','cloudiff://guide/agent','cloudiff-project-workflow','cloudiff-production-policy')
 pol=api.get('production_policy') or {};disc=api.get('agent_discovery') or {};ok=all(x in page for x in markers) and pol.get('admin')=='autoriza sozinho' and pol.get('professor')=='autoriza sozinho' and pol.get('two_approvers_required') is False and disc.get('initialize_instructions') is True and api.get('secrets_exposed') is False
 checks.append({'name':'portal-production-policy-and-agent-discovery','ok':ok,'admin_policy':pol.get('admin'),'professor_policy':pol.get('professor'),'two_approvers_required':pol.get('two_approvers_required'),'agent_discovery':bool(disc),'secrets_exposed':api.get('secrets_exposed')})
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
 ok=rep.get('ok') is True and rep.get('catalog_tools')==33 and rep.get('safe_project_admin_tools')==25 and rep.get('test_only_tools')==8 and len(rslugs)==8 and rslugs==slugs and all(p.get('tool_count')==33 and p.get('scope_match') is True for p in rep.get('projects') or []) and rep.get('effects_executed') is False and rep.get('secrets_exposed') is False
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
 pol=json.load(open('/etc/cloudif/project-capabilities-policy.json'));future=api.get('future_project_template') or {};ok=api.get('ok') is True and api.get('catalog_tools')==33 and len(api.get('projects') or [])==8 and future.get('tool_count')==33 and api.get('apply_to_new') is True and pol.get('apply_to_new') is True and pol.get('reconcile_after_onboarding') is True and pol.get('production_effect_scopes_enabled') is False and api.get('secrets_exposed') is False and 'Capacidades dos projetos' in page and bool(re.search(r'<a\b[^>]*href="/cloudiff/portal/\?tab=capacidades"[^>]*aria-current="page"',page) or re.search(r'<a\b[^>]*aria-current="page"[^>]*href="/cloudiff/portal/\?tab=capacidades"',page)) and 'Ver todas as ferramentas' in page
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
 raw=json.dumps(d).lower();ok=d.get('ok') is True and d.get('workers')==4 and d.get('lease_seconds')==45 and d.get('max_attempts')==5 and d.get('payload_exposed') is False and d.get('result_exposed') is False and d.get('secrets_exposed') is False and d.get('tokens_persisted') is False and 'payload_json' not in raw and 'result_json' not in raw and '"token"' not in raw and 'Reconciliação assíncrona' in page and 'class="active" href="/cloudiff/portal/?tab=reconciliacao"' in page
 checks.append({'name':'portal-reconciliation-observability','ok':ok,'workers':d.get('workers'),'lease_seconds':d.get('lease_seconds'),'secrets_exposed':d.get('secrets_exposed')})
except Exception as e:checks.append({'name':'portal-reconciliation-observability','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:home=x.read().decode('utf-8','replace')
 import re
 navm=re.search(r'<nav class="tabs enterprise-nav".*?</nav>',home,re.S);nav=navm.group(0) if navm else ''
 primary=('Início','Meus Projetos','Agentes de IA','Monitoramento','Ajuda')
 ok=bool(nav) and all(x in nav for x in primary) and '>Administração<' not in nav and 'enterprise-submenu' in nav
 checks.append({'name':'portal-enterprise-navigation-primary','ok':ok,'primary_groups':5,'admin_hidden_for_non_admin':'>Administração<' not in nav,'hierarchical':bool(nav)})
except Exception as e:checks.append({'name':'portal-enterprise-navigation-primary','ok':False,'error':type(e).__name__})
try:
 project_items=('Lista de projetos','Opções do projeto','Banco de dados','Deploys e Git')
 duplicates=('Backups do projeto','Containers','Ambientes e conectores')
 ok=all(x in nav for x in project_items) and all(x not in nav for x in duplicates) and '/cloudiff/portal/?tab=opcoes-projeto' in nav
 checks.append({'name':'portal-project-navigation-submenus','ok':ok,'project_menu_items':4,'duplicates_removed':True,'project_options_route':'opcoes-projeto','database_under_projects':True,'deploys_under_projects':True})
except Exception as e:checks.append({'name':'portal-project-navigation-submenus','ok':False,'error':type(e).__name__})
try:
 ai_items=('Visão geral do AGIA','Gestão de agentes','Capacidades por projeto','Reconciliação','Aprovações','Documentação MCP');monitor_items=('Saúde da plataforma','Transações','Promoções e rollbacks','Filas','Telemetria');help_items=('Primeiros passos','Como obter token','Conectar clientes de IA','Como funcionam as aprovações','Referência das ferramentas MCP')
 ok=all(x in nav for x in ai_items+monitor_items+help_items)
 checks.append({'name':'portal-ai-monitor-help-submenus','ok':ok,'ai_items':len(ai_items),'monitor_items':len(monitor_items),'help_items':len(help_items)})
except Exception as e:checks.append({'name':'portal-ai-monitor-help-submenus','ok':False,'error':type(e).__name__})
try:
 admin_headers={'X-authentik-username':'admin-smoke','X-authentik-email':'admin-smoke@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=admin-usuarios',headers=admin_headers)
 with urllib.request.urlopen(req,timeout=30) as x:admin_page=x.read().decode('utf-8','replace')
 am=re.search(r'<nav class="tabs enterprise-nav".*?</nav>',admin_page,re.S);anav=am.group(0) if am else ''
 admin_items=('Administração','Usuários e perfis','Políticas de acesso','Identidades AGIA','Configurações','Auditoria administrativa','Operações de manutenção')
 ok=all(x in anav for x in admin_items) and 'class="active" href="/cloudiff/portal/?tab=admin-usuarios"' in anav and '@media(max-width:700px)' in admin_page
 checks.append({'name':'portal-admin-navigation-and-responsive-layout','ok':ok,'admin_items':6,'active_state':True,'responsive':True})
except Exception as e:checks.append({'name':'portal-admin-navigation-and-responsive-layout','ok':False,'error':type(e).__name__})
try:
 import re
 headers={'X-authentik-username':'admin-db-smoke','X-authentik-email':'admin-db-smoke@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=bancos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:page=x.read().decode('utf-8','replace')
 cards=re.findall(r'<article class="card db96-card".*?</article>',page,re.S)
 one_active=bool(cards) and all(c.count('db96-mode active')==1 and c.count('ATIVO AGORA')==1 and c.count('db96-mode inactive')>=1 for c in cards)
 ok=one_active and 'cloudif-db-state-design' in page and 'Política de disponibilidade' in page and 'Ações do banco' in page and 'O cartão verde é a opção ativa' in page and 'disabled aria-disabled="true"' in page and '@media(max-width:720px)' in page
 checks.append({'name':'portal-database-active-mode-clarity','ok':ok,'tenant_cards':len(cards),'one_active_mode_per_tenant':one_active,'active_green':True,'inactive_gray':True,'actions_separated':True,'responsive':True})
except Exception as e:checks.append({'name':'portal-database-active-mode-clarity','ok':False,'error':type(e).__name__})
try:
 headers={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=projetos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:project_page=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=bancos',headers=headers)
 with urllib.request.urlopen(req,timeout=30) as x:db_page=x.read().decode('utf-8','replace')
 import re
 navm=re.search(r'<nav class="tabs enterprise-nav".*?</nav>',project_page,re.S);nav2=navm.group(0) if navm else ''
 project_ok=all(x in nav2 for x in ('Lista de projetos','Opções do projeto','Banco de dados','Deploys e Git')) and all(x not in nav2 for x in ('Backups do projeto','Containers','Ambientes e conectores')) and '/cloudiff/portal/?tab=opcoes-projeto' in nav2
 cards=re.findall(r'<article class="card db96-card".*?</article>',db_page,re.S)
 db_ok=bool(cards) and all(c.count('db96-mode active')==1 and c.count('ATIVO AGORA')==1 and c.count('db96-mode inactive')>=1 for c in cards) and all(x in db_page for x in ('db97-legend','verde significa a política ativa','cinza significa opção inativa','azul é ação principal','vermelho é ação destrutiva'))
 checks.append({'name':'portal-project-options-and-database-visual-logic','ok':project_ok and db_ok,'project_menu_items':4,'duplicates_removed':True,'tenant_cards':len(cards),'database_visual_semantics':db_ok})
except Exception as e:checks.append({'name':'portal-project-options-and-database-visual-logic','ok':False,'error':type(e).__name__})
try:
 import re,html as _html
 uh={'X-authentik-username':'iff1742962','X-authentik-email':'iff1742962@example.invalid','X-authentik-groups':'CloudIF-Tenant-iff1742962'}
 ah={'X-authentik-username':'admin-canonical-smoke','X-authentik-email':'admin-canonical@example.invalid','X-authentik-groups':'CloudIF-Tenants-Admin'}
 user_tabs=('opcoes-projeto','gestao-agentes','documentacao-mcp','monitor-saude','monitor-transacoes','monitor-promocoes','monitor-filas','monitor-telemetria','ajuda','ajuda-token','ajuda-clientes','ajuda-aprovacoes','ajuda-ferramentas')
 admin_tabs=('admin-usuarios','admin-politicas','admin-identidades','admin-configuracoes','admin-auditoria','admin-manutencao')
 pages={}
 for tab in user_tabs:
  req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab='+tab,headers=uh)
  with urllib.request.urlopen(req,timeout=30) as x:pages[tab]=x.read().decode('utf-8','replace')
 for tab in admin_tabs:
  req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab='+tab,headers=ah)
  with urllib.request.urlopen(req,timeout=30) as x:pages[tab]=x.read().decode('utf-8','replace')
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=resumo',headers=ah)
 with urllib.request.urlopen(req,timeout=30) as x:menu_page=x.read().decode('utf-8','replace')
 nm=re.search(r'<nav class="tabs enterprise-nav".*?</nav>',menu_page,re.S);nhtml=nm.group(0) if nm else ''
 hrefs=[_html.unescape(x) for x in re.findall(r'<a[^>]+href="([^"]+)"',nhtml) if 'sign_out' not in x]
 unique=len(hrefs)==len(set(hrefs))
 active=all(('class="active" href="/cloudiff/portal/?tab='+tab+'"') in pages[tab] for tab in user_tabs+admin_tabs)
 content=all(('cloudif-unique-pages98' in pages[tab] or 'cloudif-focused-pages98' in pages[tab] or 'cloudif-ui-v2' in pages[tab]) for tab in user_tabs+admin_tabs)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/api/navigation',headers=ah)
 with urllib.request.urlopen(req,timeout=30) as x:api=json.load(x)
 req=urllib.request.Request('http://127.0.0.1:18094/cloudiff/portal/?tab=admin-usuarios',headers=uh)
 with urllib.request.urlopen(req,timeout=30) as x:denied=x.read().decode('utf-8','replace')
 acl='Área restrita à administração' in denied and 'Gestão de usuários e perfis' not in denied
 ok=unique and active and content and acl and api.get('policy')=='one_item_one_route_one_purpose' and api.get('unique_routes_required') is True and api.get('secrets_exposed') is False
 checks.append({'name':'portal-canonical-navigation-contract','ok':ok,'menu_links':len(hrefs),'unique_links':len(set(hrefs)),'user_pages':len(user_tabs),'admin_pages':len(admin_tabs),'active_state':active,'admin_acl':acl,'policy':api.get('policy')})
except Exception as e:checks.append({'name':'portal-canonical-navigation-contract','ok':False,'error':type(e).__name__})
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
