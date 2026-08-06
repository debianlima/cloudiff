#!/usr/bin/env python3
import html,json,time,urllib.request,urllib.error
META_KEYS=('proposal_digest','merge_digest','deployment_digest','promotion_digest','activation_digest','window_digest_sha256','snapshot_sha256','target_url','canary_a_sha256','canary_b_sha256','effect_tool_available','activation_allowed','commit_sha','expected_head_sha','expected_previous_commit','version','path','proposal_number','dry_run','target','real_deploy','supabase_operation','supabase_plan_digest','summary','actor_user','secret_values_in_metadata','plan_digest','config_revision','config_digest','toolchain_digest','archive_sha256','build_job_id','build_plan_digest','preview_plan_digest','preview_ttl_seconds')
ACTION_LABELS={'forgejo.propose-edit':'Criar proposta no Forgejo','forgejo.propose-change-set':'Criar proposta multifarquivo no Forgejo','forgejo.proposal.merge':'Mesclar pull request','deployment.validate':'Validar deploy sem efeitos','deployment.promote-test':'Promover para ambiente de teste','deployment.production.deploy':'Publicar em produção','deployment.production.rollback':'Reverter produção','deployment.production.homologation.deploy':'Publicar na homologação','deployment.production.homologation.rollback':'Reverter homologação','deployment.production.activate':'Pré-ativação de produção real','supabase.operation.records.change':'Alterar registros do Supabase','supabase.operation.sql.change':'Executar SQL no Supabase','supabase.operation.rls.change':'Alterar políticas RLS','supabase.operation.schema.change':'Alterar schema do banco','supabase.operation.secrets.read':'Exibir segredos do tenant','build.multiservice':'Construir aplicação multissserviço','preview.multiservice':'Criar preview multissserviço'}
def request(base,token,method,path,payload=None,timeout=20):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();q=urllib.request.Request(base.rstrip('/')+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(q,timeout=timeout) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:
  try:d=json.load(e)
  except Exception:d={}
  return e.code,d
 except (urllib.error.URLError,TimeoutError,ConnectionError,OSError) as e:
  return 503,{'ok':False,'error':'approval_service_unavailable','detail':type(e).__name__}
 except Exception as e:
  return 503,{'ok':False,'error':'approval_service_unavailable','detail':type(e).__name__}
def sanitize(row):
 try:meta=json.loads(row.get('metadata_json') or '{}')
 except Exception:meta={}
 safe_meta={k:meta[k] for k in META_KEYS if k in meta}
 return {k:row.get(k) for k in ('approval_id','project_slug','action','requested_by','requester_role','approved_by','approver_role','second_approved_by','second_approver_role','two_approvers_required','authorization_mode','rejected_by','status','reason','created_at','expires_at','approved_at','rejected_at','consumed_at','rejection_reason','trace_id')}|{'action_label':ACTION_LABELS.get(row.get('action'),row.get('action')),'metadata':safe_meta}
def filter_rows(rows,slugs):return [sanitize(x) for x in rows if x.get('project_slug') in slugs]
def fmt_epoch(v):
 if not v:return '—'
 try:return time.strftime('%d/%m/%Y %H:%M:%S',time.localtime(int(v)))
 except Exception:return '—'
def badge(status):
 cls={'pending':'pending','pending_second':'pending','approved':'ok','consumed':'muted','rejected':'bad','expired':'muted'}.get(status,'muted')
 return '<span class="backup-status '+cls+'">'+html.escape(str(status))+'</span>'
def render(rows,csrf,can_decide):
 pending=sum(1 for x in rows if x['status'] in ('pending','pending_second'));approved=sum(1 for x in rows if x['status']=='approved');history=len(rows)-pending-approved
 cards=[]
 for x in rows[:80]:
  meta=''.join('<div><b>'+html.escape(k.replace('_',' '))+':</b> <code>'+html.escape(str(v))+'</code></div>' for k,v in x['metadata'].items()) or '<div class="small">Sem detalhes adicionais.</div>'
  actions=''
  if can_decide and x['status'] in ('pending','pending_second'):
   actions='<div class="backup-actions"><form method="post" action="/cloudiff/portal/action/approval"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="approval_id" value="'+html.escape(x['approval_id'])+'"><input type="hidden" name="operation" value="approve"><button class="btn" type="submit">Aprovar</button></form><form method="post" action="/cloudiff/portal/action/approval"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="approval_id" value="'+html.escape(x['approval_id'])+'"><input type="hidden" name="operation" value="reject"><label class="small">Motivo da rejeição<input name="rejection_reason" minlength="4" maxlength="500" required></label><button class="btn danger" type="submit">Rejeitar</button></form></div>'
  cards.append('<article class="backup-item"><div><div class="section-title"><div><h3>'+html.escape(str(x['action_label']))+'</h3><p class="small"><code>'+html.escape(x['approval_id'])+'</code></p></div>'+badge(x['status'])+'</div><p><b>Projeto:</b> <code>'+html.escape(str(x['project_slug']))+'</code></p><p><b>Solicitante:</b> '+html.escape(str(x['requested_by']))+' · perfil '+html.escape(str(x.get('requester_role') or 'agent'))+'</p><p><b>Política:</b> '+html.escape(str(x.get('authorization_mode') or 'decisão única'))+'</p>'+('<p><b>Primeiro aprovador:</b> '+html.escape(str(x.get('approved_by') or 'aguardando'))+' · <b>Segundo aprovador:</b> '+html.escape(str(x.get('second_approved_by') or 'aguardando'))+'</p>' if x.get('two_approvers_required') else '')+'<p><b>Motivo:</b> '+html.escape(str(x['reason'] or '—'))+'</p><p class="small">Criada em '+fmt_epoch(x['created_at'])+' · expira em '+fmt_epoch(x['expires_at'])+'</p><details><summary>Impacto e vínculo da operação</summary>'+meta+'</details>'+actions+'</div></article>')
 return '<section class="card" id="human-approvals"><div class="section-title"><div><h2>Aprovações humanas</h2><p class="small">Decisões vinculadas ao projeto e ao digest. Homologação exige uma aprovação humana de uso único por operação. A pré-ativação real exige dois administradores ou professores distintos; o solicitante não pode aprovar e qualquer mudança no digest invalida a autorização.</p></div></div><div class="backup-summary"><div class="backup-stat"><b>Pendentes</b><div class="kpi">'+str(pending)+'</div></div><div class="backup-stat"><b>Aprovadas</b><div class="kpi">'+str(approved)+'</div></div><div class="backup-stat"><b>Histórico</b><div class="kpi">'+str(history)+'</div></div></div><div class="backup-list">'+(''.join(cards) or '<div class="box">Nenhuma aprovação visível.</div>')+'</div></section>'
