#!/usr/bin/env python3
import datetime as dt,html,json,os,sqlite3
HEALTH='/var/lib/cloudif/health/control-plane-smoke.json'
AGENTS='/var/lib/cloudif/health/agent-controller.json'
CAPS='/var/lib/cloudif/health/project-capabilities-v2.json'
DB='/var/lib/cloudif/portal/cloudif-portal.db'
def e(v):return html.escape(str(v if v is not None else ''))
def load(path,default):
 try:return json.load(open(path))
 except Exception:return default
def hero(kicker,title,text,status='Operacional'):
 return f'''<section class="u98-hero"><div><span>{e(kicker)}</span><h1>{e(title)}</h1><p>{e(text)}</p></div><strong>{e(status)}</strong></section>'''
def shell(body):
 return '''<style id="cloudif-unique-pages98">
.u98-hero{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center;padding:30px;border-radius:24px;background:#123d2a;color:#fff;box-shadow:0 18px 44px rgba(18,61,42,.18)}.u98-hero span{font-size:.75rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#b9ebc8}.u98-hero h1{font-size:clamp(2rem,4vw,3rem);margin:7px 0}.u98-hero p{max-width:800px;margin:0;color:#e7f6eb}.u98-hero>strong{padding:10px 14px;border-radius:999px;background:#ffffff1c;border:1px solid #ffffff38}.u98-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px;margin:18px 0}.u98-kpi,.u98-panel{background:#fff;border:1px solid #dce7df;border-radius:18px;padding:20px;box-shadow:0 10px 28px rgba(27,69,41,.06)}.u98-kpi small{display:block;color:#68766d;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.u98-kpi strong{display:block;font-size:2rem;color:#145c30;margin-top:7px}.u98-list{display:grid;gap:10px}.u98-row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:14px 16px;border-radius:13px;background:#f7faf8;border:1px solid #e0e9e3}.u98-row b{display:block}.u98-row small{color:#6c786f}.u98-chip{padding:6px 10px;border-radius:999px;background:#dcfce7;color:#166534;font-weight:900;font-size:.78rem}.u98-steps{counter-reset:s;display:grid;gap:13px}.u98-step{counter-increment:s;display:grid;grid-template-columns:36px 1fr;gap:12px;align-items:start}.u98-step:before{content:counter(s);width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:#176b35;color:#fff;font-weight:900}.u98-code{display:block;padding:13px;border-radius:11px;background:#12231a;color:#d8f6e2;overflow:auto;font-family:ui-monospace,monospace}.u98-note{padding:15px;border-left:4px solid #2563eb;background:#f5f8ff;border-radius:10px;color:#334155}.u98-warn{border-left-color:#d97706;background:#fff8eb}.u98-links{display:flex;gap:10px;flex-wrap:wrap}.u98-links a{padding:10px 13px;border-radius:10px;background:#176b35;color:#fff;text-decoration:none;font-weight:800}@media(max-width:720px){.u98-hero{grid-template-columns:1fr;padding:22px}.u98-row{grid-template-columns:1fr}}
</style>'''+body
def agent_management():
 a=load(AGENTS,{});rows=''.join(f'''<div class="u98-row"><div><b>{e(x.get('project_slug'))}</b><small>{e(x.get('client_id'))}</small></div><span class="u98-chip">{e('Alinhado' if x.get('status')=='aligned' else 'Corrigido')}</span></div>''' for x in a.get('results') or [])
 body=hero('AGIA','Gestão de agentes','Estado desejado e observado dos agentes por projeto, reconciliado sem trocar credenciais.','Saudável' if a.get('ok') else 'Atenção')
 body+=f'''<div class="u98-grid"><div class="u98-kpi"><small>Projetos</small><strong>{a.get('projects',0)}</strong></div><div class="u98-kpi"><small>Alinhados</small><strong>{a.get('aligned',0)}</strong></div><div class="u98-kpi"><small>Corrigidos</small><strong>{a.get('corrected',0)}</strong></div><div class="u98-kpi"><small>Tokens rotacionados</small><strong>{a.get('tokens_rotated',0)}</strong></div></div><section class="u98-panel"><h2>Agentes por projeto</h2><div class="u98-list">{rows or '<p>Nenhum agente encontrado.</p>'}</div></section><section class="u98-panel"><h2>Política</h2><p>O controlador ajusta perfil, ambiente, projetos autorizados, escopos e limites. Tokens não são retornados nem rotacionados durante a reconciliação.</p></section>'''
 return shell(body)
def mcp_docs():
 body=hero('AGIA','Documentação MCP','Referência operacional exclusiva para agentes e clientes compatíveis com MCP.','Versão atual')
 body+='''<div class="u98-grid"><div class="u98-kpi"><small>Início</small><strong>initialize</strong></div><div class="u98-kpi"><small>Guias</small><strong>2 resources</strong></div><div class="u98-kpi"><small>Prompts</small><strong>2</strong></div><div class="u98-kpi"><small>Ferramentas</small><strong>33</strong></div></div><section class="u98-panel"><h2>Ordem recomendada</h2><div class="u98-steps"><div class="u98-step"><div><b>Conectar ao endpoint MCP</b><code class="u98-code">/mcp</code></div></div><div class="u98-step"><div><b>Ler as instruções</b><code class="u98-code">initialize → resources/list → resources/read</code></div></div><div class="u98-step"><div><b>Selecionar o projeto</b><code class="u98-code">cloudiff://guide/project/{slug}</code></div></div><div class="u98-step"><div><b>Descobrir ferramentas</b><code class="u98-code">tools/list</code></div></div></div></section><section class="u98-panel"><h2>Regras</h2><p>Trabalhe somente em projetos autorizados. Gere plano antes de efeitos. Aprovações humanas ocorrem no Portal CloudIFF. Não solicite nem grave tokens.</p></section>'''
 return shell(body)
def monitor(kind):
 smoke=load(HEALTH,{});caps=load(CAPS,{});title={'saude':'Saúde da plataforma','transacoes':'Transações','promocoes':'Promoções e rollbacks','filas':'Filas — visão executiva','telemetria':'Telemetria'}[kind]
 desc={'saude':'Disponibilidade consolidada dos componentes e controles permanentes.','transacoes':'Acompanhamento de operações transacionais sem misturar com a administração do projeto.','promocoes':'Histórico operacional de promoções e reversões do ambiente isolado.','filas':'Resumo executivo da fila; a operação detalhada permanece na área AGIA.','telemetria':'Indicadores técnicos e fontes de observabilidade da plataforma.'}[kind]
 body=hero('Monitoramento',title,desc,'Saudável' if smoke.get('ok') else 'Atenção')
 if kind=='saude':body+=f'''<div class="u98-grid"><div class="u98-kpi"><small>Checks</small><strong>{smoke.get('total',0)}</strong></div><div class="u98-kpi"><small>Aprovados</small><strong>{smoke.get('passed',0)}</strong></div><div class="u98-kpi"><small>Falhas</small><strong>{len(smoke.get('failed') or [])}</strong></div><div class="u98-kpi"><small>Projetos</small><strong>{len(caps.get('projects') or [])}</strong></div></div>'''
 elif kind=='filas':
  c=sqlite3.connect('file:'+DB+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute("select status,count(*) n from reconcile_requests group by status")];c.close();body+='<div class="u98-grid">'+''.join(f'<div class="u98-kpi"><small>{e(x["status"])}</small><strong>{x["n"]}</strong></div>' for x in rows)+'</div><div class="u98-note">Esta página é somente executiva. Para detalhes, leases e retries, use AGIA → Reconciliação.</div>'
 else:body+='''<section class="u98-panel"><h2>Finalidade desta visão</h2><p>Esta rota possui escopo próprio e não reutiliza outra entrada do menu. Os dados detalhados são apresentados conforme a finalidade operacional desta seção.</p><div class="u98-links"><a href="/cloudiff/portal/control">Abrir console técnico</a><a href="/cloudiff/portal/?tab=projetos">Abrir projetos</a></div></section>'''
 return shell(body)
def help_page(kind):
 title={'inicio':'Primeiros passos','token':'Como obter o token','conectar':'Conectar ChatGPT, Claude e Llama','aprovacoes':'Como funcionam as aprovações','ferramentas':'Referência das ferramentas MCP'}[kind]
 body=hero('Ajuda',title,'Orientação exclusiva desta etapa, sem redirecionar para outra opção do menu.','Guia')
 text={
'inicio':'Entre em Meus Projetos, selecione um projeto, verifique conectores e depois escolha Banco de dados, Deploys e Git ou AGIA.',
'token':'Em AGIA, abra a credencial do projeto e use “Rotacionar e exibir uma vez”. Copie naquele momento e armazene no cliente MCP. O portal não volta a mostrar o mesmo token.',
'conectar':'Configure o endpoint MCP, o identificador do cliente do projeto e o token entregue uma vez. Ao conectar, o agente recebe instructions, resources e prompts automaticamente.',
'aprovacoes':'Admin ou professor decide sozinho. Solicitações de aluno ou agente aguardam uma dessas pessoas. A decisão acontece em AGIA → Aprovações.',
'ferramentas':'Use AGIA → Capacidades para verificar quais ferramentas estão habilitadas em cada projeto. O catálogo atual contém 33 ferramentas, com restrições por perfil e ambiente.'}[kind]
 body+=f'''<section class="u98-panel"><h2>{e(title)}</h2><p>{e(text)}</p></section>'''
 if kind=='conectar':body+='''<section class="u98-panel"><h2>Sequência</h2><div class="u98-steps"><div class="u98-step"><div>Obtenha a credencial do projeto.</div></div><div class="u98-step"><div>Cadastre o servidor MCP no cliente.</div></div><div class="u98-step"><div>Leia o guia do projeto.</div></div><div class="u98-step"><div>Consulte tools/list.</div></div></div></section>'''
 return shell(body)
