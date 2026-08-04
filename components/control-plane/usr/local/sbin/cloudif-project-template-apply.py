#!/usr/bin/env python3
import base64,json,sqlite3,sys,time,urllib.request,urllib.error
from pathlib import Path
LIB=Path("/srv/cloudif/lib")
if str(LIB) not in sys.path: sys.path.insert(0,str(LIB))
DB='/var/lib/cloudif/portal/cloudif-portal.db'
def read_env(path):
 d={}; p=Path(path)
 if p.exists():
  for line in p.read_text(errors='ignore').splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1); d[k.strip()]=v.strip().strip('"\'')
 return d
def post(url,token,payload,timeout=90):
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),method='POST',headers={'Content-Type':'application/json','X-CloudIF-Token':token,'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read() or b'{}')
def public_number(slug):
 c=sqlite3.connect(DB); now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 c.execute('CREATE TABLE IF NOT EXISTS project_public_ids(project_slug TEXT PRIMARY KEY,public_number INTEGER NOT NULL UNIQUE,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
 r=c.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
 if not r:
  n=c.execute('select coalesce(max(public_number),1000)+1 from project_public_ids').fetchone()[0]
  c.execute('insert into project_public_ids values(?,?,?,?)',(slug,n,now,now)); c.commit()
 else:n=r[0]
 c.close(); return n
def build(kind,slug,owner,tenant,num):
 if kind=='onboarding':
  from cloudif_onboarding_v2 import build_onboarding_v2
  return build_onboarding_v2(slug,owner,tenant,num)
 portal='https://cloudiff.duckdns.org/'; forge=f'https://cloudiff.duckdns.org/git/cloudif/cloudif-{slug}'; kom='https://komodoiff.duckdns.org/'; sup=f'https://{tenant}.cloudiff.duckdns.org/project/default'; site=f'https://{num}.cloudiff.duckdns.org/'
 if kind=='onboarding':
  title='Primeiros Passos CloudIF'; body=f'''<h2>Aprenda usando este projeto</h2><div class="steps"><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#0b4768"/><text x="30" y="70" fill="white" font-size="30">Portal CloudIF</text><text x="30" y="120" fill="white" font-size="20">Crie, publique e acompanhe o projeto.</text></svg><p>Abra o Portal e acompanhe permissões, provisionamento e publicações.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#6d3bd1"/><text x="30" y="70" fill="white" font-size="30">Forgejo</text><text x="30" y="120" fill="white" font-size="20">Edite, faça commit e observe o webhook.</text></svg><p>Edite <code>site/index.html</code>, faça commit na main e acompanhe o webhook.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#08796d"/><text x="30" y="70" fill="white" font-size="30">Komodo</text><text x="30" y="120" fill="white" font-size="20">Veja stack, container, logs e saúde.</text></svg><p>Confira o stack e o healthcheck do serviço web.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#078a54"/><text x="30" y="70" fill="white" font-size="30">Supabase</text><text x="30" y="120" fill="white" font-size="20">Use PostgreSQL, API REST e RLS.</text></svg><p>Abra o tenant, crie tabelas e use a API conforme as políticas.</p></article><article><h3>Webhooks habilitados</h3><ul><li>Push Forgejo → CloudIF</li><li>Release Forgejo → publicação</li><li>CloudIF → Komodo para pull/deploy</li><li>Supabase por tabela e evento quando configurado no Portal</li></ul></article></div>'''
 else:
  title='Projeto CloudIF'; body='<h2>Recursos deste projeto</h2><p>Use os atalhos abaixo para código, deploy, banco e publicação.</p>'
 html=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;font:16px system-ui;background:#eef3f8;color:#182235}}header{{background:linear-gradient(135deg,#0b3155,#0f7b8d);color:white;padding:54px 6vw}}main{{max-width:1050px;margin:auto;padding:32px}}nav{{display:flex;gap:10px;flex-wrap:wrap}}a{{background:white;color:#0b4768;padding:11px 15px;border-radius:10px;text-decoration:none;font-weight:700}}article{{background:white;padding:22px;border-radius:16px;margin:18px 0;box-shadow:0 8px 20px #0001}}svg{{width:100%;height:auto;border-radius:12px}}code{{background:#142033;color:white;padding:3px 6px;border-radius:6px}}</style></head><body><header><h1>{title}</h1><p>Projeto {slug} · usuário {owner}</p><nav><a href="{portal}">Portal</a><a href="{forge}">Forgejo</a><a href="{kom}">Komodo</a><a href="{sup}">Supabase</a><a href="{site}">Site</a></nav></header><main>{body}</main></body></html>'''
 compose='''services:\n  web:\n    image: nginx:1.27-alpine\n    container_name: cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n    restart: unless-stopped\n    volumes:\n      - ./site:/usr/share/nginx/html:ro\n      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro\n    healthcheck:\n      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/health >/dev/null 2>&1"]\n      interval: 15s\n      timeout: 5s\n      retries: 10\n    networks:\n      cloudif-publications:\n        aliases:\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-active-web\nnetworks:\n  cloudif-publications:\n    external: true\n'''
 nginx='server { listen 80; root /usr/share/nginx/html; index index.html; location = /health { default_type application/json; return 200 \'{"ok":true}\'; } location / { try_files $uri $uri/ /index.html; } }\n'
 return [('README.md',f'# {title}\n\nPortal: {portal}\nForgejo: {forge}\nKomodo: {kom}\nSupabase: {sup}\nSite: {site}\n'),('site/index.html',html),('nginx.conf',nginx),('.env',f'CLOUDIF_PUBLIC_NUMBER={num}\nCLOUDIF_DEPLOY_NUMBER=1\n'),('docker-compose.yml',compose)]

def runtime_overlay(template):
 template=(template or 'static-nginx').strip().lower()
 if template in ('node20','node22','node24'):
  version=template.replace('node','')
  docker=f"FROM node:{version}-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm install --omit=dev\nCOPY . .\nEXPOSE 3000\nCMD [\"npm\",\"start\"]\n"
  package='{"name":"cloudif-app","private":true,"scripts":{"start":"node server.js"},"dependencies":{"express":"^4.21.0"}}\n'
  server="const express=require('express');const app=express();app.use(express.static('site'));app.get('/health',(_,r)=>r.json({ok:true}));app.listen(3000,'0.0.0.0');\n"
  compose='services:\n  web:\n    build: .\n    container_name: cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n    restart: unless-stopped\n    healthcheck:\n      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:3000/health >/dev/null 2>&1\"]\n      interval: 15s\n      timeout: 5s\n      retries: 10\n    networks:\n      cloudif-publications:\n        aliases:\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-active-web\nnetworks:\n  cloudif-publications:\n    external: true\n'
  return [('Dockerfile',docker),('package.json',package),('server.js',server),('docker-compose.yml',compose)]
 if template=='php83-apache':
  docker="""FROM php:8.3-apache
COPY site/ /var/www/html/
RUN printf '<Directory /var/www/html>\nAllowOverride All\nRequire all granted\n</Directory>\n' > /etc/apache2/conf-available/cloudif.conf && a2enconf cloudif
"""
  compose='services:\n  web:\n    build: .\n    container_name: cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n    restart: unless-stopped\n    healthcheck:\n      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1/health.php >/dev/null\"]\n      interval: 15s\n      timeout: 5s\n      retries: 10\n    networks:\n      cloudif-publications:\n        aliases:\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-active-web\nnetworks:\n  cloudif-publications:\n    external: true\n'
  return [('Dockerfile',docker),('site/index.php',"<?php echo 'CloudIF PHP 8.3';"),('site/health.php',"<?php header('Content-Type: application/json'); echo '{\"ok\":true}';"),('docker-compose.yml',compose)]
 return []

def merge_runtime(files,template):
 overlay=runtime_overlay(template)
 if not overlay:return files
 names={name for name,_ in overlay}
 return [(name,content) for name,content in files if name not in names]+overlay

def main():
 job=json.loads(Path(sys.argv[1]).read_text()); kind=job.get('template_kind','none'); runtime=job.get('runtime_template','static-nginx')
 if kind not in ('onboarding','links'): print({'skipped':True,'kind':kind}); return
 slug=job['slug']; owner=(job.get('user') or {}).get('username',''); tenant=job['tenant']; num=public_number(slug)
 marker=Path(f'/srv/cloudif/provisioning/projects/{slug}/template-applied.json')
 if marker.exists():
  try:
   old_marker=json.loads(marker.read_text())
   if old_marker.get('kind')==kind and old_marker.get('runtime_template')==runtime and old_marker.get('version')==4:
    print(json.dumps({'ok':True,'skipped':True,'reason':'template_already_applied','kind':kind,'project':slug,'public_number':num},ensure_ascii=False)); return
  except Exception: pass
 cfg=read_env('/etc/cloudif/forja-agent-client.env'); base=(cfg.get('FORJA_AGENT_URL') or 'http://10.62.91.2:18095').rstrip('/'); tok=cfg.get('FORJA_AGENT_TOKEN','')
 if not tok: raise SystemExit('missing_forja_token')
 results=[]
 files=merge_runtime(build(kind,slug,owner,tenant,num),runtime)
 for path,content in files:
  payload={'project_slug':slug,'path':path,'branch':'main','message':f'CloudIF: aplicar template {kind} ({path})','source':'project-template-automation','content_b64':base64.b64encode(content.encode()).decode()}
  last=None
  for i in range(10):
   try:last=post(base+'/project/file/commit',tok,payload); break
   except Exception as e:last={'ok':False,'error':str(e)}; time.sleep(5)
  if not last or not last.get('ok'): raise RuntimeError(f'commit_failed:{path}:{last}')
  results.append({'path':path,'commit':last.get('commit_sha','')})
 marker.parent.mkdir(parents=True,exist_ok=True)
 marker.write_text(json.dumps({'kind':kind,'runtime_template':runtime,'version':4,'project':slug,'public_number':num,'applied_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'files':results},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'ok':True,'kind':kind,'project':slug,'public_number':num,'files':results},ensure_ascii=False))
if __name__=='__main__': main()
