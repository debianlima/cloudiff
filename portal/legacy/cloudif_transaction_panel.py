#!/usr/bin/env python3
import html,json,time,urllib.parse,urllib.request,urllib.error
LABELS={'pending':'Pendente','approved':'Aprovada','reserved':'Reservada','consumed':'Concluída','rejected':'Rejeitada','expired':'Expirada'}
ACTIONS={'forgejo.propose-edit':'Criar proposta','forgejo.propose-change-set':'Criar proposta multifarquivo','forgejo.proposal.merge':'Mesclar PR','deployment.validate':'Validar deploy','deployment.promote-test':'Promover ambiente de teste','build.multiservice':'Construir aplicação multissserviço','preview.multiservice':'Criar preview multissserviço','deployment.multiservice':'Publicar aplicação multissserviço'}
def fetch(base,token,slug):
 q=urllib.request.Request(base.rstrip('/')+'/v1/transactions?project='+urllib.parse.quote(slug,safe=''),headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
 with urllib.request.urlopen(q,timeout=15) as r:return json.load(r)
def fmt(v):
 if not v:return '—'
 try:return time.strftime('%d/%m/%Y %H:%M:%S',time.localtime(int(v)))
 except Exception:return '—'
def esc(v):return html.escape(str(v if v is not None else '—'))
def badge(v):
 cls={'pending':'pending','approved':'ok','reserved':'pending','consumed':'muted','rejected':'bad','expired':'muted'}.get(v,'muted')
 return '<span class="backup-status '+cls+'">'+esc(LABELS.get(v,v))+'</span>'
def render(items):
 cards=[]
 for x in items:
  slug=x.get('project_slug');s=x.get('summary') or {};counts={v.get('status'):int(v.get('count') or 0) for v in s.get('approval_counts') or []};alerts=x.get('alerts') or [];recent=x.get('recent_approvals') or []
  stats=''.join('<div class="backup-stat"><b>'+esc(LABELS.get(k,k))+'</b><div class="kpi">'+str(counts.get(k,0))+'</div></div>' for k in ('pending','approved','reserved','consumed','rejected','expired'))
  alert_html=''.join('<div class="box"><b>'+esc(a.get('severity'))+'</b>: '+esc(a.get('code'))+' ('+esc(a.get('count'))+')</div>' for a in alerts) or '<div class="box"><span class="pill ok">Sem alertas</span></div>'
  rows=[]
  for a in recent[:12]:
   rows.append('<article class="backup-item"><div><div class="section-title"><div><b>'+esc(ACTIONS.get(a.get('action'),a.get('action')))+'</b><p class="small"><code>'+esc(a.get('approval_id'))+'</code></p></div>'+badge(a.get('status'))+'</div><p class="small">Solicitante: '+esc(a.get('requested_by'))+' · aprovado por: '+esc(a.get('approved_by'))+'</p><p class="small">Criada: '+fmt(a.get('created_at'))+' · finalizada: '+fmt(a.get('finalized_at'))+' · resultado: '+esc(a.get('finalize_result'))+'</p></div></article>')
  cards.append('<section class="card transaction-project"><div class="section-title"><div><h3>'+esc(slug)+'</h3><p class="small">Observabilidade transacional somente leitura.</p></div><span class="pill ok">Isolado por projeto</span></div><div class="backup-summary">'+stats+'</div><h4>Alertas</h4><div class="grid">'+alert_html+'</div><details><summary>Histórico recente</summary><div class="backup-list">'+(''.join(rows) or '<div class="box">Sem operações recentes.</div>')+'</div></details></section>')
 return '<section id="transaction-observability"><div class="section-title"><div><h2>Operações transacionais</h2><p class="small">Reservas, aprovações e finalizações por projeto. Sem retries ou aprovações automáticas.</p></div></div>'+(''.join(cards) or '<div class="card">Nenhum projeto visível.</div>')+'</section>'
