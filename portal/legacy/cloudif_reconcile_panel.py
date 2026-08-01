#!/usr/bin/env python3
import html,json,sqlite3,datetime
DB='/var/lib/cloudif/portal/cloudif-portal.db'
def e(v):return html.escape(str(v if v is not None else ''))
def data(limit=100):
 c=sqlite3.connect('file:'+DB+'?mode=ro',uri=True,timeout=10);c.row_factory=sqlite3.Row
 rows=[dict(r) for r in c.execute('''select request_id,created_at,started_at,finished_at,event_type,actor,username,project,tenant,status,message,attempt_count,max_attempts,next_attempt_at,lease_owner,lease_expires_at,heartbeat_at,partition_key,dead_lettered_at,last_error_type from reconcile_requests order by created_at desc limit ?''',(max(1,min(int(limit),200)),))];c.close()
 summary={}
 for r in rows:summary[r['status']]=summary.get(r['status'],0)+1
 return {'ok':True,'summary':summary,'requests':rows,'workers':4,'lease_seconds':45,'max_attempts':5,'payload_exposed':False,'result_exposed':False,'secrets_exposed':False,'tokens_persisted':False,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def render():
 d=data();labels={'queued':'Na fila','running':'Em execução','waiting_retry':'Aguardando retry','ready':'Concluída','waiting':'Aguardando dependência','failed':'Falhou','dead_letter':'Dead-letter'}
 cards=''.join(f'<div class="box"><b>{e(labels.get(k,k))}</b><p>{v}</p></div>' for k,v in sorted(d['summary'].items())) or '<div class="box"><b>Fila</b><p>Vazia</p></div>'
 rows=''.join(f'''<tr><td><code>{e(x['request_id'][:8])}</code></td><td>{e(x['event_type'])}</td><td>{e(x['project'] or x['tenant'] or x['username'] or '-')}</td><td>{e(labels.get(x['status'],x['status']))}</td><td>{x['attempt_count']}/{x['max_attempts']}</td><td>{e(x['next_attempt_at'] or '-')}</td><td>{e(x['message'])}</td></tr>''' for x in d['requests'])
 return f'''<section class="card"><div class="section-title"><div><h1>Reconciliação assíncrona</h1><p>Fila durável por projeto, com quatro workers, leases recuperáveis, retry e dead-letter.</p></div><span class="pill ok">Sem tokens na fila</span></div><div class="grid">{cards}</div><div class="infra-note"><b>Como funciona:</b> projetos diferentes executam em paralelo; o mesmo projeto permanece serializado. Leases expiram em 45 segundos e são recuperados. Após cinco falhas, a tarefa vai para dead-letter. A rotação de credencial não altera jobs pendentes, pois tokens não são gravados na fila.</div></section><section class="card"><h2>Tarefas recentes</h2><table><tr><th>ID</th><th>Evento</th><th>Partição</th><th>Estado</th><th>Tentativas</th><th>Próxima tentativa</th><th>Mensagem</th></tr>{rows}</table><p class="small">Payloads, resultados internos, tokens e segredos não são exibidos.</p></section>'''
