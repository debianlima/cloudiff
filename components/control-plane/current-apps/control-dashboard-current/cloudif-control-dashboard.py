#!/usr/bin/env python3
import os,json,urllib.request,html,sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
HOST=os.environ.get('CLOUDIF_DASH_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_DASH_PORT','18200'))
CU=os.environ['CLOUDIF_CONTROL_URL'];CT=os.environ['CLOUDIF_CONTROL_TOKEN'];MU=os.environ['CLOUDIF_MONITOR_URL'];MT=os.environ['CLOUDIF_MONITOR_TOKEN']
AU=os.environ.get('CLOUDIF_AUDIT_URL','http://127.0.0.1:18201');AT=os.environ.get('CLOUDIF_AUDIT_TOKEN','')
NU=os.environ.get('CLOUDIF_NOTIFY_URL','http://127.0.0.1:18202');NT=os.environ.get('CLOUDIF_NOTIFY_TOKEN','')
GU=os.environ.get('CLOUDIF_AGENT_URL','http://127.0.0.1:18203');GT=os.environ.get('CLOUDIF_AGENT_ADMIN_TOKEN','')
PU=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204');PT=os.environ.get('CLOUDIF_APPROVAL_TOKEN','')
EU=os.environ.get('CLOUDIF_EVAL_URL','http://127.0.0.1:18205');ET=os.environ.get('CLOUDIF_EVAL_TOKEN','')
ACCESS_DB=os.environ.get('CLOUDIF_ACCESS_INGEST_DB','/var/lib/cloudif/access-ingest/access.db')
def get(url,token):
 r=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'});
 with urllib.request.urlopen(r,timeout=8) as x:return json.load(x)
def access_snapshot():
 try:
  c=sqlite3.connect(f'file:{ACCESS_DB}?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row;r=c.execute('select * from snapshots order by id desc limit 1').fetchone();c.close()
  if not r:return {'requests':0,'unique_visitors':0,'hosts':0,'public_requests':0,'internal_requests':0,'bytes':0,'received_at':''}
  d=dict(r);x=json.loads(d['summary_json']);x['received_at']=d['received_at'];return x
 except Exception:return {'requests':0,'unique_visitors':0,'hosts':0,'public_requests':0,'internal_requests':0,'bytes':0,'received_at':'','unavailable':True}
def visible(user,groups):
 ps=get(CU+'/v1/projects',CT)['projects'];admin=any(x in groups.lower() for x in ('admin','professor'))
 if admin:return ps
 out=[]
 for p in ps:
  try:d=get(CU+'/v1/projects/'+p['slug'],CT)
  except Exception:continue
  if p.get('owner')==user or any(a.get('subject_type')=='user' and a.get('subject')==user for a in d.get('acl',[])):out.append(p)
 return out
def data(user,groups):
 admin=any(x in groups.lower() for x in ('admin','professor'))
 ps=visible(user,groups);metrics={x['slug']:x for x in get(MU+'/v1/projects',MT)['projects']};rows=[]
 for p in ps:
  m=metrics.get(p['slug'],{});rows.append({'slug':p['slug'],'name':p['name'],'tenant':p['tenant'],'status':p['status'],'repo_url':p['repo_url'],'connectors':{'forgejo':p['forgejo_status'],'supabase':p['supabase_status'],'publication':p['komodo_status']},'metrics':{'state':m.get('state','unknown'),'running':bool(m.get('running')),'healthy':bool(m.get('healthy')),'cpu_pct':m.get('cpu_pct',0),'mem_pct':m.get('mem_pct',0),'mem_usage':m.get('mem_usage',''),'net_io':m.get('net_io',''),'pids':m.get('pids',0),'container_name':m.get('container_name',''),'issues':json.loads(m.get('issues_json') or '[]')}})
 try:audit=get(AU+'/v1/summary',AT).get('summary') or {}
 except Exception:audit={'mcp_calls':0,'agent_events':0,'errors':0,'unavailable':True}
 try:
  notices=get(NU+'/v1/notifications?status=open',NT).get('notifications') or []
  allowed={x['slug'] for x in rows};notices=[n for n in notices if not n.get('project_slug') or n.get('project_slug') in allowed]
 except Exception:notices=[]
 try:clients=get(GU+'/v1/clients',GT).get('clients') or []
 except Exception:clients=[]
 try:
  approvals=get(PU+'/v1/approvals?status=pending',PT).get('approvals') or []
  allowed={x['slug'] for x in rows};approvals=[a for a in approvals if a.get('project_slug') in allowed]
 except Exception:approvals=[]
 try:
  evaluations=get(EU+'/v1/evaluations',ET).get('evaluations') or []
  allowed={x['slug'] for x in rows};evaluations=[e for e in evaluations if e.get('project_slug') in allowed]
 except Exception:evaluations=[]
 access=access_snapshot() if admin else {'requests':0,'unique_visitors':0,'hosts':0,'public_requests':0,'internal_requests':0,'bytes':0,'received_at':''}
 return {'ok':True,'user':user,'projects':rows,'notifications':notices,'clients':clients,'approvals':approvals,'evaluations':evaluations,'access':access,'summary':{'total':len(rows),'running':sum(x['metrics']['running'] for x in rows),'healthy':sum(x['metrics']['healthy'] for x in rows),'critical':sum(bool(x['metrics']['issues']) for x in rows),'mcp_calls':int(audit.get('mcp_calls') or 0),'agent_events':int(audit.get('agent_events') or 0),'audit_errors':int(audit.get('errors') or 0),'audit_unavailable':bool(audit.get('unavailable')),'open_alerts':len(notices),'critical_alerts':sum(n.get('severity')=='critical' for n in notices),'mcp_clients':len(clients),'pending_approvals':len(approvals),'draft_evaluations':sum(e.get('status')=='draft' for e in evaluations),'reviewed_evaluations':sum(e.get('status')=='reviewed' for e in evaluations),'access_requests':int(access.get('requests') or 0),'unique_visitors':int(access.get('unique_visitors') or 0),'access_hosts':int(access.get('hosts') or 0),'public_requests':int(access.get('public_requests') or 0)}}
CSS='''*{box-sizing:border-box}html{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f3f7f4;color:#14231a}body{margin:0;padding-bottom:72px}header{position:sticky;top:0;z-index:3;background:#10291d;color:#fff;padding:14px 16px}header strong{display:block;font-size:1.1rem}header span{color:#b8d4c3;font-size:.78rem}main{padding:14px;max-width:1440px;margin:auto}.hero{background:linear-gradient(145deg,#123522,#1b7650);color:#fff;border-radius:20px;padding:22px}.hero h1{margin:.2rem 0;font-size:clamp(1.6rem,8vw,2.6rem)}.summary{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.summary article,.card{background:#fff;border:1px solid #dae5dd;border-radius:16px;padding:14px}.summary span,.metric span{display:block;color:#68766c;font-size:.72rem}.summary strong{font-size:1.5rem}.grid{display:grid;grid-template-columns:1fr;gap:12px}.head{display:flex;justify-content:space-between;gap:10px}.dot{width:11px;height:11px;border-radius:50%;background:#e25757;margin-top:5px}.ok .dot{background:#28c775}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}.metric{background:#f1f6f2;border-radius:11px;padding:9px}.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{font-size:.68rem;padding:5px 8px;border-radius:99px;background:#e4f3e9;color:#22593a}nav{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #dae5dd;display:grid;grid-template-columns:repeat(4,1fr);padding:7px}nav a{min-height:44px;display:grid;place-items:center;text-decoration:none;color:#52645a;font-size:.75rem}:focus-visible{outline:3px solid #3ed786;outline-offset:2px}@media(min-width:720px){body{padding-bottom:0}.summary{grid-template-columns:repeat(4,1fr)}.grid{grid-template-columns:repeat(2,1fr)}nav{position:static;margin:10px auto;max-width:600px;border:0;border-radius:14px}}@media(min-width:1100px){.grid{grid-template-columns:repeat(3,1fr)}main{padding:24px}}'''
def page(d):
 cards=[]
 for p in d['projects']:
  m=p['metrics'];cls='card ok' if m['healthy'] else 'card';chips=''.join(f'<span class="chip">{html.escape(k)}: {html.escape(str(v or "unknown"))}</span>' for k,v in p['connectors'].items())
  cards.append(f'''<article class="{cls}"><div class="head"><div><strong>{html.escape(p['name'])}</strong><small>{html.escape(p['slug'])}</small></div><i class="dot" aria-label="{'Saudável' if m['healthy'] else 'Atenção'}"></i></div><div class="metrics"><div class="metric"><span>CPU</span><b>{m['cpu_pct']}%</b></div><div class="metric"><span>Memória</span><b>{html.escape(str(m['mem_usage']))}</b></div><div class="metric"><span>Rede</span><b>{html.escape(str(m['net_io']))}</b></div><div class="metric"><span>Processos</span><b>{m['pids']}</b></div></div><div class="chips">{chips}</div></article>''')
 s=d['summary'];return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#10291d"><link rel="manifest" href="/cloudiff/portal/control/manifest.webmanifest"><link rel="icon" href="/cloudiff/portal/control/icon.svg" type="image/svg+xml"><meta name="apple-mobile-web-app-capable" content="yes"><title>CloudIFF Controle</title><style>{CSS}</style></head><body><header><strong>CloudIFF</strong><span>Controle e monitoramento</span></header><nav aria-label="Principal"><a href="#resumo">Resumo</a><a href="#projetos">Projetos</a><a href="#ia">IA</a><a href="#perfil">Perfil</a></nav><main><section class="hero" id="resumo"><p>Visão acadêmica e operacional</p><h1>Olá, {html.escape(d['user'])}</h1><p>Recursos e conectores dos projetos autorizados.</p></section><section class="summary"><article><span>Projetos</span><strong>{s['total']}</strong></article><article><span>Executando</span><strong>{s['running']}</strong></article><article><span>Saudáveis</span><strong>{s['healthy']}</strong></article><article><span>Atenção</span><strong>{s['critical']}</strong></article><article><span>Chamadas MCP</span><strong>{s['mcp_calls']}</strong></article><article><span>Eventos de agente</span><strong>{s['agent_events']}</strong></article><article><span>Alertas abertos</span><strong>{s['open_alerts']}</strong></article><article><span>Alertas críticos</span><strong>{s['critical_alerts']}</strong></article><article><span>Clientes MCP</span><strong>{s['mcp_clients']}</strong></article><article><span>Aprovações pendentes</span><strong>{s['pending_approvals']}</strong></article><article><span>Avaliações em rascunho</span><strong>{s['draft_evaluations']}</strong></article><article><span>Avaliações revisadas</span><strong>{s['reviewed_evaluations']}</strong></article><article><span>Requisições públicas</span><strong>{s['access_requests']}</strong></article><article><span>Visitantes únicos</span><strong>{s['unique_visitors']}</strong></article><article><span>Hosts publicados</span><strong>{s['access_hosts']}</strong></article><article><span>Tráfego externo</span><strong>{s['public_requests']}</strong></article></section><h2 id="projetos">Projetos</h2><section class="grid">{''.join(cards)}</section></main><script>if("serviceWorker" in navigator){{addEventListener("load",()=>navigator.serviceWorker.register("/cloudiff/portal/control/sw.js",{{scope:"/cloudiff/portal/control/"}}).catch(()=>{{}}));}}</script></body></html>'''
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def ident(self):return self.headers.get('X-authentik-username','').strip(),self.headers.get('X-authentik-groups','')
 def out(self,code,b,ctype):
  if isinstance(b,str):b=b.encode();self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/health':self.out(200,json.dumps({'ok':True}),'application/json');return
  if p=='/manifest.webmanifest':
   self.out(200,json.dumps({'name':'CloudIFF Controle','short_name':'CloudIFF','start_url':'/cloudiff/portal/control','scope':'/cloudiff/portal/control/','display':'standalone','background_color':'#f3f7f4','theme_color':'#10291d','lang':'pt-BR','icons':[{'src':'/cloudiff/portal/control/icon.svg','sizes':'any','type':'image/svg+xml','purpose':'any maskable'}]},ensure_ascii=False),'application/manifest+json');return
  if p=='/sw.js':
   self.out(200,"const C='cloudiff-static-v1';const A=['/cloudiff/portal/control/manifest.webmanifest','/cloudiff/portal/control/icon.svg'];self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(A)).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(A.includes(u.pathname)){e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));}});",'application/javascript; charset=utf-8');return
  if p=='/icon.svg':
   self.out(200,"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><rect width='512' height='512' rx='112' fill='#10291d'/><path d='M128 152h256v56H192v48h160v56H192v48h192v56H128z' fill='#3ed786'/></svg>",'image/svg+xml');return
  u,g=self.ident()
  if not u:self.out(401,json.dumps({'ok':False,'error':'unauthorized'}),'application/json');return
  try:d=data(u,g)
  except Exception:self.out(503,json.dumps({'ok':False,'error':'backend_unavailable'}),'application/json');return
  if p=='/api/dashboard':self.out(200,json.dumps(d,ensure_ascii=False,separators=(',',':')),'application/json');return
  if p=='/':self.out(200,page(d),'text/html; charset=utf-8');return
  self.out(404,'not found','text/plain')
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
