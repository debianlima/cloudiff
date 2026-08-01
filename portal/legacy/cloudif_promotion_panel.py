#!/usr/bin/env python3
import html,json,urllib.request
STATUS={'published':'Publicado','rolled_back':'Revertido','failed':'Falhou','scheduled':'Agendado','running':'Executando'}
def fetch(base,token):
 q=urllib.request.Request(base.rstrip('/')+'/v1/promotions?project=sistema-de-biblioteca-teste',headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
 with urllib.request.urlopen(q,timeout=20) as r:return json.load(r)
def e(v):return html.escape(str(v if v is not None else '—'))
def render(d):
 s=d.get('summary') or {};jobs=d.get('jobs') or []
 stats=''.join('<div class="backup-stat"><b>'+k+'</b><div class="kpi">'+str(v)+'</div></div>' for k,v in [('Total',s.get('total',0)),('Publicados',s.get('published',0)),('Revertidos',s.get('rolled_back',0)),('Falhas',s.get('failed',0)),('Rollbacks manuais',s.get('manual_rollbacks',0))])
 rows=[]
 for j in jobs[:20]:
  st=j.get('status');cls='ok' if st=='published' else ('bad' if st in ('failed','rolled_back') else 'pending');manual=j.get('operation')=='manual_rollback';title=('Rollback manual → job #'+e(j.get('target_job_id'))) if manual else ('Job #'+e(j.get('id')))
  rows.append('<article class="backup-item"><div class="section-title"><div><b>'+title+'</b><p class="small"><code>'+e(j.get('commit_sha'))+'</code></p></div><span class="backup-status '+cls+'">'+e(STATUS.get(st,st))+'</span></div><p class="small">Registro: #'+e(j.get('id'))+' · versão: '+e(j.get('version'))+' · início: '+e(j.get('started_at'))+' · fim: '+e(j.get('finished_at'))+'</p></article>')
 return '<section class="card" id="promotion-history"><div class="section-title"><div><h2>Histórico de promoções do ambiente isolado</h2><p class="small">Consulta somente leitura; não executa deploy, rollback ou retry.</p></div><span class="pill ok">isolated-test</span></div><div class="backup-summary">'+stats+'</div><div class="backup-list">'+(''.join(rows) or '<div class="box">Sem promoções registradas.</div>')+'</div></section>'
