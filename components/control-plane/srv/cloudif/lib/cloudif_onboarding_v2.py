#!/usr/bin/env python3
"""Código inicial publicado em todo projeto novo da CloudIFF."""
from html import escape


def build_onboarding_v2(slug, owner, tenant, num):
    slug = str(slug or "projeto")
    owner = str(owner or "usuario")
    tenant = str(tenant or "")
    number = int(num)

    portal = "https://cloudiff.duckdns.org/cloudiff/portal/?tab=publicacao"
    repo_web = f"https://cloudiff.duckdns.org/git/{owner}/cloudif-{slug}"
    repo_clone = repo_web + ".git"
    site = f"https://{number}.cloudiff.duckdns.org/"
    version = f"https://{number}-d1.cloudiff.duckdns.org/"
    supabase_url = f"https://{tenant}.cloudiff.duckdns.org" if tenant else ""
    studio = supabase_url + "/project/default" if supabase_url else ""

    supabase_status = (
        f'<a href="{escape(studio)}">Abrir Supabase Studio</a>'
        if studio else
        '<span>Este projeto foi criado sem tenant. Vincule um banco pelo Portal para habilitar a API.</span>'
    )
    supabase_value = escape(supabase_url or "https://<tenant>.cloudiff.duckdns.org")

    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escape(slug)} · primeiros passos</title>
  <style>
    :root{{--ink:#142019;--muted:#5d6a62;--paper:#f4f6f3;--surface:#fff;--rule:#dce3dc;--accent:#168821;--accent-dark:#0d6418;--code:#101914}}
    *{{box-sizing:border-box}}
    body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
    a{{color:var(--accent-dark);font-weight:700;text-underline-offset:3px}}
    header,main,footer{{width:min(1040px,calc(100% - 40px));margin:auto}}
    header{{padding:72px 0 42px;border-bottom:1px solid var(--rule)}}
    .eyebrow{{margin:0 0 10px;color:var(--accent-dark);font-size:.78rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}}
    h1{{max-width:760px;margin:0;font-size:clamp(2.2rem,7vw,4.6rem);line-height:1;letter-spacing:-.055em}}
    header>p:last-of-type{{max-width:680px;margin:22px 0 0;color:var(--muted);font-size:1.08rem}}
    nav{{display:flex;gap:18px;flex-wrap:wrap;margin-top:26px}}
    main{{padding:46px 0 72px}}
    section{{padding:34px 0;border-bottom:1px solid var(--rule)}}
    section:first-child{{padding-top:0}}
    h2{{margin:0 0 10px;font-size:clamp(1.45rem,3vw,2rem);letter-spacing:-.025em}}
    h3{{margin:0 0 7px;font-size:1rem}}
    p{{margin:0 0 16px}}
    .lead{{max-width:720px;color:var(--muted)}}
    .grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:22px}}
    article{{min-width:0;padding:22px;background:var(--surface);border:1px solid var(--rule);border-radius:12px}}
    article p,li{{color:var(--muted)}}
    ol,ul{{margin:14px 0 0;padding-left:22px}}
    li+li{{margin-top:8px}}
    pre{{margin:14px 0 0;padding:16px;background:var(--code);color:#e8f5ea;border-radius:10px;overflow:auto;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}
    code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
    .address{{display:block;margin-top:10px;padding:12px;background:#eef4ef;border-radius:8px;overflow-wrap:anywhere}}
    .note{{margin-top:18px;padding:16px;border-left:3px solid var(--accent);background:var(--surface)}}
    .button{{display:inline-flex;padding:10px 14px;border-radius:8px;background:var(--accent);color:#fff;text-decoration:none}}
    footer{{padding:25px 0 42px;color:var(--muted);font-size:.88rem}}
    @media(max-width:720px){{header,main,footer{{width:min(100% - 28px,1040px)}}header{{padding-top:45px}}.grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <header>
    <p class="eyebrow">CloudIFF · publicação d1</p>
    <h1>Seu projeto está publicado.</h1>
    <p>Esta é a página inicial de <strong>{escape(slug)}</strong>. Substitua o código da raiz do repositório e publique uma nova versão pelo Portal.</p>
    <nav aria-label="Acessos do projeto">
      <a href="{escape(portal)}">Publicações</a>
      <a href="{escape(repo_web)}">Forgejo</a>
      {supabase_status}
      <a href="{escape(version)}">Abrir d1</a>
    </nav>
  </header>
  <main>
    <section>
      <h2>1. Publique seu código</h2>
      <p class="lead">A raiz do repositório é a raiz da aplicação. Não crie a pasta <code>site/</code> e não envie Dockerfile, Compose, <code>.env</code> ou segredos.</p>
      <ol>
        <li>Clone o repositório e edite <code>index.html</code> ou <code>index.php</code>.</li>
        <li>Faça commit e push na branch <code>main</code>.</li>
        <li>Abra <strong>Portal → Publicações</strong> e selecione <strong>Publicar nova versão</strong>.</li>
        <li>Confira a URL imutável da nova <code>dN</code> e use <strong>Ativar esta versão</strong>.</li>
      </ol>
      <p class="note">Cada publicação recebe stack, imagem, container, URL e terminais próprios. A versão anterior permanece disponível para retorno.</p>
    </section>

    <section>
      <h2>2. Clone pelo Forgejo HTTPS</h2>
      <p class="lead">Use seu usuário do Forgejo e um token pessoal quando o Git solicitar a senha. Não coloque o token no endereço do repositório.</p>
      <div class="grid">
        <article>
          <h3>Linux</h3>
          <pre>git clone {escape(repo_clone)}
cd cloudif-{escape(slug)}
git config user.name "Seu nome"
git config user.email "seu.email@iff.edu.br"</pre>
          <p>Depois de editar:</p>
          <pre>git add .
git commit -m "Atualizar aplicação"
git push origin main</pre>
        </article>
        <article>
          <h3>Windows · PowerShell</h3>
          <pre>git config --global credential.helper manager
git clone {escape(repo_clone)}
Set-Location cloudif-{escape(slug)}</pre>
          <p>Depois de editar:</p>
          <pre>git add .
git commit -m "Atualizar aplicação"
git push origin main</pre>
        </article>
      </div>
      <code class="address">{escape(repo_clone)}</code>
    </section>

    <section>
      <h2>3. Conecte uma aplicação desktop ao Supabase</h2>
      <p class="lead">Aplicações desktop devem usar a API HTTPS e uma chave publicável/anon. Nunca distribua a chave <code>service_role</code> ou uma chave secreta dentro do aplicativo.</p>
      <code class="address">{supabase_value}</code>
      <div class="grid">
        <article>
          <h3>Electron ou JavaScript</h3>
          <pre>npm install @supabase/supabase-js</pre>
          <pre>import {{ createClient }} from '@supabase/supabase-js'

const supabase = createClient(
  '{supabase_value}',
  'SUA_CHAVE_PUBLICAVEL'
)

const {{ data, error }} = await supabase
  .from('sua_tabela')
  .select('*')</pre>
        </article>
        <article>
          <h3>Python · Tkinter, PySide ou outro desktop</h3>
          <pre>python -m pip install requests</pre>
          <pre>import requests

url = '{supabase_value}/rest/v1/sua_tabela'
key = 'SUA_CHAVE_PUBLICAVEL'
response = requests.get(
    url,
    params={{'select': '*'}},
    headers={{
        'apikey': key,
        'Authorization': f'Bearer {{key}}',
    }},
    timeout=30,
)
response.raise_for_status()
print(response.json())</pre>
        </article>
      </div>
      <p class="note">Crie as tabelas e políticas RLS no Supabase Studio. Métodos de conexão não apresentados nesta página devem ser verificados com a TI.</p>
    </section>

    <section>
      <h2>Endereços desta publicação</h2>
      <div class="grid">
        <article><h3>Endereço ativo</h3><a href="{escape(site)}">{escape(site)}</a></article>
        <article><h3>Versão imutável d1</h3><a href="{escape(version)}">{escape(version)}</a></article>
      </div>
    </section>
  </main>
  <footer>CloudIFF · código-fonte no Forgejo, runtime gerenciado fora do repositório.</footer>
</body>
</html>'''
    return [('site/index.html', html)]
