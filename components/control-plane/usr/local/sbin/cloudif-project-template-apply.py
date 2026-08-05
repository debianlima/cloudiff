#!/usr/bin/env python3
import base64
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

LIB = Path('/srv/cloudif/lib')
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

DB = '/var/lib/cloudif/portal/cloudif-portal.db'
PLATFORM_NAMES = {
    'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml',
    'Dockerfile', 'Dockerfile.runtime', 'nginx.conf', '.env',
    'apache-vhost.conf', 'supervisor.conf', 'node-runner.sh',
    'health.php', 'runtime.json',
}


def read_env(path):
    data = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                data[key.strip()] = value.strip().strip('"\'')
    return data


def post(url, token, payload, timeout=90):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-CloudIF-Token': token,
            'Authorization': 'Bearer ' + token,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b'{}')


def public_number(slug):
    con = sqlite3.connect(DB)
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    con.execute(
        'CREATE TABLE IF NOT EXISTS project_public_ids('
        'project_slug TEXT PRIMARY KEY,public_number INTEGER NOT NULL UNIQUE,'
        'created_at TEXT NOT NULL,updated_at TEXT NOT NULL)'
    )
    row = con.execute(
        'select public_number from project_public_ids where project_slug=?',
        (slug,),
    ).fetchone()
    if row:
        number = int(row[0])
    else:
        number = int(con.execute(
            'select coalesce(max(public_number),1000)+1 from project_public_ids'
        ).fetchone()[0])
        con.execute(
            'insert into project_public_ids values(?,?,?,?)',
            (slug, number, now, now),
        )
        con.commit()
    con.close()
    return number


def build(kind, slug, owner, tenant, number):
    if kind == 'onboarding':
        from cloudif_onboarding_v2 import build_onboarding_v2
        return build_onboarding_v2(slug, owner, tenant, number)

    portal = 'https://cloudiff.duckdns.org/'
    forgejo = f'https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}'
    komodo = 'https://komodoiff.duckdns.org/'
    supabase = f'https://{tenant}.cloudiff.duckdns.org/project/default'
    site = f'https://{number}.cloudiff.duckdns.org/'
    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Projeto CloudIFF</title>
  <style>
    body{{margin:0;font:16px system-ui;background:#f6f7f6;color:#18221c}}
    main{{max-width:860px;margin:auto;padding:12vh 24px}}
    nav{{display:flex;gap:10px;flex-wrap:wrap}}
    a{{color:#166534;font-weight:700}}
  </style>
</head>
<body>
  <main>
    <small>CloudIFF</small>
    <h1>Projeto CloudIFF</h1>
    <p>Projeto {slug} de {owner}.</p>
    <nav>
      <a href="{portal}">Portal</a>
      <a href="{forgejo}">Forgejo</a>
      <a href="{komodo}">Komodo</a>
      <a href="{supabase}">Supabase</a>
      <a href="{site}">Site</a>
    </nav>
  </main>
</body>
</html>
'''
    return [('index.html', html)]


def project_readme(slug, owner, tenant, number, runtime, php_version):
    node_version = runtime.replace('node', '') if runtime.startswith('node') else '22'
    return f'''# {slug.replace('-', ' ').title()}

Código-fonte do projeto CloudIFF de **{owner}**.

## Estrutura

A raiz deste repositório é a raiz da aplicação publicada. Exemplos:

- `index.php` ou `index.html`: página inicial;
- `api/server.js`: API Node.js opcional, publicada em `/api/`;
- `api/package.json`: dependências da API;
- demais pastas: CSS, JavaScript, imagens e código da aplicação.

Não existe uma subpasta `site/`. O conteúdo que estiver na raiz será usado para gerar cada publicação imutável.

## Infraestrutura gerenciada

Compose, Dockerfile, Apache, Supervisor, healthcheck, imagens e metadados de runtime são gerados pela CloudIFF fora do Git. Não adicione segredos, `.env` ou arquivos de infraestrutura da plataforma ao repositório.

Runtime selecionado: Apache + PHP {php_version} + Node.js {node_version}.

## Fluxo

1. Edite o código na raiz.
2. Faça commit e push na `main`.
3. Crie uma publicação no Portal.
4. Cada versão `d1`, `d2`, `d3` recebe stack, imagem, container e terminal próprios.
5. Ativar uma versão altera apenas o alias estável; as demais versões permanecem independentes e podem ser reconstruídas pelo commit registrado.

Site: https://{number}.cloudiff.duckdns.org/
Forgejo: https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}
Supabase: https://{tenant}.cloudiff.duckdns.org/project/default
'''


def runtime_overlay(template, php_version='8.3'):
    template = (template or 'node22').strip().lower()
    php_version = str(php_version or '8.3').strip()
    if template not in ('node20', 'node22', 'node24'):
        template = 'node22'
    if php_version not in ('8.2', '8.3', '8.4'):
        raise ValueError('unsupported_php_version')
    return [
        (
            'api/server.js',
            "const http=require('http');"
            "const port=Number(process.env.PORT||3000);"
            "http.createServer((req,res)=>{"
            "res.setHeader('Content-Type','application/json');"
            "res.end(JSON.stringify({ok:true,node:process.version,path:req.url}))"
            "}).listen(port,'127.0.0.1');\n",
        ),
        (
            'api/package.json',
            '{"name":"cloudif-api","private":true,'
            '"scripts":{"start":"node server.js"}}\n',
        ),
    ]


def _source_path(name):
    name = str(name or '').strip().lstrip('/')
    if name.startswith('site/'):
        name = name[5:]
    if not name or name.startswith('.cloudif/') or name in PLATFORM_NAMES:
        return ''
    if name.startswith('../') or '/..' in name:
        return ''
    return name


def merge_runtime(files, template, php_version='8.3'):
    merged = {}
    for name, content in files:
        target = _source_path(name)
        if target and target != 'README.md':
            merged[target] = content
    for name, content in runtime_overlay(template, php_version):
        merged.setdefault(name, content)
    if not any(name in merged for name in ('index.php', 'index.html')):
        merged['index.php'] = (
            "<?php echo '<h1>CloudIFF</h1>"
            "<p>Projeto pronto para receber seu código.</p>';"
        )
    return sorted(merged.items())


def main():
    job = json.loads(Path(sys.argv[1]).read_text())
    kind = job.get('template_kind', 'none')
    runtime = job.get('runtime_template', 'node22')
    php_version = job.get('php_version', '8.3')
    if kind not in ('onboarding', 'links'):
        print(json.dumps({'skipped': True, 'kind': kind}))
        return

    slug = job['slug']
    owner = (job.get('user') or {}).get('username', '')
    tenant = job['tenant']
    number = public_number(slug)
    state_dir = Path(f'/srv/cloudif/provisioning/projects/{slug}')
    marker = state_dir / 'template-applied.json'
    if marker.exists():
        try:
            old = json.loads(marker.read_text())
            if (
                old.get('kind') == kind
                and old.get('runtime_template') == runtime
                and old.get('php_version', '8.3') == php_version
                and old.get('version') == 10
            ):
                print(json.dumps({
                    'ok': True,
                    'skipped': True,
                    'reason': 'template_already_applied',
                    'kind': kind,
                    'project': slug,
                    'public_number': number,
                }, ensure_ascii=False))
                return
        except Exception:
            pass

    config = read_env('/etc/cloudif/forja-agent-client.env')
    base = (config.get('FORJA_AGENT_URL') or 'http://10.62.91.2:18095').rstrip('/')
    token = config.get('FORJA_AGENT_TOKEN', '')
    if not token:
        raise SystemExit('missing_forja_token')

    files = merge_runtime(build(kind, slug, owner, tenant, number), runtime, php_version)
    files.append((
        'README.md',
        project_readme(slug, owner, tenant, number, runtime, php_version),
    ))
    results = []
    for path, content in files:
        payload = {
            'project_slug': slug,
            'owner': owner,
            'repo_owner': owner,
            'repo': f'cloudif-{slug}',
            'repo_path': f'{owner}/cloudif-{slug}',
            'path': path,
            'branch': 'main',
            'message': f'CloudIFF: adicionar código inicial ({path})',
            'source': 'project-template-automation',
            'content_b64': base64.b64encode(content.encode()).decode(),
        }
        last = None
        for _ in range(10):
            try:
                last = post(base + '/project/file/commit', token, payload)
                break
            except Exception as exc:
                last = {'ok': False, 'error': type(exc).__name__}
                time.sleep(5)
        if not last or not last.get('ok'):
            raise RuntimeError(f'commit_failed:{path}:{last}')
        results.append({'path': path, 'commit': last.get('commit_sha', '')})

    state_dir.mkdir(parents=True, exist_ok=True)
    runtime_meta = {
        'schema': 2,
        'layout': 'managed-root-v1',
        'runtime_template': runtime,
        'php_version': php_version,
        'node_version': runtime.replace('node', ''),
        'repository_root': 'application',
        'infrastructure_in_git': False,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    (state_dir / 'managed-runtime.json').write_text(
        json.dumps(runtime_meta, ensure_ascii=False, indent=2) + '\n'
    )
    marker.write_text(json.dumps({
        'kind': kind,
        'runtime_template': runtime,
        'php_version': php_version,
        'version': 10,
        'project': slug,
        'public_number': number,
        'applied_at': runtime_meta['updated_at'],
        'files': results,
    }, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'ok': True,
        'kind': kind,
        'project': slug,
        'public_number': number,
        'files': results,
        'runtime': runtime_meta,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
