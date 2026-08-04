#!/usr/bin/env python3
import datetime as dt,html,json,os,sqlite3,subprocess
HEALTH='/var/lib/cloudif/health'
PORTAL='/var/lib/cloudif/portal/cloudif-portal.db'
ONBOARDING='/var/lib/cloudif/onboarding/onboarding.db'
AGENTS='/var/lib/cloudif/agents/agents.db'
def e(v):return html.escape(str(v if v is not None else ''))
def jload(path,default=None):
 try:return json.load(open(path))
 except Exception:return default if default is not None else {}
def dbcount(path,query,args=()):
 try:
  c=sqlite3.connect('file:'+path+'?mode=ro',uri=True,timeout=5);v=c.execute(query,args).fetchone()[0];c.close();return int(v or 0)
 except Exception:return 0
def active(unit):
 try:return subprocess.run(['systemctl','is-active',unit],text=True,capture_output=True,timeout=4).stdout.strip() or 'unknown'
 except Exception:return 'unknown'
def shell(title,eyebrow,intro,body,accent='green'):
 return f'''<style id="section98-style">.s98-hero{{padding:28px;border-radius:22px;background:#f7f9f8;border:1px solid #dbe5de;margin-bottom:18px}}.s98-hero[data-accent=blue]{{border-top:5px solid #2563eb}}.s98-hero[data-accent=green]{{border-top:5px solid #17803d}}.s98-hero[data-accent=amber]{{border-top:5px solid #d97706}}.s98-eyebrow{{font-size:.75rem;font-weight:900;text-transform:uppercase;letter-spacing:.12em;color:#176b35}}.s98-hero h1{{margin:6px 0 8px;font-size:clamp(1.9rem,4vw,2.8rem);letter-spacing:-.035em}}.s98-hero p{{margin:0;max-width:850px;color:#647268;font-size:1.02rem}}.s98-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}.s98-kpi{{padding:18px;border:1px solid #dbe5de;border-radius:16px;background:#fff}}.s98-kpi span{{display:block;color:#66756b;font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;font-weight:850}}.s98-kpi strong{{display:block;margin-top:6px;font-size:1.8rem;color:#154c2a}}.s98-list{{display:grid;gap:10px}}.s98-item{{display:grid;grid-template-columns:36px 1fr;gap:11px;padding:14px;border:1px solid #dbe5de;border-radius:14px;background:#fff}}.s98-icon{{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:#e9f4ec;color:#176b35;font-weight:900}}.s98-item h3,.s98-item p{{margin:0}}.s98-item p{{margin-top:4px;color:#69776e}}.s98-note{{padding:15px;border-left:4px solid #2563eb;background:#f8fafc;border-radius:10px;color:#334155}}.s98-code{{padding:13px;border-radius:12px;background:#111827;color:#e5e7eb;font-family:ui-monospace,monospace;overflow:auto}}@media(max-width:650px){{.s98-hero{{padding:21px}}}}</style><section class="s98-hero" data-accent="{accent}"><span class="s98-eyebrow">{e(eyebrow)}</span><h1>{e(title)}</h1><p>{e(intro)}</p></section>{body}'''
def cards(items):
 return '<section class="s98-list">'+''.join(f'<article class="s98-item"><span class="s98-icon">{e(i)}</span><div><h3>{e(t)}</h3><p>{e(d)}</p></div></article>' for i,t,d in items)+'</section>'
def agent_management():
 r=jload(HEALTH+'/project-state-reconcile.json',{});fallback=jload(HEALTH+'/agent-controller.json',{})
 projects=r.get('projects') or []
 if not projects:
  projects=[{'project_slug':x.get('project_slug'),'agent':'aligned' if x.get('status') in ('aligned','corrected') else x.get('status'),'onboarding':'ready','capabilities':'unknown','tool_count':0,'connectors':{},'overall':'attention','token_rotated':False} for x in fallback.get('results') or []]
  r={'ok':fallback.get('ok'),'projects_count':fallback.get('projects',0),'projects_ready':fallback.get('aligned',0),'agents_aligned':fallback.get('aligned',0),'capabilities_aligned':0,'catalog_tools':0,'execution_mode':'legacy','generated_at':fallback.get('generated_at'),'future_project_template':{'automatic_onboarding':True,'automatic_agent_identity':True,'automatic_capabilities':True,'production_effects_enabled':False},'projects':projects,'tokens_rotated':fallback.get('tokens_rotated',0)}
 rows=[]
 for x in projects:
  conn=x.get('connectors') or {};ready=sum(1 for v in conn.values() if v in ('ready','planned','not_applicable'));total=len(conn)
  detail=f"onboarding {x.get('onboarding','-')} · agente {x.get('agent','-')} · capacidades {x.get('capabilities','-')} · {x.get('tool_count',0)} ferramentas · conectores {ready}/{total}"
  rows.append(('✓' if x.get('overall')=='ready' else '!',x.get('project_slug') or '-',detail))
 future=r.get('future_project_template') or {}
 body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Projetos prontos</span><strong>{int(r.get('projects_ready') or 0)}/{int(r.get('projects_count') or 0)}</strong></div><div class="s98-kpi"><span>Agentes alinhados</span><strong>{int(r.get('agents_aligned') or 0)}</strong></div><div class="s98-kpi"><span>Capacidades alinhadas</span><strong>{int(r.get('capabilities_aligned') or 0)}</strong></div><div class="s98-kpi"><span>Tokens rotacionados</span><strong>{int(r.get('tokens_rotated') or 0)}</strong></div></section><div class="s98-note" style="margin:16px 0"><b>Reconciliação unificada:</b> {e(r.get('execution_mode') or 'desconhecida')} · última atualização {e(r.get('generated_at') or '-')}.</div>{cards(rows)}<section class="card"><h2>Novos projetos</h2><div class="s98-grid"><div class="s98-kpi"><span>Onboarding automático</span><strong>{'Sim' if future.get('automatic_onboarding') else 'Não'}</strong></div><div class="s98-kpi"><span>Identidade AGIA</span><strong>{'Automática' if future.get('automatic_agent_identity') else 'Manual'}</strong></div><div class="s98-kpi"><span>Capacidades</span><strong>{'Automáticas' if future.get('automatic_capabilities') else 'Manuais'}</strong></div><div class="s98-kpi"><span>Efeitos de produção</span><strong>{'Ativos' if future.get('production_effects_enabled') else 'Bloqueados'}</strong></div></div></section>'''
 return shell('Gestão de agentes','AGIA','Prontidão completa dos projetos atuais e do modelo aplicado aos projetos futuros.',body)

def mcp_docs():
 items=[('1','Descoberta automática','O cliente lê initialize.instructions, resources/list e prompts/list.'),('2','Guia do projeto','Leia cloudiff://guide/project/{slug} antes de chamar ferramentas.'),('3','Ferramentas','Consulte tools/list e respeite escopos, conectores e ambiente.'),('4','Aprovação','Operações protegidas são decididas no Portal CloudIFF.'),('5','Credenciais','O token é exibido uma vez e nunca deve ser enviado em prompts ou filas.')]
 body=cards(items)+'''<section class="card"><h2>Recursos MCP publicados</h2><div class="s98-code">cloudiff://guide/agent<br>cloudiff://guide/project/{slug}<br>cloudiff-project-workflow<br>cloudiff-production-policy</div></section>'''
 return shell('Documentação MCP','AGIA','Referência canônica para ChatGPT, Claude, Llama e outros clientes compatíveis.',body,'blue')
def monitor_health():
 h=jload(HEALTH+'/control-plane-smoke.json',{});body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Smoke</span><strong>{h.get('passed','-')}/{h.get('total','-')}</strong></div><div class="s98-kpi"><span>Portal</span><strong>{active('cloudif-admin-portal.service')}</strong></div><div class="s98-kpi"><span>MCP</span><strong>{active('cloudif-mcp-gateway.service')}</strong></div><div class="s98-kpi"><span>Registry</span><strong>{active('cloudif-agent-registry.service')}</strong></div></section>'''
 return shell('Saúde da plataforma','Monitoramento','Visão executiva do estado dos principais serviços e dos testes permanentes.',body)
def monitor_transactions():
 total=dbcount(PORTAL,'select count(*) from reconcile_requests');running=dbcount(PORTAL,"select count(*) from reconcile_requests where status='running'");retry=dbcount(PORTAL,"select count(*) from reconcile_requests where status='waiting_retry'")
 body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Transações registradas</span><strong>{total}</strong></div><div class="s98-kpi"><span>Em execução</span><strong>{running}</strong></div><div class="s98-kpi"><span>Aguardando retry</span><strong>{retry}</strong></div></section>{cards([('TX','Consistência','Operações usam estado, idempotência, reserva e finalização.'),('↻','Recuperação','Leases expirados retornam à fila sem perder a tarefa.'),('✓','Auditoria','Resultados são sanitizados e vinculados ao projeto.')])}'''
 return shell('Transações','Monitoramento','Acompanhamento do protocolo transacional e da recuperação de operações.',body,'blue')
def monitor_promotions():
 jobs=dbcount(PORTAL,'select count(*) from release_jobs');ok=dbcount(PORTAL,"select count(*) from release_jobs where status in ('success','ready','promoted','rolled_back')")
 body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Jobs de release</span><strong>{jobs}</strong></div><div class="s98-kpi"><span>Concluídos</span><strong>{ok}</strong></div></section>{cards([('↑','Promoções','Histórico de publicação no ambiente isolado.'),('↩','Rollbacks','Reversões manuais vinculadas ao job de destino.'),('■','Produção','Permanece bloqueada enquanto o alvo recuperável não estiver configurado.')])}'''
 return shell('Promoções e rollbacks','Monitoramento','Histórico operacional de promoções e reversões, separado da tela geral dos projetos.',body,'amber')
def monitor_queue():
 q=dbcount(PORTAL,"select count(*) from reconcile_requests where status in ('queued','waiting_retry','running')");dead=dbcount(PORTAL,"select count(*) from reconcile_requests where status='dead_letter'")
 body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Fila ativa</span><strong>{q}</strong></div><div class="s98-kpi"><span>Dead-letter</span><strong>{dead}</strong></div><div class="s98-kpi"><span>Workers</span><strong>4</strong></div><div class="s98-kpi"><span>Lease</span><strong>45 s</strong></div></section><div class="s98-note">Esta é a visão operacional de monitoramento. A página AGIA → Reconciliação explica e detalha o fluxo funcional para agentes.</div>'''
 return shell('Filas e conciliação','Monitoramento','Indicadores operacionais da fila assíncrona, retries, leases e dead-letter.',body)
def monitor_telemetry():
 cap=jload(HEALTH+'/project-capabilities-v2.json',{});agent=jload(HEALTH+'/agent-controller.json',{})
 body=f'''<section class="s98-grid"><div class="s98-kpi"><span>Projetos observados</span><strong>{len(cap.get('projects') or [])}</strong></div><div class="s98-kpi"><span>Ferramentas catalogadas</span><strong>{cap.get('catalog_tools','-')}</strong></div><div class="s98-kpi"><span>Agentes observados</span><strong>{agent.get('projects','-')}</strong></div><div class="s98-kpi"><span>Debounce</span><strong>{active('cloudif-project-state-reconcile.path')}</strong></div></section>'''
 return shell('Telemetria','Monitoramento','Métricas consolidadas de projetos, agentes, capacidades e reconciliação.',body,'blue')
def admin_page(kind):
 specs={
 'admin-usuarios':('Usuários e perfis','Identidades humanas, grupos e papéis usados no portal.',[('US','Usuários','Identidades chegam pelo Authentik e são vinculadas a grupos.'),('PF','Perfis','Administrador, professor, aluno e perfis de projeto.'),('AC','Acesso','A visibilidade é filtrada por tenant, projeto e função.')]),
 'admin-politicas':('Políticas de acesso','Escopos, ambientes e decisões de autorização.',[('RB','RBAC','Escopos são derivados do perfil no Agent Registry.'),('EN','Ambientes','Projeto, isolated-test e produção possuem políticas distintas.'),('AP','Aprovação','Produção exige uma decisão de administrador ou professor.')]),
 'admin-agentes':('Agentes e identidades','Clientes MCP, controladores e reconciliação de metadados.',[('ID','Identidades','Um cliente MCP por projeto.'),('↻','Controlador','Estado desejado e observado sem rotação automática.'),('TK','Tokens','Credenciais permanecem server-side e são exibidas uma vez.')]),
 'admin-configuracoes':('Configurações','Parâmetros e integrações da plataforma.',[('CF','Parâmetros','Limites, URLs e recursos são administrados server-side.'),('IN','Integrações','Forgejo, Supabase, Komodo e Authentik.'),('FL','Fail-closed','Ausência ou drift de configuração bloqueia efeitos.')]),
 'admin-auditoria':('Auditoria administrativa','Evidências de ações administrativas e decisões.',[('AU','Eventos','Ações são vinculadas a ator, projeto e trace.'),('SC','Sanitização','Tokens, senhas e payloads sensíveis não são expostos.'),('RT','Retenção','Evidências permanentes são preservadas conforme política.')]),
 'admin-manutencao':('Operações de manutenção','Diagnóstico e reparação controlada da plataforma.',[('SM','Smoke','Baseline permanente e rollback por release.'),('RC','Reconciliação','Timers e path com debounce corrigem divergências.'),('BK','Recuperação','Cada alteração possui roteiro de rollback.')])}
 title,intro,items=specs[kind];return shell(title,'Administração',intro,cards(items),'amber')
def help_page(kind):
 specs={
 'ajuda-inicio':('Primeiros passos','Fluxo inicial para entrar, escolher um projeto e conectar ferramentas.',[('1','Escolha o projeto','Abra Meus Projetos e confira conectores.'),('2','Obtenha a credencial','Use a área Agentes de IA para exibição única.'),('3','Conecte o cliente','Configure endpoint, client_id e token.'),('4','Leia o guia','O agente deve consultar o resource do projeto.')]),
 'ajuda-token':('Como obter o token','Procedimento seguro para emitir ou rotacionar a credencial MCP.',[('1','Abra Agentes de IA','Selecione o projeto autorizado.'),('2','Rotacione quando necessário','A ação exige sessão, ACL e CSRF.'),('3','Copie uma única vez','O token não volta a aparecer.'),('4','Guarde no cliente','Nunca grave em código, Git, prompt ou fila.')]),
 'ajuda-clientes':('Conectar clientes de IA','Como ChatGPT, Claude e Llama descobrem e usam o MCP.',[('MC','MCP','Use o endpoint autenticado do CloudIFF.'),('IN','Initialize','O servidor envia instruções automaticamente.'),('RS','Resources','Leia o guia geral e o guia do projeto.'),('TL','Tools','Chame apenas as ferramentas autorizadas.')]),
 'ajuda-aprovacoes':('Como funcionam as aprovações','Onde e por quem operações protegidas são decididas.',[('PO','Portal CloudIFF','Aprovações humanas acontecem na aba própria.'),('AD','Administrador','Pode decidir sozinho.'),('PR','Professor','Pode decidir sozinho.'),('AL','Aluno ou agente','Aguarda administrador ou professor.')]),
 'ajuda-ferramentas':('Referência das ferramentas MCP','Como interpretar ferramentas habilitadas, condicionais e restritas.',[('EN','Habilitada','Pode ser usada pelo perfil e projeto.'),('CN','Condicional','Depende do conector estar pronto.'),('IT','Isolated-test','Exclusiva do operador de teste.'),('FC','Fail-closed','Planeja ou informa bloqueios sem executar efeito.')])}
 title,intro,items=specs[kind];return shell(title,'Ajuda',intro,cards(items),'blue')
ROUTES={
 'gestao-agentes':agent_management,'documentacao-mcp':mcp_docs,
 'monitor-saude':monitor_health,'monitor-transacoes':monitor_transactions,'monitor-promocoes':monitor_promotions,'monitor-filas':monitor_queue,'monitor-telemetria':monitor_telemetry,
}
def render(tab):
 if tab in ROUTES:return ROUTES[tab]()
 if tab.startswith('admin-'):return admin_page(tab)
 if tab.startswith('ajuda-'):return help_page(tab)
 raise KeyError(tab)

# Compatibility and dedicated project-options route.
def options_project():
 items=[('SV','Serviços e conectores','Abra a tela do projeto e use a aba Serviços.'),('CT','Containers','Use a aba Contêineres para telemetria e execução.'),('BK','Backups','Use a aba Backup para histórico e recuperação.'),('PB','Publicações','Use a aba Publicações para versões e ambientes.'),('CF','Configurações','Use a aba Configurações para administração do projeto.')]
 body=cards(items)+'''<section class="card"><h2>Abrir as opções</h2><p>Selecione um projeto na lista e use as abas internas. O menu principal não repete cada opção.</p><a class="btn" href="/cloudiff/portal/?tab=projetos&section=options">Abrir projetos</a></section>'''
 return shell('Opções do projeto','Meus Projetos','Uma entrada única para serviços, containers, backups, publicações e configurações.',body)

def documentation_mcp():
 return mcp_docs()

def monitor(kind):
 if kind not in ROUTES:raise KeyError(kind)
 return ROUTES[kind]()

_help_page98_base=help_page
def help_page(kind):
 aliases={'ajuda':'ajuda-inicio'}
 resolved=aliases.get(kind,kind)
 body=_help_page98_base(resolved)
 if resolved=='ajuda-inicio':
  body+='''<section class="card" style="margin-top:16px"><div class="section-title"><div><h2>Vídeos rápidos</h2><p class="small">Apresentações curtas para conhecer a CloudIFF e acompanhar o fluxo de uso.</p></div></div><div class="grid"><div class="box"><h3>Apresentação rápida da CloudIFF</h3><p>Visão breve da plataforma, seus recursos e a experiência de uso.</p><a class="btn" href="https://youtu.be/cxH3K8s1R9M" target="_blank" rel="noopener noreferrer">Assistir no YouTube</a></div><div class="box"><h3>Demonstração prática da plataforma</h3><p>Vídeo curto mostrando o uso da CloudIFF e o fluxo de trabalho.</p><a class="btn" href="https://youtu.be/pJ7mx3VZuWU" target="_blank" rel="noopener noreferrer">Assistir no YouTube</a></div></div></section><section class="card" style="margin-top:16px"><div class="section-title"><div><h2>GitHub e manual técnico</h2><p class="small">Código-fonte e documentação completa da arquitetura CloudIFF.</p></div><a class="btn" href="https://github.com/debianlima/cloudiff" target="_blank" rel="noopener noreferrer">Abrir GitHub do projeto</a></div><p>O repositório documenta arquitetura, fluxogramas, agentes e funções, protocolos de reconciliação, modelo de dados, mensagens, aprovações, operação, serviços, rotas e a finalidade de cada pasta e arquivo.</p></section>'''
 return body

_admin_page98_base=admin_page
def admin_page(kind):
 aliases={'admin-identidades':'admin-agentes'}
 return _admin_page98_base(aliases.get(kind,kind))
