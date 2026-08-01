#!/usr/bin/env python3
import html,json
REPORT='/var/lib/cloudif/health/project-capabilities-v2.json'
def e(v):return html.escape(str(v if v is not None else ''))
def data():
 try:return json.load(open(REPORT))
 except Exception:return {'ok':False,'projects':[],'catalog_tools':0,'secrets_exposed':False}
def render():
 d=data();cards=[]
 labels={'enabled':'Habilitada','enabled_fail_closed':'Habilitada com bloqueio seguro','conditional_connector':'Depende do conector','restricted_environment':'Somente ambiente isolado','blocked_policy':'Bloqueada pela política'}
 for p in d.get('projects') or []:
  rows=''.join(f'<tr><td><code>{e(x["name"])}</code></td><td>{e(labels.get(x["status"],x["status"]))}</td><td>{e(x["reason"])}</td><td>{e(x.get("connector") or "-")}</td></tr>' for x in p['tools'])
  c=p['counts'];cards.append(f'''<article class="card"><div class="section-title"><div><h2>{e(p['project_slug'])}</h2><p>{e(p['role_profile'])} · {e(p['environment'])} · {p['tool_count']} ferramentas avaliadas</p></div><span class="pill {'ok' if p['scope_match'] else 'bad'}">{'Catálogo aplicado' if p['scope_match'] else 'Divergência'}</span></div><div class="grid"><div class="box"><b>Habilitadas</b><p>{c.get('enabled',0)}</p></div><div class="box"><b>Fail-closed</b><p>{c.get('enabled_fail_closed',0)}</p></div><div class="box"><b>Condicionais</b><p>{c.get('conditional_connector',0)}</p></div><div class="box"><b>Ambiente isolado</b><p>{c.get('restricted_environment',0)}</p></div></div><details><summary><b>Ver todas as ferramentas</b></summary><table><tr><th>Ferramenta</th><th>Estado</th><th>Motivo</th><th>Conector</th></tr>{rows}</table></details></article>''')
 intro=f'''<section class="card"><h1>Capacidades dos projetos</h1><p>Catálogo completo aplicado aos projetos atuais e usado como modelo para projetos futuros.</p><div class="grid"><div class="box"><b>Ferramentas no catálogo</b><p>{d.get('catalog_tools',0)}</p></div><div class="box"><b>Projetos atuais</b><p>{len(d.get('projects') or [])}</p></div><div class="box"><b>Aplicação futura</b><p>{'Ativa' if d.get('apply_to_new') else 'Inativa'}</p></div><div class="box"><b>Efeitos executados</b><p>Não</p></div></div><div class="infra-note"><b>Regra:</b> funções universais são habilitadas; funções dependentes de conectores ficam condicionais; promoção e rollback de teste permanecem exclusivos do <code>test-operator</code> em <code>isolated-test</code>.</div></section>'''
 return intro+''.join(cards)
