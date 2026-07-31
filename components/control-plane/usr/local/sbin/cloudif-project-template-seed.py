#!/usr/bin/env python3
import base64,json,os,re,sqlite3,subprocess,sys,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
DB='/var/lib/cloudif/portal/cloudif-portal.db'
ENV_FILES=['/etc/cloudif/provision.env','/etc/cloudif/forja-agent-client.env','/etc/cloudif/komodo-agent-client.env']
def load_env():
 d={}
 for f in ENV_FILES:
  p=Path(f)
  if not p.exists(): continue
  for line in p.read_text(errors='ignore').splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1); d[k]=v.strip().strip('"\'')
 return d
def req(url,method='GET',data=None,headers=None,timeout=60):
 h={'Accept':'application/json'}; h.update(headers or {})
 body=None
 if data is not None:
  body=json.dumps(data).encode(); h['Content-Type']='application/json'
 r=urllib.request.Request(url,data=body,method=method,headers=h)
 try:
  with urllib.request.urlopen(r,timeout=timeout) as x:
   raw=x.read().decode(errors='ignore'); return x.status,(json.loads(raw) if raw else {}),raw
 except urllib.error.HTTPError as e:
  raw=e.read().decode(errors='ignore')
  try:d=json.loads(raw)
  except:d={}
  return e.code,d,raw
def svg(title,subtitle,color,items):
 rows=''.join(f'<rect x="80" y="{170+i*72}" width="864" height="52" rx="12" fill="#ffffff" opacity=".95"/><text x="108" y="{203+i*72}" font-family="Arial" font-size="22" fill="#183153">{x}</text>' for i,x in enumerate(items))
 return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="640" viewBox="0 0 1024 640"><rect width="1024" height="640" fill="{color}"/><rect x="44" y="44" width="936" height="552" rx="28" fill="#f8fafc" opacity=".18"/><text x="80" y="104" font-family="Arial" font-size="42" font-weight="700" fill="#fff">{title}</text><text x="80" y="142" font-family="Arial" font-size="22" fill="#e2e8f0">{subtitle}</text>{rows}</svg>'''
def files_for(kind,slug,owner,tenant,anon):
 repo=f'https://cloudiff.duckdns.org/git/cloudif/cloudif-{slug}'
 portal='https://cloudiff.duckdns.org/'
 komodo='https://komodoiff.duckdns.org/'
 supabase=f'https://{tenant}.cloudiff.duckdns.org/project/default'
 public=f'https://cloudiff.duckdns.org/apps/{slug}/'
 common_links=f'''<a href="{portal}" target="_blank">Portal CloudIF</a><a href="{repo}" target="_blank">Forgejo</a><a href="{komodo}" target="_blank">Komodo</a><a href="{supabase}" target="_blank">Supabase</a>'''
 if kind=='onboarding':
  title='Primeiros Passos CloudIF'
  intro='Aprenda alterando este próprio projeto. Faça uma mudança no Forgejo, observe o webhook, acompanhe o deploy no Komodo e consulte os dados no Supabase.'
  sections='''
<section id="portal"><h2>1. Portal CloudIF</h2><img src="assets/portal.svg" alt="Portal CloudIF"><p>O Portal reúne projetos, permissões, bancos, publicação e histórico. Este projeto pertence ao seu usuário e serve como ambiente seguro de aprendizado.</p></section>
<section id="forgejo"><h2>2. Edite no Forgejo</h2><img src="assets/forgejo.svg" alt="Forgejo"><ol><li>Abra o repositório pelo botão acima.</li><li>Edite <code>site/index.html</code> ou <code>site/style.css</code>.</li><li>Crie um commit na branch <code>main</code>.</li><li>O webhook de push avisa o CloudIF automaticamente.</li></ol></section>
<section id="komodo"><h2>3. Acompanhe no Komodo</h2><img src="assets/komodo.svg" alt="Komodo"><p>O Komodo mantém o stack do projeto. Após um push, confira o pull, o deploy e os logs do serviço <code>web</code>. Não altere tokens nem credenciais no compose.</p></section>
<section id="supabase"><h2>4. Use o banco Supabase</h2><img src="assets/supabase.svg" alt="Supabase"><p>A tabela de demonstração é <code>public.cloudif_tutorial_steps</code>. O botão abaixo consulta a API REST com a chave pública do projeto.</p><button id="db-test">Testar conexão com o banco</button><pre id="db-result">Ainda não testado.</pre></section>
<section id="webhooks"><h2>5. Webhooks habilitados</h2><img src="assets/webhooks.svg" alt="Webhooks"><ul><li><strong>Forgejo push:</strong> registra alterações e aciona sincronização/deploy.</li><li><strong>Forgejo release:</strong> participa do fluxo de publicação versionada.</li><li><strong>CloudIF → Komodo:</strong> solicita atualização do stack e acompanha o resultado.</li><li><strong>Eventos do banco:</strong> podem ser habilitados por tabela no Portal, com endpoint e eventos definidos.</li></ul><p>Segredos de webhook nunca aparecem no site ou no repositório.</p></section>
<section><h2>6. Exercício sugerido</h2><ol><li>Troque o título desta página.</li><li>Adicione uma linha na tabela pelo Supabase.</li><li>Faça commit no Forgejo.</li><li>Acompanhe o deploy no Komodo.</li><li>Abra novamente a URL pública e confirme a mudança.</li></ol></section>'''
 else:
  title='Projeto CloudIF'
  intro='Página inicial criada automaticamente com os recursos deste projeto.'
  sections='''<section><h2>Recursos vinculados</h2><p>Use os atalhos acima para administrar código, deploy e banco conforme suas permissões.</p></section><section><h2>Próximos passos</h2><ol><li>Substitua esta página pelo conteúdo da aplicação.</li><li>Edite o código no Forgejo.</li><li>Acompanhe o stack no Komodo.</li><li>Configure e consulte o banco no Supabase.</li></ol></section>'''
 index=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="stylesheet" href="style.css"></head><body><header><span class="badge">Projeto de {owner}</span><h1>{title}</h1><p>{intro}</p><nav>{common_links}</nav></header><main>{sections}</main><footer><p>Projeto: <code>{slug}</code> · Tenant: <code>{tenant}</code></p><a href="{public}">URL pública deste projeto</a></footer><script src="config.js"></script><script src="app.js"></script></body></html>'''
 css='''*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Arial;background:#f1f5f9;color:#172033;line-height:1.6}header{padding:64px max(6vw,24px);background:linear-gradient(135deg,#0f3b63,#106c8a);color:#fff}h1{font-size:clamp(2.2rem,5vw,4.6rem);margin:.2rem 0}.badge{display:inline-block;background:#f5a623;color:#152238;padding:6px 12px;border-radius:999px;font-weight:700}nav{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}nav a,button{background:#fff;color:#0f3b63;border:0;padding:12px 18px;border-radius:10px;font-weight:700;text-decoration:none;cursor:pointer}main{max-width:1100px;margin:0 auto;padding:42px 24px}section{background:#fff;padding:30px;margin:0 0 24px;border-radius:18px;box-shadow:0 8px 24px #0f172a12}section img{width:100%;border-radius:14px;margin:12px 0 20px}code,pre{background:#0f172a;color:#dbeafe;border-radius:8px;padding:3px 7px}pre{padding:16px;overflow:auto}footer{padding:32px;text-align:center;color:#475569}footer a{color:#0f6c8a}ol,ul{padding-left:24px}@media(max-width:700px){header{padding-top:38px}section{padding:20px}}'''
 js='''document.getElementById("db-test")?.addEventListener("click",async()=>{const out=document.getElementById("db-result");out.textContent="Consultando...";try{const r=await fetch(window.CLOUDIF_CONFIG.supabaseRest+"/cloudif_tutorial_steps?select=id,title,completed&order=id",{headers:{apikey:window.CLOUDIF_CONFIG.anonKey,Authorization:"Bearer "+window.CLOUDIF_CONFIG.anonKey}});const text=await r.text();if(!r.ok)throw new Error("HTTP "+r.status+" "+text);out.textContent=JSON.stringify(JSON.parse(text),null,2)}catch(e){out.textContent="Falha: "+e.message}});'''
 cfg=f'''window.CLOUDIF_CONFIG={{supabaseRest:"https://{tenant}.cloudiff.duckdns.org/rest/v1",anonKey:{json.dumps(anon)}}};'''
 compose=f'''services:\n  web:\n    image: nginx:1.27-alpine\n    restart: unless-stopped\n    volumes:\n      - ./site:/usr/share/nginx/html:ro\n      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro\n    healthcheck:\n      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/health >/dev/null 2>&1"]\n      interval: 15s\n      timeout: 5s\n      retries: 10\n    networks:\n      default:\n        aliases:\n          - cloudif-{slug}-web\n'''
 nginx='''server { listen 80; server_name _; root /usr/share/nginx/html; index index.html; location = /health { access_log off; add_header Content-Type text/plain; return 200 "ok\\n"; } location / { try_files $uri $uri/ /index.html; } }'''
 readme=f'''# {title}\n\nProjeto criado automaticamente pelo CloudIF para **{owner}**.\n\n## Links\n\n- Portal: {portal}\n- Forgejo: {repo}\n- Komodo: {komodo}\n- Supabase: {supabase}\n- Site: {public}\n\n## Fluxo automático\n\n1. Commit no Forgejo.\n2. Webhook de push notifica o CloudIF.\n3. O CloudIF solicita atualização no Komodo.\n4. O stack é validado.\n5. A publicação saudável é disponibilizada.\n\nOs tokens e segredos são mantidos fora do repositório.\n'''
 data={
 'README.md':readme,'docker-compose.yml':compose,'nginx.conf':nginx,
 'site/index.html':index,'site/style.css':css,'site/app.js':js,'site/config.js':cfg,
 '.cloudif-template.json':json.dumps({'schema':1,'kind':kind,'owner':owner,'tenant':tenant,'project':slug},indent=2,ensure_ascii=False),
 }
 if kind=='onboarding':
  data.update({
   'site/assets/portal.svg':svg('Portal CloudIF','Projetos, permissões, bancos e publicação','#0f3b63',['Abra o projeto','Confira os links integrados','Acompanhe o histórico de publicação']),
   'site/assets/forgejo.svg':svg('Forgejo','Código e controle de versão','#7c3aed',['Edite os arquivos','Crie um commit na main','O webhook avisa o CloudIF']),
   'site/assets/komodo.svg':svg('Komodo','Stack, containers, logs e deploy','#0f766e',['Verifique o stack','Acompanhe pull e deploy','Consulte logs e healthcheck']),
   'site/assets/supabase.svg':svg('Supabase','Banco PostgreSQL e API REST','#059669',['Abra o tenant pessoal','Consulte cloudif_tutorial_steps','Teste a API pelo site']),
   'site/assets/webhooks.svg':svg('Webhooks','Automação entre código e deploy','#b45309',['Push no Forgejo','Notificação ao CloudIF','Atualização do stack no Komodo']),
   'supabase/seed.sql':'-- Executado automaticamente no tenant pessoal.\nselect * from public.cloudif_tutorial_steps order by id;\n',
  })
 return data
def seed_db(tenant):
 env=Path(f'/srv/cloudif/tenants/{tenant}/.env')
 if not env.exists(): raise RuntimeError('tenant_env_missing')
 sql='''CREATE TABLE IF NOT EXISTS public.cloudif_tutorial_steps (id integer PRIMARY KEY, title text NOT NULL, completed boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()); ALTER TABLE public.cloudif_tutorial_steps ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS cloudif_tutorial_read ON public.cloudif_tutorial_steps; CREATE POLICY cloudif_tutorial_read ON public.cloudif_tutorial_steps FOR SELECT TO anon, authenticated USING (true); INSERT INTO public.cloudif_tutorial_steps(id,title,completed) VALUES (1,'Abrir o Portal CloudIF',true),(2,'Editar um arquivo no Forgejo',false),(3,'Acompanhar o deploy no Komodo',false),(4,'Consultar dados no Supabase',false),(5,'Entender os webhooks',false) ON CONFLICT(id) DO UPDATE SET title=excluded.title;'''
 cmd=['docker','exec','-i',f'cloudif_{tenant}-db-1','psql','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1']
 r=subprocess.run(cmd,input=sql,text=True,capture_output=True,timeout=120)
 if r.returncode: raise RuntimeError('database_seed_failed:'+r.stderr[-300:])
def main():
 if len(sys.argv)<5: raise SystemExit('usage: seed <kind> <slug> <owner> <tenant>')
 kind,slug,owner,tenant=sys.argv[1:5]
 env=load_env(); token=env.get('FORGEJO_TOKEN',''); base=(env.get('FORGEJO_URL') or 'https://cloudiff.duckdns.org/git').rstrip('/')
 if not token: raise RuntimeError('forgejo_token_missing')
 api=base+'/api/v1'; repo=f'cloudif-{slug}'; auth={'Authorization':'token '+token}
 st,meta,_=req(f'{api}/repos/cloudif/{repo}',headers=auth)
 if st!=200: raise RuntimeError(f'repo_lookup_failed:{st}')
 tenant_env={}
 for line in Path(f'/srv/cloudif/tenants/{tenant}/.env').read_text(errors='ignore').splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1); tenant_env[k]=v.strip().strip('"\'')
 anon=tenant_env.get('ANON_KEY') or tenant_env.get('SUPABASE_ANON_KEY') or ''
 if not anon: raise RuntimeError('anon_key_missing')
 created=[]; skipped=[]
 for path,content in files_for(kind,slug,owner,tenant,anon).items():
  q=urllib.parse.quote(path,safe='/')
  s,_,_=req(f'{api}/repos/cloudif/{repo}/contents/{q}?ref=main',headers=auth)
  if s==200: skipped.append(path); continue
  payload={'content':base64.b64encode(content.encode()).decode(),'message':f'CloudIF: adicionar template {kind} ({path})','branch':'main','committer':{'name':'CloudIF Automation','email':'cloudif@localhost'},'author':{'name':owner,'email':f'{owner}@localhost'}}
  s,d,raw=req(f'{api}/repos/cloudif/{repo}/contents/{q}',method='POST',data=payload,headers=auth,timeout=90)
  if s not in (200,201): raise RuntimeError(f'create_file_failed:{path}:{s}:{raw[:180]}')
  created.append(path)
 if kind=='onboarding': seed_db(tenant)
 # Trigger pull and deploy through the existing agent.
 agent=(env.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/'); kt=env.get('KOMODO_AGENT_TOKEN','')
 hdr={'X-CloudIF-Token':kt} if kt else {}
 results={}
 for op in ('pull','deploy'):
  s,d,raw=req(agent+f'/komodo/stack/{op}',method='POST',data={'project':slug,'project_slug':slug,'tenant':tenant,'actor':'cloudif-template-seed','source':'onboarding-template'},headers=hdr,timeout=240)
  results[op]={'status':s,'ok':s in (200,201,202) and not (isinstance(d,dict) and d.get('ok') is False)}
 print(json.dumps({'kind':kind,'project':slug,'created':created,'skipped':skipped,'database_seeded':kind=='onboarding','komodo':results},ensure_ascii=False))
if __name__=='__main__': main()
