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
 portal='https://cloudiff.duckdns.org/'; forge=f'https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}'; kom='https://komodoiff.duckdns.org/'; sup=f'https://{tenant}.cloudiff.duckdns.org/project/default'; site=f'https://{num}.cloudiff.duckdns.org/'
 if kind=='onboarding':
  title='Primeiros Passos CloudIF'; body=f'''<h2>Aprenda usando este projeto</h2><div class="steps"><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#0b4768"/><text x="30" y="70" fill="white" font-size="30">Portal CloudIF</text><text x="30" y="120" fill="white" font-size="20">Crie, publique e acompanhe o projeto.</text></svg><p>Abra o Portal e acompanhe permissões, provisionamento e publicações.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#6d3bd1"/><text x="30" y="70" fill="white" font-size="30">Forgejo</text><text x="30" y="120" fill="white" font-size="20">Edite, faça commit e observe o webhook.</text></svg><p>Edite <code>site/index.html</code>, faça commit na main e acompanhe o webhook.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#08796d"/><text x="30" y="70" fill="white" font-size="30">Komodo</text><text x="30" y="120" fill="white" font-size="20">Veja stack, container, logs e saúde.</text></svg><p>Confira o stack e o healthcheck do serviço web.</p></article><article><svg viewBox="0 0 600 180"><rect width="600" height="180" rx="18" fill="#078a54"/><text x="30" y="70" fill="white" font-size="30">Supabase</text><text x="30" y="120" fill="white" font-size="20">Use PostgreSQL, API REST e RLS.</text></svg><p>Abra o tenant, crie tabelas e use a API conforme as políticas.</p></article><article><h3>Webhooks habilitados</h3><ul><li>Push Forgejo → CloudIF</li><li>Release Forgejo → publicação</li><li>CloudIF → Komodo para pull/deploy</li><li>Supabase por tabela e evento quando configurado no Portal</li></ul></article></div>'''
 else:
  title='Projeto CloudIF'; body='<h2>Recursos deste projeto</h2><p>Use os atalhos abaixo para código, deploy, banco e publicação.</p>'
 html=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;font:16px system-ui;background:#eef3f8;color:#182235}}header{{background:linear-gradient(135deg,#0b3155,#0f7b8d);color:white;padding:54px 6vw}}main{{max-width:1050px;margin:auto;padding:32px}}nav{{display:flex;gap:10px;flex-wrap:wrap}}a{{background:white;color:#0b4768;padding:11px 15px;border-radius:10px;text-decoration:none;font-weight:700}}article{{background:white;padding:22px;border-radius:16px;margin:18px 0;box-shadow:0 8px 20px #0001}}svg{{width:100%;height:auto;border-radius:12px}}code{{background:#142033;color:white;padding:3px 6px;border-radius:6px}}</style></head><body><header><h1>{title}</h1><p>Projeto {slug} · usuário {owner}</p><nav><a href="{portal}">Portal</a><a href="{forge}">Forgejo</a><a href="{kom}">Komodo</a><a href="{sup}">Supabase</a><a href="{site}">Site</a></nav></header><main>{body}</main></body></html>'''
 compose='''services:\n  web:\n    image: nginx:1.27-alpine\n    container_name: cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n    restart: unless-stopped\n    volumes:\n      - ./site:/usr/share/nginx/html:ro\n      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro\n    healthcheck:\n      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/health >/dev/null 2>&1"]\n      interval: 15s\n      timeout: 5s\n      retries: 10\n    networks:\n      cloudif-publications:\n        aliases:\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web\n          - cloudif-p${CLOUDIF_PUBLIC_NUMBER}-active-web\nnetworks:\n  cloudif-publications:\n    external: true\n'''
 nginx='server { listen 80; root /usr/share/nginx/html; index index.html; location = /health { default_type application/json; return 200 \'{"ok":true}\'; } location / { try_files $uri $uri/ /index.html; } }\n'
 return [('README.md',f'# {title}\n\nPortal: {portal}\nForgejo: {forge}\nKomodo: {kom}\nSupabase: {sup}\nSite: {site}\n'),('site/index.html',html),('nginx.conf',nginx),('.env',f'CLOUDIF_PUBLIC_NUMBER={num}\nCLOUDIF_DEPLOY_NUMBER=1\n'),('docker-compose.yml',compose)]

def project_readme(slug,owner,tenant,num,runtime,php_version):
 node_version=runtime.replace('node','') if runtime.startswith('node') else '22'
 return f"""# {slug.replace('-', ' ').title()}

Projeto CloudIFF de **{owner}** com **Apache + PHP {php_version} + Node.js {node_version}**.

## Onde colocar o projeto

Todo o código da aplicação fica em `site/`:

- `site/index.php` é interpretado pelo PHP na raiz do domínio;
- `site/index.html`, CSS, JavaScript e imagens são servidos pelo Apache;
- `site/api/server.js` implementa APIs Node disponíveis em `/api/`;
- outras pastas dentro de `site/` pertencem livremente ao projeto.

Você pode apagar o conteúdo de exemplo de `site/` e colocar seu sistema real.

## Estrutura do repositório

| Caminho | Finalidade | O usuário deve editar? |
|---|---|---|
| `site/` | Código da aplicação, páginas PHP, HTML, CSS, JavaScript, imagens e APIs Node. | **Sim.** É a área normal de trabalho. |
| `site/index.php` | Página inicial PHP, interpretada pelo Apache. | **Sim.** Pode ser substituída pelo sistema real. |
| `site/api/server.js` | Processo Node opcional, publicado por `/api/`. | **Sim.** Pode ser alterado ou removido quando não houver API Node. |
| `site/api/package.json` | Dependências da API Node. | **Sim.** Adicione as bibliotecas necessárias. |
| `.cloudif/` | Dockerfile, Compose, Apache, Supervisor, healthcheck, versões e metadados. | **Não normalmente.** É infraestrutura gerenciada pela plataforma. |
| `README.md` | Manual do projeto. | **Sim.** Pode receber documentação adicional. |

## Infraestrutura gerenciada

A pasta oculta `.cloudif/` contém Dockerfile, Compose, Apache, Supervisor, healthcheck e metadados de runtime. A plataforma mantém essa pasta. Alterações avançadas são possíveis, mas podem quebrar build, saúde ou publicação automática.

Arquivos em `.cloudif/` não são exemplos descartáveis. Eles formam o contrato de execução do projeto. O usuário pode personalizá-los somente quando souber preservar porta 80, serviço `web`, healthcheck, rede e aliases de publicação.

## Publicação automática

1. Edite `site/`.
2. Faça commit e push na branch `main`.
3. O Forgejo envia o webhook.
4. O Komodo reconstrói o container isolado do projeto.
5. A CloudIFF valida o healthcheck e publica por HTTPS.

Site: https://{num}.cloudiff.duckdns.org/
Forgejo: https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}
Supabase: https://{tenant}.cloudiff.duckdns.org/project/default

## Contrato da plataforma

- Apache atende internamente na porta 80;
- o proxy público atende HTTP 80 e HTTPS 443, terminando TLS no Nginx;
- PHP interpreta arquivos dentro de `site/`;
- Node executa `site/api/server.js` em `127.0.0.1:3000`;
- Apache encaminha `/api/` para o processo Node;
- o serviço público se chama `web` e participa da rede `cloudif-publications`;
- segredos não devem ser enviados ao Git.

A imagem-base compartilhada desta combinação é `cloudif/runtime-apache-php{php_version}-node{node_version}:v1`. O container final continua exclusivo deste projeto.
"""


def runtime_overlay(template,php_version='8.3'):
 template=(template or 'node22').strip().lower()
 php_version=str(php_version or '8.3').strip()
 if php_version not in ('8.2','8.3','8.4'):
  raise ValueError('unsupported_php_version')
 if template not in ('node20','node22','node24'):
  template='node22'
 node_version=template.replace('node','')
 base_tag=f'cloudif/runtime-apache-php{php_version}-node{node_version}:v1'
 base=f"""FROM php:{php_version}-apache
ARG NODE_MAJOR={node_version}
RUN apt-get update \\
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg supervisor libpq-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libzip-dev libicu-dev default-mysql-client postgresql-client unzip git \\
 && curl -fsSL https://deb.nodesource.com/setup_${{NODE_MAJOR}}.x | bash - \\
 && apt-get install -y --no-install-recommends nodejs \\
 && docker-php-ext-configure gd --with-freetype --with-jpeg \\
 && docker-php-ext-install -j\"$(nproc)\" pdo pdo_mysql mysqli pdo_pgsql pgsql gd intl zip opcache \\
 && a2enmod rewrite headers proxy proxy_http expires \\
 && rm -rf /var/lib/apt/lists/*
COPY .cloudif/apache-vhost.conf /etc/apache2/sites-available/000-default.conf
COPY .cloudif/supervisor.conf /etc/supervisor/conf.d/cloudif.conf
COPY .cloudif/node-runner.sh /usr/local/bin/cloudif-node-runner
COPY .cloudif/health.php /opt/cloudif/health.php
RUN chmod 0755 /usr/local/bin/cloudif-node-runner
EXPOSE 80
CMD [\"/usr/bin/supervisord\",\"-n\",\"-c\",\"/etc/supervisor/supervisord.conf\"]
"""
 docker=f"""FROM {base_tag}
COPY site/ /var/www/html/
WORKDIR /var/www/html
RUN if [ -f api/package-lock.json ]; then cd api && npm ci --omit=dev; elif [ -f api/package.json ]; then cd api && npm install --omit=dev; fi \\
 && chown -R www-data:www-data /var/www/html
"""
 apache="""<VirtualHost *:80>
  DocumentRoot /var/www/html
  DirectoryIndex index.php index.html
  <Directory /var/www/html>
    AllowOverride All
    Options FollowSymLinks
    Require all granted
  </Directory>
  Alias /.cloudif-health /opt/cloudif/health.php
  <Location /.cloudif-health>
    Require all granted
  </Location>
  ProxyPreserveHost On
  ProxyPass /api/ http://127.0.0.1:3000/
  ProxyPassReverse /api/ http://127.0.0.1:3000/
  SetEnvIf X-Forwarded-Proto https HTTPS=on
  ErrorLog ${APACHE_LOG_DIR}/error.log
  CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
"""
 supervisor="""[supervisord]
nodaemon=true
user=root

[program:apache]
command=/usr/sbin/apache2ctl -D FOREGROUND
autostart=true
autorestart=true
priority=10
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0

[program:node]
command=/usr/local/bin/cloudif-node-runner
autostart=true
autorestart=true
startsecs=2
priority=20
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0
"""
 runner="""#!/bin/sh
set -eu
cd /var/www/html
if [ -f api/server.js ]; then
  cd api
  export HOST=127.0.0.1 PORT=3000 NODE_ENV=${NODE_ENV:-production}
  exec node server.js
fi
exec sh -c 'while :; do sleep 3600; done'
"""
 health="<?php header('Content-Type: application/json'); echo json_encode(['ok'=>true,'php'=>PHP_VERSION]);"
 compose=f"""services:
  web:
    image: cloudif/project-${{CLOUDIF_PUBLIC_NUMBER}}:php{php_version}-node{node_version}
    build:
      context: ..
      dockerfile: .cloudif/Dockerfile
    container_name: cloudif-p${{CLOUDIF_PUBLIC_NUMBER}}-d${{CLOUDIF_DEPLOY_NUMBER}}-web
    restart: unless-stopped
    healthcheck:
      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1/.cloudif-health >/dev/null\"]
      interval: 15s
      timeout: 5s
      retries: 12
      start_period: 30s
    networks:
      cloudif-publications:
        aliases:
          - cloudif-p${{CLOUDIF_PUBLIC_NUMBER}}-d${{CLOUDIF_DEPLOY_NUMBER}}-web
          - cloudif-p${{CLOUDIF_PUBLIC_NUMBER}}-active-web
networks:
  cloudif-publications:
    external: true
"""
 runtime=json.dumps({'schema':1,'apache':'2.4','php':php_version,'node':node_version,'base_image':base_tag,'compose_file':'.cloudif/docker-compose.yml'},ensure_ascii=False,indent=2)+'\n'
 return [
  ('.cloudif/Dockerfile.base',base),
  ('.cloudif/Dockerfile',docker),
  ('.cloudif/apache-vhost.conf',apache),
  ('.cloudif/supervisor.conf',supervisor),
  ('.cloudif/node-runner.sh',runner),
  ('.cloudif/health.php',health),
  ('.cloudif/docker-compose.yml',compose),
  ('.cloudif/runtime.json',runtime),
  ('site/index.php',f"<?php echo '<h1>CloudIFF</h1><p>Apache + PHP {php_version} + Node.js {node_version}</p>';"),
  ('site/api/server.js',"const http=require('http');const port=Number(process.env.PORT||3000);http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,node:process.version,path:req.url}))}).listen(port,'127.0.0.1');\n"),
  ('site/api/package.json','{"name":"cloudif-api","private":true,"scripts":{"start":"node server.js"}}\n')]


def merge_runtime(files,template,php_version="8.3"):
 overlay=runtime_overlay(template,php_version)
 env=next((content for name,content in files if name=='.env'),'CLOUDIF_PUBLIC_NUMBER=1001\nCLOUDIF_DEPLOY_NUMBER=1\n')
 keep=[(name,content) for name,content in files if name.startswith('site/') and name!='site/index.html']
 return keep+overlay+[('.cloudif/.env',env)]

def main():
 job=json.loads(Path(sys.argv[1]).read_text()); kind=job.get('template_kind','none'); runtime=job.get('runtime_template','node22'); php_version=job.get('php_version','8.3')
 if kind not in ('onboarding','links'): print({'skipped':True,'kind':kind}); return
 slug=job['slug']; owner=(job.get('user') or {}).get('username',''); tenant=job['tenant']; num=public_number(slug)
 marker=Path(f'/srv/cloudif/provisioning/projects/{slug}/template-applied.json')
 if marker.exists():
  try:
   old_marker=json.loads(marker.read_text())
   if old_marker.get('kind')==kind and old_marker.get('runtime_template')==runtime and old_marker.get('php_version','8.3')==php_version and old_marker.get('version')==9:
    print(json.dumps({'ok':True,'skipped':True,'reason':'template_already_applied','kind':kind,'project':slug,'public_number':num},ensure_ascii=False)); return
  except Exception: pass
 cfg=read_env('/etc/cloudif/forja-agent-client.env'); base=(cfg.get('FORJA_AGENT_URL') or 'http://10.62.91.2:18095').rstrip('/'); tok=cfg.get('FORJA_AGENT_TOKEN','')
 if not tok: raise SystemExit('missing_forja_token')
 results=[]
 files=merge_runtime(build(kind,slug,owner,tenant,num),runtime,php_version)
 files=[(path,content) for path,content in files if path!='README.md']+[('README.md',project_readme(slug,owner,tenant,num,runtime,php_version))]
 for path,content in files:
  payload={'project_slug':slug,'owner':owner,'repo_owner':owner,'repo':f'cloudif-{slug}','repo_path':f'{owner}/cloudif-{slug}','path':path,'branch':'main','message':f'CloudIF: aplicar template {kind} ({path})','source':'project-template-automation','content_b64':base64.b64encode(content.encode()).decode()}
  last=None
  for i in range(10):
   try:last=post(base+'/project/file/commit',tok,payload); break
   except Exception as e:last={'ok':False,'error':str(e)}; time.sleep(5)
  if not last or not last.get('ok'): raise RuntimeError(f'commit_failed:{path}:{last}')
  results.append({'path':path,'commit':last.get('commit_sha','')})
 marker.parent.mkdir(parents=True,exist_ok=True)
 marker.write_text(json.dumps({'kind':kind,'runtime_template':runtime,'php_version':php_version,'version':9,'project':slug,'public_number':num,'applied_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'files':results},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'ok':True,'kind':kind,'project':slug,'public_number':num,'files':results},ensure_ascii=False))
if __name__=='__main__': main()
