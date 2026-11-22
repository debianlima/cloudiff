#!/usr/bin/env python3
import html,json,os,time,urllib.request,urllib.error
META_KEYS=('proposal_digest','merge_digest','deployment_digest','promotion_digest','activation_digest','window_digest_sha256','snapshot_sha256','target_url','canary_a_sha256','canary_b_sha256','effect_tool_available','activation_allowed','commit_sha','expected_head_sha','expected_previous_commit','version','path','proposal_number','dry_run','target','real_deploy','supabase_operation','supabase_plan_digest','summary','actor_user','secret_values_in_metadata','plan_digest','config_revision','config_digest','toolchain_digest','archive_sha256','build_job_id','build_plan_digest','preview_plan_digest','preview_ttl_seconds','environment_plan_digest','environment_action','source_environment','target_environment','expected_revision','requested_toolchain_digest','activation_plan_digest','job_id','environment')
ACTION_LABELS={'forgejo.propose-edit':'Criar proposta no Forgejo','forgejo.propose-change-set':'Criar proposta multifarquivo no Forgejo','forgejo.proposal.merge':'Mesclar pull request','deployment.validate':'Validar deploy sem efeitos','deployment.promote-test':'Promover para ambiente de teste','deployment.production.deploy':'Publicar em produção','deployment.production.rollback':'Reverter produção','deployment.production.homologation.deploy':'Publicar na homologação','deployment.production.homologation.rollback':'Reverter homologação','deployment.production.activate':'Pré-ativação de produção real','supabase.operation.records.change':'Alterar registros do Supabase','supabase.operation.sql.change':'Executar SQL no Supabase','supabase.operation.rls.change':'Alterar políticas RLS','supabase.operation.schema.change':'Alterar schema do banco','supabase.operation.secrets.read':'Exibir segredos do tenant','build.multiservice':'Construir aplicação multissserviço','preview.multiservice':'Criar preview multissserviço','deployment.multiservice':'Publicar aplicação multissserviço','project.environment.change':'Alterar ambiente do projeto','project.environment.promotion':'Promover ambiente do projeto','project.toolchain.build':'Construir imagem da toolchain','project.toolchain.activation':'Ativar imagem da toolchain','pgh.device.pair':'PGHD — Pareamento resiliente','pgh.dashboard.session':'PGH — Access Admin sem senha','pgh.vault.session':'PGH — Vault Admin sem senha','pgh.openbao.session':'PGH — OpenBao sem senha'}
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
 return {k:row.get(k) for k in ('approval_id','project_slug','action','requested_by','requester_role','approved_by','approver_role','second_approved_by','second_approver_role','two_approvers_required','authorization_mode','rejected_by','cancelled_by','status','reason','created_at','expires_at','approved_at','rejected_at','cancelled_at','consumed_at','rejection_reason','cancellation_reason','trace_id')}|{'action_label':ACTION_LABELS.get(row.get('action'),row.get('action')),'metadata':safe_meta}
def filter_rows(rows,slugs):return [sanitize(x) for x in rows if x.get('project_slug') in slugs]
def sanitize_policy(row):
 return {k:row.get(k) for k in ('policy_id','project_slug','action','requested_by','created_by','creator_role','source_approval_id','created_at','revoked_at','revoked_by','revoke_reason')}|{'action_label':ACTION_LABELS.get(row.get('action'),row.get('action')),'active':not bool(row.get('revoked_at'))}
def filter_policies(rows,slugs):return [sanitize_policy(x) for x in rows if x.get('project_slug') in slugs]
def fmt_epoch(v):
 if not v:return '—'
 try:return time.strftime('%d/%m/%Y %H:%M:%S',time.localtime(int(v)))
 except Exception:return '—'
def badge(status):
 cls={'pending':'pending','pending_second':'pending','approved':'ok','consumed':'muted','rejected':'bad','cancelled':'muted','expired':'muted'}.get(status,'muted')
 return '<span class="backup-status '+cls+'">'+html.escape(str(status))+'</span>'
def _same_human(value,actor):
 value=str(value or '').strip().lower();actor=str(actor or '').strip().lower()
 if not value or not actor:return False
 if value.startswith('portal:'):value=value.split(':',1)[1]
 return value==actor
def history_card(x):
 meta=''.join('<div><b>'+html.escape(k.replace('_',' '))+':</b> <code>'+html.escape(str(v))+'</code></div>' for k,v in (x.get('metadata') or {}).items()) or '<div class="small">Sem detalhes adicionais.</div>'
 policy_note='<p class="small"><b>Autoaprovada por política persistente.</b></p>' if x.get('authorization_mode')=='persistent_policy' else ''
 return '<article class="backup-item"><div><div class="section-title"><div><h3>'+html.escape(str(x['action_label']))+'</h3><p class="small"><code>'+html.escape(x['approval_id'])+'</code></p></div>'+badge(x['status'])+'</div><p><b>Projeto:</b> <code>'+html.escape(str(x['project_slug']))+'</code></p><p><b>Solicitante:</b> '+html.escape(str(x['requested_by']))+' · perfil '+html.escape(str(x.get('requester_role') or 'agent'))+'</p><p><b>Política:</b> '+html.escape(str(x.get('authorization_mode') or 'decisão única'))+'</p>'+policy_note+('<p><b>Primeiro aprovador:</b> '+html.escape(str(x.get('approved_by') or 'aguardando'))+' · <b>Segundo aprovador:</b> '+html.escape(str(x.get('second_approved_by') or 'aguardando'))+'</p>' if x.get('two_approvers_required') else '')+'<p><b>Motivo:</b> '+html.escape(str(x['reason'] or '—'))+'</p><p class="small">Criada em '+fmt_epoch(x['created_at'])+' · expira em '+fmt_epoch(x['expires_at'])+'</p><details><summary>Impacto e vínculo da operação</summary>'+meta+'</details></div></article>'
HISTORY_LAZY_JS='<script>(function(){var d=document.getElementById("approval-history-dialog");if(!d)return;var list=document.getElementById("approval-history-pages");var more=document.getElementById("approval-history-more");var busy=false;function page(){if(busy)return;busy=true;var next=parseInt(list.dataset.page||"0",10)+1;fetch(list.dataset.endpoint+"&page="+next+"&page_size="+list.dataset.size,{credentials:"same-origin"}).then(function(r){return r.json()}).then(function(data){if(!data.ok)return;var items=data.history_html||[];if(next===1)list.innerHTML="";items.forEach(function(h){var w=document.createElement("div");w.innerHTML=h;while(w.firstChild)list.appendChild(w.firstChild)});list.dataset.page=String(next);more.style.display=data.has_more?"":"none";}).catch(function(){}).finally(function(){busy=false})}d.addEventListener("toggle",function(){if(d.open&&list.dataset.page==="0")page()});more.addEventListener("click",page)})();</script>'
def render(rows,csrf,can_decide,policies=None,actor_username='',history_total=None,history_lazy=False,counts=None):
 actor_username=str(actor_username or '').strip()
 policies=policies or [];live_statuses=('pending','pending_second','approved');live_rows=[x for x in rows if x['status'] in live_statuses];history_rows=[x for x in rows if x['status'] not in live_statuses];pending=sum(1 for x in live_rows if x['status'] in ('pending','pending_second'));approved=sum(1 for x in live_rows if x['status']=='approved');history=(len(history_rows) if history_total is None else int(history_total))
 if counts:
  pending=int(counts.get('pending',pending));approved=int(counts.get('approved',approved))
 cards=[];history_cards=[]
 for x in (live_rows+([] if history_lazy else history_rows))[:80]:
  meta=''.join('<div><b>'+html.escape(k.replace('_',' '))+':</b> <code>'+html.escape(str(v))+'</code></div>' for k,v in x['metadata'].items()) or '<div class="small">Sem detalhes adicionais.</div>'
  actions='';decision_note=''
  status=str(x.get('status') or '')
  requester_is_actor=bool(x.get('two_approvers_required')) and _same_human(x.get('requested_by'),actor_username)
  first_approver_is_actor=status=='pending_second' and _same_human(x.get('approved_by'),actor_username)
  if first_approver_is_actor:
   decision_note='<p class="small"><b>Primeira aprovação registrada por você.</b> Aguardando um segundo administrador ou professor distinto.</p>'
  elif requester_is_actor and status=='pending':
   decision_note='<p class="small"><b>Você solicitou esta ativação.</b> A dupla aprovação deve ser dada por outras pessoas autorizadas.</p>'
  elif can_decide and status in ('pending','pending_second'):
   always='<label class="small" style="display:flex;gap:.55rem;align-items:flex-start;margin:.7rem 0"><input type="checkbox" name="always_allow" value="1" style="margin-top:.2rem"><span><b>Sempre permitir</b> esta ação neste projeto para este solicitante. A política permanece até ser revogada; validações técnicas, digests, scanners e auditoria continuam ativos.</span></label>'
   approve='<form method="post" action="/cloudiff/portal/action/approval"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="approval_id" value="'+html.escape(x['approval_id'])+'"><input type="hidden" name="operation" value="approve">'+always+'<button class="btn" type="submit">Aprovar</button></form>'
   reject='' if status=='pending_second' else '<form method="post" action="/cloudiff/portal/action/approval"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="approval_id" value="'+html.escape(x['approval_id'])+'"><input type="hidden" name="operation" value="reject"><label class="small">Motivo da rejeição<input name="rejection_reason" minlength="4" maxlength="500" required></label><button class="btn danger" type="submit">Rejeitar</button></form>'
   actions='<div class="backup-actions">'+approve+reject+'</div>'
  policy_note=''
  if x.get('authorization_mode')=='persistent_policy':policy_note='<p class="small"><b>Autoaprovada por política persistente.</b></p>'
  card='<article class="backup-item"><div><div class="section-title"><div><h3>'+html.escape(str(x['action_label']))+'</h3><p class="small"><code>'+html.escape(x['approval_id'])+'</code></p></div>'+badge(x['status'])+'</div><p><b>Projeto:</b> <code>'+html.escape(str(x['project_slug']))+'</code></p><p><b>Solicitante:</b> '+html.escape(str(x['requested_by']))+' · perfil '+html.escape(str(x.get('requester_role') or 'agent'))+'</p><p><b>Política:</b> '+html.escape(str(x.get('authorization_mode') or 'decisão única'))+'</p>'+policy_note+('<p><b>Primeiro aprovador:</b> '+html.escape(str(x.get('approved_by') or 'aguardando'))+' · <b>Segundo aprovador:</b> '+html.escape(str(x.get('second_approved_by') or 'aguardando'))+'</p>' if x.get('two_approvers_required') else '')+decision_note+'<p><b>Motivo:</b> '+html.escape(str(x['reason'] or '—'))+'</p><p class="small">Criada em '+fmt_epoch(x['created_at'])+' · expira em '+fmt_epoch(x['expires_at'])+'</p><details><summary>Impacto e vínculo da operação</summary>'+meta+'</details>'+actions+'</div></article>'
  (cards if x['status'] in live_statuses else history_cards).append(card)
 policy_cards=[]
 for policy in policies[:80]:
  revoke=''
  if can_decide and policy.get('active'):
   revoke='<form method="post" action="/cloudiff/portal/action/approval"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="policy_id" value="'+html.escape(str(policy.get('policy_id') or ''))+'"><input type="hidden" name="operation" value="revoke_policy"><button class="btn danger" type="submit">Revogar sempre permitir</button></form>'
  pair_note='';pair_controls='';pair_key=''
  if policy.get('action')=='pgh.device.pair':
   pair_note='<p class="small"><b>Recuperação PGHD — fluxo sem senha:</b> o Atlas persiste somente a confiança deste dispositivo e usa uma identidade técnica restrita para a sessão administrativa. Você não precisa receber, guardar ou digitar senha. Código e cookie de pareamento continuam efêmeros e não são armazenados.</p>'
   key_file=os.environ.get('CLOUDIF_PGH_ATLAS_PUBLIC_KEY_FILE','/etc/cloudif/public-keys/pgh-atlas-access-admin-v1.pub')
   try:
    pub=open(key_file,encoding='utf-8').read().strip()
    if pub.startswith('ssh-ed25519 ') and len(pub)<2048:
     pair_key='<details><summary>Chave pública Atlas para autorizar uma única vez no Core</summary><p class="small"><b>key_id:</b> <code>pgh-atlas-access-admin-v1</code></p><textarea readonly rows="4" style="width:100%">'+html.escape(pub)+'</textarea><p class="small">A privada permanece cifrada na VPS e não é exibida pelo Portal. A autorização desta pública é feita uma única vez pelo fluxo administrativo homologado; não forneça senha ao ChatGPT nem copie segredo para o Atlas.</p></details>'
   except Exception:
    pair_key='<p class="small"><b>Chave pública Atlas:</b> indisponível no runtime.</p>'
   core=os.environ.get('CLOUDIF_PGH_CORE_BASE_URL','').strip().rstrip('/')
   if core:
    core_h=html.escape(core,quote=True)
    pair_controls='<div class="backup-actions"><form method="post" action="'+core_h+'/dashboard/pair/start" target="_blank"><button class="btn" type="submit">Iniciar novo pareamento no Core</button></form><a class="btn btn-quiet" href="'+core_h+'/dashboard/access-admin" target="_blank" rel="noopener noreferrer">Abrir Access Admin</a></div>'
   else:
    pair_controls='<p class="small"><b>Launcher Core indisponível:</b> configure <code>CLOUDIF_PGH_CORE_BASE_URL</code> no runtime do Portal.</p>'
  admin_controls='';admin_note=''
  admin_modes={'pgh.dashboard.session':('dashboard','Abrir Access Admin pelo Atlas — sem senha'),'pgh.vault.session':('vault','Abrir Vault Admin pelo Atlas — sem senha'),'pgh.openbao.session':('openbao','Abrir OpenBao pelo Atlas — sem senha')}
  if policy.get('action') in admin_modes:
   mode,label=admin_modes[policy.get('action')]
   admin_note='<p class="small"><b>Sessão administrativa Atlas:</b> principal técnico <code>principal:admin.atlas</code>, bootstrap one-time e nenhuma senha humana armazenada.</p>'
   admin_controls='<form method="post" action="/cloudiff/portal/action/pgh_admin_session"><input type="hidden" name="csrf_token" value="'+html.escape(csrf)+'"><input type="hidden" name="policy_id" value="'+html.escape(str(policy.get('policy_id') or ''))+'"><input type="hidden" name="mode" value="'+html.escape(mode)+'"><button class="btn" type="submit">'+html.escape(label)+'</button></form>'
  policy_cards.append('<article class="backup-item"><div><div class="section-title"><div><h3>'+html.escape(str(policy.get('action_label') or policy.get('action') or 'Política'))+'</h3><p class="small"><code>'+html.escape(str(policy.get('policy_id') or ''))+'</code></p></div><span class="backup-status '+('ok' if policy.get('active') else 'muted')+'">'+('ativa' if policy.get('active') else 'revogada')+'</span></div><p><b>Projeto:</b> <code>'+html.escape(str(policy.get('project_slug') or ''))+'</code></p><p><b>Solicitante autorizado:</b> '+html.escape(str(policy.get('requested_by') or ''))+'</p><p><b>Criada por:</b> '+html.escape(str(policy.get('created_by') or ''))+' · '+html.escape(str(policy.get('creator_role') or ''))+'</p><p class="small">Criada em '+fmt_epoch(policy.get('created_at'))+'</p>'+pair_note+pair_key+pair_controls+admin_note+admin_controls+revoke+'</div></article>')
 policy_section='<section class="card" id="persistent-approval-policies"><div class="section-title"><div><h2>Sempre permitir</h2><p class="small">Políticas persistentes por projeto, ação e solicitante. Podem cobrir ações críticas, mas não desativam controles técnicos nem auditoria.</p></div></div><div class="backup-list">'+(''.join(policy_cards) or '<div class="box">Nenhuma política persistente ativa.</div>')+'</div></section>'
 history_button=('<div class="approval-history-toolbar"><button class="btn btn-quiet approval-history-trigger" type="button" onclick="document.getElementById(\'approval-history-dialog\').showModal()">Carregar histórico ('+str(history)+')</button></div>') if history else ''
 history_head='<div class="approval-history-dialog__head"><div><h3 id="approval-history-title">Histórico de aprovações</h3><p>'+str(history)+' decisão'+('' if history==1 else 'ões')+' concluída'+('' if history==1 else 's')+'.</p></div><form method="dialog"><button class="btn btn-quiet" type="submit">Fechar</button></form></div>'
 if history_lazy:
  history_dialog=('<dialog id="approval-history-dialog" class="approval-history-dialog" aria-labelledby="approval-history-title">'+history_head+'<div class="approval-history-dialog__body"><div class="backup-list" id="approval-history-pages" data-endpoint="/cloudiff/portal/api/approvals?history=1" data-page="0" data-size="20"><div class="box">O histórico é carregado sob demanda.</div></div><div class="approval-history-toolbar"><button class="btn btn-quiet" id="approval-history-more" type="button">Carregar mais</button></div></div></dialog>'+HISTORY_LAZY_JS) if history else ''
 else:
  history_dialog=('<dialog id="approval-history-dialog" class="approval-history-dialog" aria-labelledby="approval-history-title">'+history_head+'<div class="approval-history-dialog__body"><div class="backup-list">'+(''.join(history_cards) or '<div class="box">Nenhum registro histórico.</div>')+'</div></div></dialog>') if history else ''
 return '<section class="card" id="human-approvals"><div class="section-title"><div><h2>Aprovações humanas</h2><p class="small">Cada decisão é vinculada ao projeto e ao conteúdo da operação. Marque “Sempre permitir” quando quiser transformar a decisão em uma política persistente para o mesmo projeto, ação e solicitante.</p></div></div><div class="backup-summary"><div class="backup-stat"><b>Pendentes</b><div class="kpi">'+str(pending)+'</div></div><div class="backup-stat"><b>Aprovadas</b><div class="kpi">'+str(approved)+'</div></div><div class="backup-stat"><b>Histórico</b><div class="kpi">'+str(history)+'</div></div></div><div class="backup-list">'+(''.join(cards) or '<div class="box">Nenhuma aprovação pendente ou aguardando consumo.</div>')+'</div>'+history_button+'</section>'+history_dialog+policy_section
