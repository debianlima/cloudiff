#!/usr/bin/env python3
import html,json,urllib.request
ROLE_LABELS={'viewer':'Visualizador','developer':'Desenvolvedor','maintainer':'Mantenedor','release-manager':'Gestor de releases','project-admin':'Administrador do projeto','test-operator':'Operador do ambiente de teste','custom':'Personalizado'}
APPROVAL_SCOPES={'approval:request-proposal':'Criar proposta de alteração','approval:request-merge':'Mesclar pull request','approval:request-deploy':'Validar deploy dry-run','approval:request-promote-test':'Promover ambiente isolado de teste'}
TOOL_GROUPS=(('Projeto',('project:',)),('Workspace',('workspace:',)),('Forgejo',('forgejo:',)),('Aprovações',('approval:',)),('Deploy',('deployment:',)))
def fetch(url,token):
 req=urllib.request.Request(url.rstrip('/')+'/v1/projects',headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r).get('projects',[])
def visible(rows,slugs):return [x for x in rows if x.get('project_slug') in slugs]
def badge(status):
 cls='ok' if status=='ready' else ('muted' if status in ('planned','not_applicable') else 'bad')
 return '<span class="pill '+cls+'">'+html.escape(str(status))+'</span>'
def role_badge(role):return '<span class="pill ok">'+html.escape(ROLE_LABELS.get(role,role))+'</span>'
def permission_summary(scopes):
 out=[]
 for label,prefixes in TOOL_GROUPS:
  count=sum(1 for s in scopes if any(s.startswith(p) for p in prefixes))
  if count:out.append('<div class="box"><b>'+html.escape(label)+'</b><div class="kpi">'+str(count)+'</div><span class="small">permissões</span></div>')
 return ''.join(out)
def approval_list(scopes):
 rows=['<li>'+html.escape(label)+'</li>' for scope,label in APPROVAL_SCOPES.items() if scope in scopes]
 return ''.join(rows) or '<li>Nenhuma solicitação de aprovação disponível.</li>'
def blocked_list(scopes):
 rows=[]
 if 'deployment:promote-test' not in scopes:rows.append('Promoção real no ambiente isolado de teste')
 rows.extend(['Deploy de produção','Aprovação automática','Push direto em main','Terminal arbitrário','Seleção livre de repositório'])
 return ''.join('<li>'+html.escape(x)+'</li>' for x in rows)
def render(rows,csrf_token=""):
 cards=[]
 for x in rows:
  c=x.get('connectors') or {};ins=x.get('instructions') or {};headers=ins.get('example_headers') or {};scopes=list(x.get('scopes') or []);role=str(x.get('role_profile') or ins.get('role_profile') or 'custom');environment='isolated-test' if role=='test-operator' else 'project'
  conn=''.join('<div class="box"><b>'+html.escape(str(k))+'</b><br>'+badge((v or {}).get('status','unknown'))+'</div>' for k,v in c.items())
  scope_html=''.join('<li><code>'+html.escape(str(v))+'</code></li>' for v in scopes)
  auth='Authorization: '+headers.get('Authorization','Bearer <TOKEN_DO_PROJETO>');client='X-CloudIF-Client: '+headers.get('X-CloudIF-Client',x.get('client_id',''))
  card='<article class="project-card"><div class="section-title"><div><h3>'+html.escape(str(x.get('project_slug')))+'</h3><p class="small">Ambiente permitido: <code>'+html.escape(environment)+'</code></p></div>'+role_badge(role)+'</div>'
  card+='<p><b>Identidade:</b> <code>'+html.escape(str(x.get('client_id')))+'</code></p><div class="grid">'+conn+'</div>'
  card+='<h4>Permissões efetivas</h4><div class="backup-summary">'+permission_summary(scopes)+'</div>'
  card+='<details><summary>Operações que exigem aprovação humana</summary><ul>'+approval_list(scopes)+'</ul></details>'
  card+='<details><summary>Operações bloqueadas</summary><ul>'+blocked_list(scopes)+'</ul><p><span class="pill bad">Produção desabilitada</span></p></details>'
  card+='<details><summary>Como conectar as ferramentas</summary><p>Endpoint MCP: <code>'+html.escape(str(ins.get('mcp_endpoint')))+'</code></p><div class="terminal-box"><div>'+html.escape(auth)+'</div><div>'+html.escape(client)+'</div></div><p class="small">'+html.escape(str(ins.get('secret_delivery')))+'</p><button type="button" class="btn secondary oi-rotate" data-slug="'+html.escape(str(x.get('project_slug')),quote=True)+'">Rotacionar e exibir uma vez</button></details>'
  card+='<details><summary>Escopos técnicos</summary><ul>'+scope_html+'</ul></details></article>';cards.append(card)
 script='''<script>(function(){const csrf='''+json.dumps(csrf_token)+''';document.querySelectorAll('.oi-rotate').forEach(btn=>btn.addEventListener('click',async()=>{if(!confirm('A credencial atual será invalidada imediatamente. Continuar?'))return;btn.disabled=true;try{const body=new URLSearchParams({csrf_token:csrf,slug:btn.dataset.slug,reason:'Rotação solicitada pelo painel do projeto'});const r=await fetch('/cloudiff/portal/action/rotate-project-credential',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const d=await r.json();if(!r.ok)throw new Error(d.error||'Falha na rotação');const value='Authorization: Bearer '+d.token+'\nX-CloudIF-Client: '+d.client_id;prompt('Copie agora. Esta credencial não será exibida novamente.',value)}catch(e){alert(e.message)}finally{btn.disabled=false}}))})();</script>'''
 return '<section class="card" id="project-identities"><div class="section-title"><div><h2>Identidades, funções e conexões</h2><p class="small">Geradas automaticamente para cada projeto. Funções e escopos são aplicados no servidor; a credencial só aparece uma vez após rotação autenticada.</p></div></div><div class="grid">'+(''.join(cards) or '<div class="box">Nenhuma identidade visível.</div>')+'</div></section>'+script
