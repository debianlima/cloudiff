#!/usr/bin/env python3
import os,json,hmac,urllib.request,urllib.error,threading,time,uuid,hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
HOST=os.environ.get('CLOUDIF_MCP_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_MCP_PORT','18198'))
TOKEN=os.environ.get('CLOUDIF_MCP_TOKEN','');CONTROL=os.environ.get('CLOUDIF_CONTROL_URL','http://127.0.0.1:18197').rstrip('/');CONTROL_TOKEN=os.environ.get('CLOUDIF_CONTROL_TOKEN','')
AUDIT_URL=os.environ.get('CLOUDIF_AUDIT_URL','http://127.0.0.1:18201').rstrip('/')
AUDIT_TOKEN=os.environ.get('CLOUDIF_AUDIT_TOKEN','')
AGENT_URL=os.environ.get('CLOUDIF_AGENT_URL','http://127.0.0.1:18203').rstrip('/')
AGENT_ADMIN_TOKEN=os.environ.get('CLOUDIF_AGENT_ADMIN_TOKEN','')
WORKSPACE_URL=os.environ.get('CLOUDIF_WORKSPACE_URL','http://127.0.0.1:18206').rstrip('/')
WORKSPACE_TOKEN=os.environ.get('CLOUDIF_WORKSPACE_TOKEN','')
APPROVAL_URL=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204').rstrip('/')
APPROVAL_TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','')
FORJA_URL=os.environ.get('CLOUDIF_FORJA_AGENT_URL','http://10.62.91.2:18095').rstrip('/')
FORJA_TOKEN=os.environ.get('CLOUDIF_FORJA_AGENT_TOKEN','')
DEPLOYMENT_URL=os.environ.get('CLOUDIF_DEPLOYMENT_BROKER_URL','http://127.0.0.1:18207').rstrip('/')
DEPLOYMENT_TOKEN=os.environ.get('CLOUDIF_DEPLOYMENT_BROKER_TOKEN','')
RUNTIME_URL=os.environ.get('CLOUDIF_RUNTIME_URL','http://127.0.0.1:18212').rstrip('/')
BUILD_URL=os.environ.get('CLOUDIF_BUILD_URL','http://127.0.0.1:18213').rstrip('/')
BUILD_TOKEN=os.environ.get('CLOUDIF_BUILD_TOKEN','')
PREVIEW_URL=os.environ.get('CLOUDIF_PREVIEW_URL','http://127.0.0.1:18214').rstrip('/')
PREVIEW_TOKEN=os.environ.get('CLOUDIF_PREVIEW_TOKEN','')
def audit_async(event):
    if not AUDIT_TOKEN:return
    def run():
        try:
            req=urllib.request.Request(AUDIT_URL+'/v1/events',data=json.dumps(event,separators=(',',':')).encode(),method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+AUDIT_TOKEN})
            urllib.request.urlopen(req,timeout=2).read()
        except Exception:pass
    threading.Thread(target=run,daemon=True).start()
TOOLS=[
 {'name':'project.list','description':'Lista projetos registrados na CloudIFF','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'project.get','description':'Obtém projeto pelo slug','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.connectors','description':'Lista conectores e ACL do projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1}},'required':['slug'],'additionalProperties':False}},
 {'name':'runtime.catalog','description':'Lista política homologada de runtimes e frameworks sem efeitos','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'runtime.detect','description':'Detecta framework a partir de evidências sanitizadas do workspace autorizado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'runtime.plan','description':'Gera plano declarativo usando somente templates homologados','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'runtime.validate','description':'Valida plano declarativo contra a política server-side','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'build.plan','description':'Gera plano de build imutável, side-effect-free e derivado da política homologada','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'build.request','description':'Reserva build estático idempotente na fila durável; Node permanece fail-closed','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'framework':{'type':'string','enum':['static']},'build_plan_digest':{'type':'string','pattern':'^[0-9a-f]{64}$'}},'required':['slug','ref','framework','build_plan_digest'],'additionalProperties':False}},
 {'name':'build.status','description':'Consulta status sanitizado de build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'build.logs.read','description':'Lê logs sanitizados de build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'build.artifact.get','description':'Obtém metadados imutáveis do artefato sem segredo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'deployment.preview.plan','description':'Planeja preview temporário por build sem criar URL ou efeito','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'},'commit_ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400}},'required':['slug','build_id','commit_ref'],'additionalProperties':False}},
 {'name':'deployment.preview.status','description':'Consulta estado sanitizado de preview temporário vinculado ao projeto autorizado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'preview_id':{'type':'string','pattern':'^prv_[0-9a-f]{20}$'}},'required':['slug','preview_id'],'additionalProperties':False}},
 {'name':'approval.request-preview','description':'Cria aprovação pendente vinculada ao digest canônico do preview','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'},'commit_ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400},'reason':{'type':'string','minLength':4,'maxLength':500}},'required':['slug','build_id','commit_ref','reason'],'additionalProperties':False}},
 {'name':'deployment.preview','description':'Cria preview HTTPS temporário aprovado com reserve-effect-finalize, TTL e remoção automática','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'},'commit_ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','build_id','commit_ref','approval_id'],'additionalProperties':False}},
 {'name':'workspace.probe','description':'Executa uma sonda efêmera isolada e sem rede para validar o workspace do projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.prepare','description':'Prepara e inspeciona um archive Forgejo autorizado em workspace efêmero somente leitura','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.validate','description':'Valida Compose e conteúdo estático do projeto sem iniciar serviços','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.test-static','description':'Executa validação Nginx de projeto estático em container efêmero sem rede','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.preview-static','description':'Executa preview HTTP descartável dentro de container isolado, sem publicar porta ou URL','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.edit-preview','description':'Aplica substituição textual única em HTML temporário, valida e executa preview sem persistir','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024}},'required':['slug','path','expected_sha256','find','replace'],'additionalProperties':False}},
 {'name':'forgejo.propose-edit','description':'Cria branch isolada e pull request rascunho após preview e aprovação vinculada de uso único','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000}},'required':['slug','approval_id','path','expected_sha256','find','replace','title','body'],'additionalProperties':False}},
 {'name':'forgejo.propose-edit.plan','description':'Calcula o digest canônico e o plano de uma proposta sem criar aprovação, branch ou pull request','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000}},'required':['slug','path','expected_sha256','find','replace','title','body'],'additionalProperties':False}},
 {'name':'approval.request-proposal','description':'Cria uma aprovação pendente vinculada ao digest canônico de uma proposta Forgejo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','path','expected_sha256','find','replace','title','body','reason'],'additionalProperties':False}},
 {'name':'approval.get','description':'Consulta uma aprovação própria vinculada ao projeto autorizado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','approval_id'],'additionalProperties':False}},
 {'name':'forgejo.proposal.list','description':'Lista pull requests do projeto autorizado por meio do agente da forja, sem efeitos persistentes','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'state':{'type':'string','enum':['open','closed','all']},'limit':{'type':'integer','minimum':1,'maximum':50}},'required':['slug'],'additionalProperties':False}},
 {'name':'forgejo.proposal.close','description':'Fecha um pull request CloudIFF controlado sem excluir a branch','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','number'],'additionalProperties':False}},
 {'name':'forgejo.proposal.delete-branch','description':'Exclui a branch cloudif-proposal de um pull request já fechado ou mesclado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','number'],'additionalProperties':False}},
 {'name':'forgejo.proposal.merge.plan','description':'Calcula o digest canônico para merge aprovado de um PR CloudIFF','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'}},'required':['slug','number','expected_head_sha'],'additionalProperties':False}},
 {'name':'approval.request-merge','description':'Cria aprovação pendente vinculada ao merge de um PR e SHA específicos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','number','expected_head_sha','reason'],'additionalProperties':False}},
 {'name':'forgejo.proposal.merge','description':'Mescla PR CloudIFF após aprovação humana persistente de uso único','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','number','expected_head_sha','approval_id'],'additionalProperties':False}},
 {'name':'supabase.migrations.inspect','description':'Inspeciona migrações SQL versionadas em um commit sem expor conteúdo e sem alterar o banco','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120}},'required':['slug','commit_sha','version'],'additionalProperties':False}},
 {'name':'supabase.migrations.plan','description':'Gera plano sem efeitos para migrações versionadas apenas no ambiente isolated-test','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120}},'required':['slug','commit_sha','version'],'additionalProperties':False}},
 {'name':'deployment.production.homologation.plan','description':'Planeja publicação blue/green somente no alvo descartável de homologação','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']},'build_id':{'type':'string','pattern':'^[0-9a-f-]{36}$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'approval.request-production-homologation','description':'Solicita aprovação humana de uso único para deploy ou rollback blue/green de homologação','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']},'operation':{'type':'string','enum':['deploy','rollback']},'build_id':{'type':'string','pattern':'^[0-9a-f-]{36}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','operation','reason'],'additionalProperties':False}},
 {'name':'deployment.production.homologation.deploy','description':'Executa publicação blue/green aprovada somente no alvo de homologação','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']},'build_id':{'type':'string','pattern':'^[0-9a-f-]{36}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','build_id','approval_id'],'additionalProperties':False}},
 {'name':'deployment.production.homologation.rollback','description':'Executa rollback blue/green aprovado somente no alvo de homologação','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','approval_id'],'additionalProperties':False}},
 {'name':'deployment.production.activation.plan','description':'Gera plano canônico sem efeitos para ativação futura do alvo real selado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']}},'required':['slug'],'additionalProperties':False}},
 {'name':'approval.request-production-activation','description':'Cria dupla aprovação vinculada ao digest exato do plano de ativação real, sem executar efeitos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['atalhos-cloudif-iff1860746']},'reason':{'type':'string','minLength':8,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':3600}},'required':['slug','reason'],'additionalProperties':False}},
 {'name':'deployment.production.readiness','description':'Mostra requisitos e bloqueios do ambiente de produção sem executar efeitos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'deployment.production.plan','description':'Planeja deploy de produção sem efeitos e só libera quando o alvo estiver completamente configurado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120}},'required':['slug','commit_sha','version'],'additionalProperties':False}},
 {'name':'deployment.plan','description':'Planeja validação seca de deploy sem criar release, backup, migração ou stack','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120}},'required':['slug','commit_sha','version'],'additionalProperties':False}},
 {'name':'approval.request-deploy','description':'Cria aprovação pendente vinculada a projeto, commit e versão para validação seca','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','commit_sha','version','reason'],'additionalProperties':False}},
 {'name':'deployment.validate','description':'Executa validação seca aprovada; nunca cria release, backup, migração ou deploy Komodo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','commit_sha','version','approval_id'],'additionalProperties':False}},
 {'name':'deployment.promote-test.plan','description':'Planeja promoção real apenas no ambiente de teste isolado, com rollback obrigatório','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120}},'required':['slug','commit_sha','version'],'additionalProperties':False}},
 {'name':'approval.request-promote-test','description':'Cria aprovação pendente vinculada à promoção real no ambiente de teste','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120},'expected_previous_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','commit_sha','version','expected_previous_commit','reason'],'additionalProperties':False}},
 {'name':'deployment.promote-test','description':'Executa promoção real aprovada apenas no projeto de teste isolado, com rollback automático','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'commit_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'version':{'type':'string','minLength':5,'maxLength':120},'expected_previous_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','commit_sha','version','expected_previous_commit','approval_id'],'additionalProperties':False}},
 {'name':'deployment.promote-test.status','description':'Consulta somente leitura do estado de um job de promoção autorizado no ambiente de teste','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'job_id':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','job_id'],'additionalProperties':False}},
 {'name':'deployment.rollback-test.plan','description':'Planeja rollback manual apenas para um job histórico publicado do ambiente isolado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'target_job_id':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','target_job_id'],'additionalProperties':False}},
 {'name':'approval.request-rollback-test','description':'Solicita aprovação humana separada para rollback manual no ambiente isolado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'target_job_id':{'type':'integer','minimum':1,'maximum':2147483647},'expected_current_job_id':{'type':'integer','minimum':1,'maximum':2147483647},'expected_current_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'target_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','target_job_id','expected_current_job_id','expected_current_commit','target_commit','reason'],'additionalProperties':False}},
 {'name':'deployment.rollback-test','description':'Executa rollback manual aprovado para release histórica do ambiente isolado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','enum':['sistema-de-biblioteca-teste']},'target_job_id':{'type':'integer','minimum':1,'maximum':2147483647},'expected_current_job_id':{'type':'integer','minimum':1,'maximum':2147483647},'expected_current_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'target_commit':{'type':'string','pattern':'^[a-f0-9]{40}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','target_job_id','expected_current_job_id','expected_current_commit','target_commit','approval_id'],'additionalProperties':False}},
]
def control(path):
    r=urllib.request.Request(CONTROL+path,headers={'Authorization':'Bearer '+CONTROL_TOKEN,'Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=8) as x:return json.loads(x.read().decode())
def workspace_probe(slug,trace_id):
    payload=json.dumps({'project_slug':slug,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/probe',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=15) as x:return json.loads(x.read().decode())
def workspace_prepare(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/prepare',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=45) as x:return json.loads(x.read().decode())
def workspace_validate(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/validate',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=45) as x:return json.loads(x.read().decode())
def workspace_test_static(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/test-static',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode())
def workspace_preview_static(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/preview-static',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=75) as x:return json.loads(x.read().decode())
def workspace_edit_preview(slug,ref,path,expected_sha256,find_text,replace_text,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id,'path':path,'expected_sha256':expected_sha256,'find':find_text,'replace':replace_text},ensure_ascii=False,separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/edit-preview',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=90) as x:return json.loads(x.read().decode())
def proposal_digest(slug,path,expected_sha256,find_text,replace_text,title,body):
    canonical={'action':'forgejo.propose-edit','base_branch':'main','body':body,'expected_sha256':expected_sha256,'find':find_text,'path':path,'project_slug':slug,'replace':replace_text,'title':title}
    raw=json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()
def approval_get(approval_id):
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=8) as x:data=json.load(x)
    return next((a for a in data.get('approvals',[]) if a.get('approval_id')==approval_id),None)
def approval_consume(approval_id):
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals/'+urllib.parse.quote(approval_id,safe='')+'/consume',data=b'{}',method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        raise ValueError('approval_consume_failed') from e
def transaction_ids(action,approval_id,client_id,digest):
    raw=json.dumps({'action':action,'approval_id':approval_id,'client_id':client_id,'digest':digest},sort_keys=True,separators=(',',':')).encode()
    h=hashlib.sha256(raw).hexdigest()
    return 'res_'+h[:32],'exec_'+h[32:64]
def approval_transition(approval_id,operation,payload):
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals/'+urllib.parse.quote(approval_id,safe='')+'/'+operation,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
def deployment_effect_call(path,slug,commit_sha,version,trace_id,execution_id,timeout=300):
    payload={'project_slug':slug,'commit_sha':commit_sha,'version':version,'trace_id':trace_id,'execution_id':execution_id}
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
def approval_create(project_slug,requested_by,reason,ttl_seconds,trace_id,digest):
    payload={'project_slug':project_slug,'action':'forgejo.propose-edit','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':{'proposal_digest':digest}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e
def forgejo_propose(payload):
    req=urllib.request.Request(FORJA_URL+'/project/proposal/create',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Authorization':'Bearer '+FORJA_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'forgejo_proposal_failed')) from e
def forgejo_proposal_list(slug,state,limit):
    query=urllib.parse.urlencode({'slug':slug,'state':state,'limit':limit})
    req=urllib.request.Request(FORJA_URL+'/project/proposals?'+query,headers={'X-CloudIF-Token':FORJA_TOKEN,'Authorization':'Bearer '+FORJA_TOKEN,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'forgejo_proposal_list_failed')) from e
def merge_digest(client_id,slug,number,expected_head_sha):
    canonical={'action':'forgejo.proposal.merge','client_id':client_id,'project_slug':slug,'proposal_number':number,'expected_head_sha':expected_head_sha}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def approval_create_merge(project_slug,requested_by,reason,ttl_seconds,trace_id,digest,number,expected_head_sha):
    payload={'project_slug':project_slug,'action':'forgejo.proposal.merge','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':{'merge_digest':digest,'proposal_number':number,'expected_head_sha':expected_head_sha}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e
def forgejo_proposal_merge(slug,number,expected_head_sha,approval_id,requested_by,trace_id):
    payload={'project_slug':slug,'number':number,'expected_head_sha':expected_head_sha,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace_id}
    req=urllib.request.Request(FORJA_URL+'/project/proposal/merge',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=75) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'proposal_merge_failed')) from e
def forgejo_proposal_merge_txn(slug,number,expected_head_sha,approval_id,requested_by,reservation_id):
    payload={'project_slug':slug,'number':number,'expected_head_sha':expected_head_sha,'approval_id':approval_id,'requested_by':requested_by,'trace_id':'txn-'+reservation_id}
    req=urllib.request.Request(FORJA_URL+'/project/proposal/merge',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
    except Exception:
        return 599,{'ok':False,'error':'forgejo_response_unknown'}
def deployment_digest(client_id,slug,commit_sha,version):
    canonical={'action':'deployment.validate','client_id':client_id,'project_slug':slug,'commit_sha':commit_sha,'version':version,'dry_run':True}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def approval_create_deploy(project_slug,requested_by,reason,ttl_seconds,trace_id,digest,commit_sha,version):
    payload={'project_slug':project_slug,'action':'deployment.validate','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':{'deployment_digest':digest,'commit_sha':commit_sha,'version':version,'dry_run':True}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e
def deployment_call(path,slug,commit_sha,version,trace_id,timeout=180):
    payload={'project_slug':slug,'commit_sha':commit_sha,'version':version,'trace_id':trace_id}
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'deployment_broker_failed')) from e
def promotion_digest(client_id,slug,commit_sha,version,expected_previous_commit):
    canonical={'action':'deployment.promote-test','client_id':client_id,'project_slug':slug,'commit_sha':commit_sha,'version':version,'expected_previous_commit':expected_previous_commit,'target':'isolated-test','real_deploy':True}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def approval_create_promote_test(project_slug,requested_by,reason,ttl_seconds,trace_id,digest,commit_sha,version,expected_previous_commit):
    payload={'project_slug':project_slug,'action':'deployment.promote-test','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':{'promotion_digest':digest,'commit_sha':commit_sha,'version':version,'expected_previous_commit':expected_previous_commit,'target':'isolated-test','real_deploy':True}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e
def promotion_call(path,slug,commit_sha,version,expected_previous_commit,trace_id,timeout=600):
    payload={'project_slug':slug,'commit_sha':commit_sha,'version':version,'expected_previous_commit':expected_previous_commit,'trace_id':trace_id}
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        if e.code==409:raise ValueError('previous_commit_changed') from e
        raise ValueError(str(data.get('error') or 'deployment_broker_failed')) from e
def promotion_effect_call(path,slug,commit_sha,version,expected_previous_commit,execution_id,timeout=900):
    payload={'project_slug':slug,'commit_sha':commit_sha,'version':version,'expected_previous_commit':expected_previous_commit,'trace_id':'txn-'+execution_id,'execution_id':execution_id}
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
def deployment_status(job_id):
    req=urllib.request.Request(DEPLOYMENT_URL+'/v1/status?job_id='+str(int(job_id)),headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data

def rollback_digest(client_id,slug,target_job_id,expected_current_job_id,expected_current_commit,target_commit):
    canonical={'action':'deployment.rollback-test','client_id':client_id,'project_slug':slug,'target_job_id':int(target_job_id),'expected_current_job_id':int(expected_current_job_id),'expected_current_commit':expected_current_commit,'target_commit':target_commit,'target':'isolated-test','real_deploy':True}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rollback_plan_call(slug,target_job_id,trace_id):
    payload={'project_slug':slug,'target_job_id':int(target_job_id),'trace_id':trace_id}
    req=urllib.request.Request(DEPLOYMENT_URL+'/v1/plan-rollback-test',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
def rollback_effect_call(slug,target_job_id,expected_current_job_id,expected_current_commit,execution_id,timeout=900):
    payload={'project_slug':slug,'target_job_id':int(target_job_id),'expected_current_job_id':int(expected_current_job_id),'expected_current_commit':expected_current_commit,'trace_id':'txn-'+execution_id,'execution_id':execution_id}
    req=urllib.request.Request(DEPLOYMENT_URL+'/v1/rollback-test',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
def approval_create_rollback_test(project_slug,requested_by,reason,ttl_seconds,trace_id,digest,target_job_id,expected_current_job_id,expected_current_commit,target_commit):
    metadata={'rollback_digest':digest,'target_job_id':int(target_job_id),'expected_current_job_id':int(expected_current_job_id),'expected_current_commit':expected_current_commit,'target_commit':target_commit,'target':'isolated-test','real_deploy':True}
    payload={'project_slug':project_slug,'action':'deployment.rollback-test','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e

def migration_call(path,slug,commit_sha,version,trace_id):
    payload={'project_slug':slug,'commit_sha':commit_sha,'version':version,'trace_id':trace_id}
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=120) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data

AGENT_GUIDE_URI='cloudiff://guide/agent'
PROJECT_GUIDE_URI='cloudiff://guide/project/{slug}'
AGENT_INSTRUCTIONS="""Você está conectado ao MCP CloudIFF. Trabalhe somente nos projetos autorizados para esta identidade. Comece por project.list, project.get e project.connectors. Antes de qualquer efeito, gere plano e prévia. Aprovações humanas acontecem exclusivamente no Portal CloudIFF. Forgejo serve para revisão de código e Pull Requests; Supabase Studio para banco; Komodo para execução e deploy. Nunca solicite, revele ou grave tokens. Produção exige decisão de um administrador ou professor e permanece indisponível enquanto não houver alvo de produção configurado."""

def agent_guide_payload(slug=''):
    return {'version':'90A','language':'pt-BR','project_slug':slug,'workflow':['project.list','project.get','project.connectors','workspace.prepare','workspace.validate','workspace.test-static','workspace.preview-static','forgejo.propose-edit.plan','approval.request-proposal','forgejo.propose-edit'],'approvals':{'decided_in':'Portal CloudIFF','forgejo':'revisão de código e Pull Requests','supabase':'dados e banco','komodo':'execução, containers e deploys'},'security':{'direct_infrastructure_access':False,'arbitrary_terminal':False,'direct_main_push':False,'credentials_must_not_be_requested':True,'production_requires_one_admin_or_professor':True,'two_approvers_required':False,'production_target_configured':False},'instructions':AGENT_INSTRUCTIONS}

def production_info_call(path,payload,timeout=120):
    req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data

def homologation_digest(client_id,slug,build_id,broker_digest):
 return hashlib.sha256(json.dumps({'action':'deployment.production.homologation','client_id':client_id,'project_slug':slug,'build_id':build_id,'broker_digest':broker_digest},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def approval_create_homologation(slug,requested_by,reason,ttl,trace,digest,build_id,kind):
 payload={'project_slug':slug,'action':kind,'requested_by':requested_by,'ttl_seconds':ttl,'reason':reason,'trace_id':trace,'metadata':{'homologation_digest':digest,'build_id':build_id,'target':'production-homologation','homologation_only':True}}
 req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=10) as x:return json.load(x)
def homologation_call(path,payload,timeout=300):
 req=urllib.request.Request(DEPLOYMENT_URL+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
 except urllib.error.HTTPError as e:
  try:b=json.load(e)
  except Exception:b={}
  return e.code,b

SCOPE_BY_TOOL={
 'runtime.catalog':'project:read','runtime.detect':'project:read','runtime.plan':'project:read','runtime.validate':'project:read','build.plan':'project:read','build.request':'workspace:test-static','build.status':'project:read','build.logs.read':'project:read','build.artifact.get':'project:read','deployment.preview.plan':'project:read','deployment.preview.status':'project:read','approval.request-preview':'approval:request-preview','deployment.preview':'deployment:preview',
 'workspace.probe':'workspace:probe','workspace.prepare':'workspace:prepare','workspace.validate':'workspace:validate','workspace.test-static':'workspace:test-static','workspace.preview-static':'workspace:preview-static','workspace.edit-preview':'workspace:edit-preview',
 'forgejo.propose-edit':'forgejo:propose-edit','forgejo.propose-edit.plan':'forgejo:plan-edit','approval.request-proposal':'approval:request-proposal','approval.get':'approval:read-own','forgejo.proposal.list':'forgejo:proposal-read','forgejo.proposal.close':'forgejo:proposal-close','forgejo.proposal.delete-branch':'forgejo:proposal-delete-branch','forgejo.proposal.merge.plan':'forgejo:proposal-merge-plan','approval.request-merge':'approval:request-merge','forgejo.proposal.merge':'forgejo:proposal-merge',
 'deployment.production.homologation.plan':'deployment:production-plan','approval.request-production-homologation':'approval:request-deploy','deployment.production.homologation.deploy':'deployment:production-plan','deployment.production.homologation.rollback':'deployment:production-plan','deployment.production.activation.plan':'deployment:production-plan','approval.request-production-activation':'approval:request-deploy','deployment.production.readiness':'project:read','deployment.production.plan':'deployment:production-plan','supabase.migrations.inspect':'supabase:migration-inspect','supabase.migrations.plan':'supabase:migration-plan','deployment.plan':'deployment:plan','approval.request-deploy':'approval:request-deploy','deployment.validate':'deployment:validate','deployment.promote-test.plan':'deployment:promote-test-plan','approval.request-promote-test':'approval:request-promote-test','deployment.promote-test':'deployment:promote-test','deployment.promote-test.status':'deployment:promote-test-status','deployment.rollback-test.plan':'deployment:rollback-test-plan','approval.request-rollback-test':'approval:request-rollback-test','deployment.rollback-test':'deployment:rollback-test'
}
def forgejo_proposal_action(action,slug,number,requested_by,trace_id):
    if action not in {'close','delete-branch'}:raise ValueError('invalid_proposal_action')
    payload={'project_slug':slug,'number':number,'trace_id':trace_id,'requested_by':requested_by}
    req=urllib.request.Request(FORJA_URL+'/project/proposal/'+action,data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Authorization':'Bearer '+FORJA_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'forgejo_proposal_action_failed')) from e
def preview_digest(client_id,slug,build_id,commit_ref):
    canonical={'project_slug':slug,'build_id':build_id,'commit_ref':commit_ref,'ttl_seconds':3600,'operation_type':'deployment.preview','public_url_ready':False}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def approval_create_preview(project_slug,requested_by,reason,ttl_seconds,trace_id,digest,build_id,commit_ref):
    payload={'project_slug':project_slug,'action':'deployment.preview','requested_by':requested_by,'ttl_seconds':ttl_seconds,'reason':reason,'trace_id':trace_id,'metadata':{'preview_plan_digest':digest,'build_id':build_id,'commit_ref':commit_ref,'public_url_ready':False}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e

def preview_call(path,payload=None):
    data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
    req=urllib.request.Request(PREVIEW_URL+path,data=data,method='GET' if data is None else 'POST',headers={'Authorization':'Bearer '+PREVIEW_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as x:return json.load(x)

def build_call(path,payload=None):
    data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
    req=urllib.request.Request(BUILD_URL+path,data=data,method='GET' if data is None else 'POST',headers={'Authorization':'Bearer '+BUILD_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as x:return json.load(x)

def runtime_call(path,payload=None):
    data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
    req=urllib.request.Request(RUNTIME_URL+path,data=data,method='GET' if data is None else 'POST',headers={'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as x:return json.load(x)

class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def sendj(self,code,data):
        ctx=getattr(self,'_audit_ctx',None)
        if ctx and not getattr(self,'_audit_sent',False):
            self._audit_sent=True
            event=dict(ctx);event['result']='error' if code>=400 or (isinstance(data,dict) and data.get('error')) else 'success';event['duration_ms']=int((time.monotonic()-event.pop('_start'))*1000)
            audit_async(event)
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def auth(self):
        client=self.headers.get('X-CloudIF-Client','').strip();got=self.headers.get('Authorization','')
        if client:return got.startswith('Bearer ') and len(got)>20
        return bool(TOKEN) and hmac.compare_digest(got,'Bearer '+TOKEN)
    def authorize_client(self,scope,slug):
        client=self.headers.get('X-CloudIF-Client','').strip()
        if not client:return {'ok':True,'legacy':True,'client_id':'internal'}
        raw=self.headers.get('Authorization','')[7:]
        payload=json.dumps({'client_id':client,'token':raw,'scope':scope,'project_slug':slug},separators=(',',':')).encode()
        req=urllib.request.Request(AGENT_URL+'/v1/authorize',data=payload,method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+AGENT_ADMIN_TOKEN})
        with urllib.request.urlopen(req,timeout=5) as x:return json.load(x)
    def do_GET(self):
        if urlparse(self.path).path=='/health':
            try: h=control('/health');self.sendj(200,{'ok':True,'service':'cloudif-mcp-gateway','control_plane':bool(h.get('ok'))})
            except Exception:self.sendj(503,{'ok':False,'error':'control_plane_unavailable'})
        else:self.sendj(404,{'ok':False,'error':'not_found'})
    def do_POST(self):
        if urlparse(self.path).path!='/mcp':self.sendj(404,{'ok':False,'error':'not_found'});return
        if not self.auth():self.sendj(401,{'ok':False,'error':'unauthorized'});return
        try:
            n=int(self.headers.get('Content-Length','0')); raw=self.rfile.read(min(n,1048576)); req=json.loads(raw or b'{}')
            rid=req.get('id'); method=req.get('method'); params=req.get('params') or {}
            args=params.get('arguments') or {};tool=params.get('name') if method=='tools/call' else method
            slug=str(args.get('slug') or '')
            scope=SCOPE_BY_TOOL.get(tool,'project:read')
            trace_id=self.headers.get('X-CloudIF-Trace-Id') or uuid.uuid4().hex
            authz=self.authorize_client(scope,slug)
            if not authz.get('ok'):
                reason=authz.get('reason','denied');self.sendj(429 if reason in {'rate_limit','daily_quota'} else 403,{'jsonrpc':'2.0','id':rid,'error':{'code':-32029 if reason in {'rate_limit','daily_quota'} else -32003,'message':reason}});return
            self._audit_ctx={'event_id':uuid.uuid4().hex,'source':'mcp','action':str(tool or method or 'unknown'),'actor_type':'agent' if self.headers.get('X-CloudIF-Client') else 'api_client','actor_id':self.headers.get('X-CloudIF-User','') or authz.get('owner_user',''),'delegated_user_id':self.headers.get('X-CloudIF-Delegated-User',''),'client_id':self.headers.get('X-CloudIF-Client','internal'),'project_slug':slug,'trace_id':trace_id,'attrs':{'rpc_method':method,'quota':{'minute_calls':authz.get('minute_calls'),'daily_calls':authz.get('daily_calls')}},'_start':time.monotonic()}
            if method=='initialize':result={'protocolVersion':'2025-03-26','serverInfo':{'name':'cloudif-mcp-gateway','version':'0.2.0'},'capabilities':{'tools':{},'resources':{},'prompts':{}},'instructions':AGENT_INSTRUCTIONS}
            elif method=='resources/list':result={'resources':[{'uri':AGENT_GUIDE_URI,'name':'Guia do agente CloudIFF','description':'Como usar ferramentas, aprovações, portais e limites de segurança.','mimeType':'application/json'},{'uri':'cloudiff://guide/project/{slug}','name':'Guia do projeto','description':'Fluxo recomendado para um projeto autorizado.','mimeType':'application/json'}]}
            elif method=='resources/read':
                uri=str(params.get('uri') or '')
                if uri==AGENT_GUIDE_URI:data=agent_guide_payload('')
                elif uri.startswith('cloudiff://guide/project/'):
                    pslug=uri.rsplit('/',1)[-1].strip()
                    if not pslug:raise ValueError('project_slug_required')
                    control('/v1/projects/'+urllib.parse.quote(pslug,safe=''));data=agent_guide_payload(pslug)
                else:raise ValueError('resource_not_found')
                result={'contents':[{'uri':uri,'mimeType':'application/json','text':json.dumps(data,ensure_ascii=False,separators=(',',':'))}]}
            elif method=='prompts/list':result={'prompts':[{'name':'cloudiff-project-workflow','description':'Instrução inicial segura para trabalhar em um projeto CloudIFF.','arguments':[{'name':'slug','description':'Slug do projeto autorizado','required':True}]},{'name':'cloudiff-production-policy','description':'Explica a política de autorização humana para produção.','arguments':[]}]}
            elif method=='prompts/get':
                pname=str(params.get('name') or '');pargs=params.get('arguments') or {}
                if pname=='cloudiff-project-workflow':
                    pslug=str(pargs.get('slug') or '').strip()
                    if not pslug:raise ValueError('project_slug_required')
                    control('/v1/projects/'+urllib.parse.quote(pslug,safe=''))
                    text=f'Trabalhe somente no projeto {pslug}. Leia cloudiff://guide/project/{pslug}. Comece por project.get e project.connectors. Gere plano e prévia antes de alterações. Solicite aprovação no Portal CloudIFF quando a ferramenta exigir. Não use terminal arbitrário, não faça push direto em main e não revele credenciais.'
                elif pname=='cloudiff-production-policy':text='Produção usa uma única decisão humana: administrador ou professor pode autorizar sozinho; solicitação de aluno ou agente permanece pendente até um administrador ou professor aprovar. Dois aprovadores não são exigidos. A execução real só pode ocorrer quando existir alvo de produção separado, smoke e rollback configurados.'
                else:raise ValueError('prompt_not_found')
                result={'description':'Orientação CloudIFF','messages':[{'role':'user','content':{'type':'text','text':text}}]}
            elif method=='tools/list':result={'tools':TOOLS}
            elif method=='tools/call':
                name=params.get('name');args=params.get('arguments') or {}
                if name=='project.list': data=control('/v1/projects');content=data.get('projects',[])
                elif name in {'project.get','project.connectors'}:
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    data=control('/v1/projects/'+urllib.parse.quote(slug,safe=''));content=data.get('project') if name=='project.get' else {'connectors':data.get('connectors',[]),'acl':data.get('acl',[])}
                elif name=='runtime.catalog':
                    if args:raise ValueError('argumentos inválidos')
                    content=runtime_call('/v1/catalog')
                elif name=='runtime.detect':
                    if 'slug' not in args or not set(args).issubset({'slug','ref'}):raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    evidence=workspace_validate(slug,ref,trace_id).get('result') or {}
                    safe={k:evidence.get(k) for k in ('technologies','compose','static')};content=runtime_call('/v1/detect',safe);content['project_slug']=slug;content['ref']=ref
                elif name in {'runtime.plan','runtime.validate','build.plan'}:
                    if 'framework' not in args or not set(args).issubset({'framework','runtime_version','package_manager'}):raise ValueError('argumentos inválidos')
                    content=runtime_call('/v1/'+('plan' if name.endswith('.plan') else 'validate'),args); content['operation_type']='build.plan' if name=='build.plan' else name
                elif name=='build.request':
                    if set(args)!={'slug','ref','framework','build_plan_digest'}:raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(str(args['slug']),safe=''))
                    content=build_call('/v1/builds',{'project_slug':args['slug'],'ref':args['ref'],'framework':args['framework'],'build_plan_digest':args['build_plan_digest']})
                elif name in {'build.status','build.logs.read','build.artifact.get'}:
                    if set(args)!={'slug','build_id'}:raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    suffix='' if name=='build.status' else ('/logs' if name=='build.logs.read' else '/artifact')
                    content=build_call('/v1/projects/'+urllib.parse.quote(slug,safe='')+'/builds/'+urllib.parse.quote(str(args['build_id']),safe='')+suffix)
                elif name=='deployment.preview.plan':
                    if not {'slug','build_id','commit_ref'}<=set(args) or not set(args).issubset({'slug','build_id','commit_ref','ttl_seconds'}):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(str(args['slug']),safe=''))
                    content=preview_call('/v1/plan',{'project_slug':args['slug'],'build_id':args['build_id'],'commit_ref':args['commit_ref'],'ttl_seconds':int(args.get('ttl_seconds') or 3600)})
                elif name=='deployment.preview.status':
                    if set(args)!={'slug','preview_id'}:raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    content=preview_call('/v1/projects/'+urllib.parse.quote(slug,safe='')+'/previews/'+urllib.parse.quote(str(args['preview_id']),safe=''))
                elif name=='approval.request-preview':
                    required={'slug','build_id','commit_ref','reason'}
                    if not required.issubset(args) or not set(args).issubset(required|{'ttl_seconds'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();build_id=str(args['build_id']).strip();commit_ref=str(args['commit_ref']).strip();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if not (4<=len(reason)<=500) or not (300<=ttl<=86400):raise ValueError('aprovação inválida')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));planned=preview_call('/v1/plan',{'project_slug':slug,'build_id':build_id,'commit_ref':commit_ref,'ttl_seconds':3600});digest=planned.get('preview_plan_digest');art=planned.get('artifact') or {}
                    if not digest or not art.get('artifact_image_id') or not art.get('immutable_source_digest'):raise ValueError('preview_plan_binding_failed')
                    created=approval_create_preview(slug,client_id,reason,ttl,trace_id,digest,build_id,commit_ref)
                    if created.get('status')!='pending':raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'preview_plan_digest':digest,'artifact_image_id':art.get('artifact_image_id'),'immutable_source_digest':art.get('immutable_source_digest'),'public_url_ready':False,'two_approvers_required':False}
                elif name=='deployment.preview':
                    if set(args)!={'slug','build_id','commit_ref','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();build_id=str(args['build_id']).strip();commit_ref=str(args['commit_ref']).strip();approval_id=str(args['approval_id']).strip()
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));planned=preview_call('/v1/plan',{'project_slug':slug,'build_id':build_id,'commit_ref':commit_ref,'ttl_seconds':3600});digest=planned.get('preview_plan_digest');row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    expected={'preview_plan_digest':digest,'build_id':build_id,'commit_ref':commit_ref,'public_url_ready':False}
                    reservation_id,execution_id=transaction_ids('deployment.preview',approval_id,client_id,digest)
                    valid=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    if not row or not valid or row.get('project_slug')!=slug or row.get('action')!='deployment.preview' or row.get('requested_by')!=client_id or not row.get('approved_by') or meta!=expected:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,res=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':600})
                        if rc!=200 or res.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    ws=workspace_preview_static(slug,commit_ref,'txn-'+execution_id)
                    valid_ws=bool(ws.get('ok') and (ws.get('result') or {}).get('valid'))
                    if not valid_ws:
                        current=approval_get(approval_id)
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        raise ValueError('preview_validation_failed')
                    data=preview_call('/v1/effect',{'project_slug':slug,'build_id':build_id,'commit_ref':commit_ref,'preview_plan_digest':digest,'approval_id':approval_id,'execution_id':execution_id})
                    if not data.get('ok') or data.get('status') not in {'validated','active'}:raise ValueError('preview_effect_failed')
                    current=approval_get(approval_id)
                    if current and current.get('status')!='consumed':
                        fc,fin=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                        if fc!=200 or fin.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                    data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};data['workspace_validated']=True;content=data
                elif name=='workspace.probe':
                    if set(args)!={'slug'}:raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    # Confirm project existence before invoking the privileged broker.
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_probe(slug,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='workspace.prepare':
                    if not set(args).issubset({'slug','ref'}) or 'slug' not in args:raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('ref inválida')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_prepare(slug,ref,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='workspace.validate':
                    if not set(args).issubset({'slug','ref'}) or 'slug' not in args:raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('ref inválida')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_validate(slug,ref,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='workspace.test-static':
                    if not set(args).issubset({'slug','ref'}) or 'slug' not in args:raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('ref inválida')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_test_static(slug,ref,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='workspace.preview-static':
                    if not set(args).issubset({'slug','ref'}) or 'slug' not in args:raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('ref inválida')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_preview_static(slug,ref,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='workspace.edit-preview':
                    required={'slug','path','expected_sha256','find','replace'}
                    if not required.issubset(args) or not set(args).issubset(required|{'ref'}):raise ValueError('argumentos inválidos')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();path=str(args.get('path') or '').strip();expected=str(args.get('expected_sha256') or '').strip();find_text=str(args.get('find') or '');replace_text=str(args.get('replace') or '')
                    if not slug:raise ValueError('slug obrigatório')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('ref inválida')
                    if not path.startswith('site/') or '..' in path or not path.endswith('.html'):raise ValueError('path inválido')
                    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('sha256 inválido')
                    if not (1<=len(find_text)<=512) or len(replace_text)>1024:raise ValueError('limite de texto inválido')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_edit_preview(slug,ref,path,expected,find_text,replace_text,trace_id)
                    if not data.get('ok'):raise ValueError('workspace indisponível')
                    content=data
                elif name=='deployment.promote-test.plan':
                    if set(args)!={'slug','commit_sha','version'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip();version=str(args['version']).strip()
                    if slug!='sistema-de-biblioteca-teste' or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit) or not (5<=len(version)<=120):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=deployment_call('/v1/plan-promote-test',slug,commit,version,trace_id,45)
                    if not plan.get('ok') or plan.get('side_effect_free') is not True or plan.get('rollback_required') is not True:raise ValueError('promotion_plan_failed')
                    prev=str((plan.get('operation') or {}).get('expected_previous_commit') or '')
                    if len(prev)!=40:raise ValueError('promotion_plan_failed')
                    digest=promotion_digest(client_id,slug,commit,version,prev)
                    content={'ok':True,'side_effect_free':True,'promotion_digest':digest,'operation':plan['operation'],'prestate':plan['prestate'],'rollback_required':True,'approval_requirements':{'action':'deployment.promote-test','requested_by':client_id,'metadata':{'promotion_digest':digest,'commit_sha':commit,'version':version,'expected_previous_commit':prev,'target':'isolated-test','real_deploy':True}}}
                elif name=='approval.request-promote-test':
                    required={'slug','commit_sha','version','expected_previous_commit','reason'}
                    if not required.issubset(args) or not set(args).issubset(required|{'ttl_seconds'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip();version=str(args['version']).strip();prev=str(args['expected_previous_commit']).strip();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if slug!='sistema-de-biblioteca-teste' or len(commit)!=40 or len(prev)!=40 or not (5<=len(version)<=120) or not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=promotion_digest(client_id,slug,commit,version,prev)
                    created=approval_create_promote_test(slug,client_id,reason,ttl,trace_id,digest,commit,version,prev)
                    if created.get('status')!='pending':raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'promotion_digest':digest,'side_effects':{'release':False,'backup':False,'migrations':False,'komodo':False}}
                elif name=='deployment.promote-test':
                    if set(args)!={'slug','commit_sha','version','expected_previous_commit','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip();version=str(args['version']).strip();prev=str(args['expected_previous_commit']).strip();approval_id=str(args['approval_id']).strip()
                    if slug!='sistema-de-biblioteca-teste' or len(commit)!=40 or len(prev)!=40 or len(approval_id)!=24 or not (5<=len(version)<=120):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=promotion_digest(client_id,slug,commit,version,prev);row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    expected_meta={'promotion_digest':digest,'commit_sha':commit,'version':version,'expected_previous_commit':prev,'target':'isolated-test','real_deploy':True}
                    reservation_id,execution_id=transaction_ids('deployment.promote-test',approval_id,client_id,digest)
                    valid_status=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    if not row or not valid_status or row.get('project_slug')!=slug or row.get('action')!='deployment.promote-test' or row.get('requested_by')!=client_id or not row.get('approved_by') or meta!=expected_meta:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if rc!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,data=promotion_effect_call('/v1/promote-test',slug,commit,version,prev,execution_id,900)
                    if code==409 and data.get('error') in {'execution_in_progress','execution_id_conflict'}:raise ValueError(data.get('error'))
                    success=bool(code==200 and data.get('ok') and data.get('status')=='published' and data.get('release_id') and data.get('backup_path') and data.get('migrations_applied')==0 and data.get('komodo_called') is True and (data.get('postcheck') or {}).get('status_ready') is True and (data.get('postcheck') or {}).get('http_smoke') is True)
                    current=approval_get(approval_id)
                    if success:
                        if current and current.get('status')!='consumed':
                            fc,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if fc!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};content=data
                    else:
                        effect_started=bool(data.get('effect_started'))
                        if current and current.get('status')=='reserved':
                            op='finalize' if effect_started else 'release';payload={'reservation_id':reservation_id,'result':'completed'} if effect_started else {'reservation_id':reservation_id};approval_transition(approval_id,op,payload)
                        raise ValueError(str(data.get('error') or 'promotion_failed'))
                elif name=='deployment.rollback-test.plan':
                    if set(args)!={'slug','target_job_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']).strip();target_job_id=int(args['target_job_id'])
                    if not client_id:raise ValueError('identified_client_required')
                    if slug!='sistema-de-biblioteca-teste' or target_job_id<1:raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));code,plan=rollback_plan_call(slug,target_job_id,trace_id)
                    if code!=200 or not plan.get('ok') or plan.get('side_effect_free') is not True:raise ValueError(str(plan.get('error') or 'rollback_plan_failed'))
                    op=plan['operation'];digest=rollback_digest(client_id,slug,target_job_id,op['expected_current_job_id'],op['expected_current_commit'],op['target_commit'])
                    content={'ok':True,'side_effect_free':True,'rollback_digest':digest,'operation':op,'prestate':plan['prestate'],'target_release':plan['target_release'],'approval_requirements':{'action':'deployment.rollback-test','requested_by':client_id,'metadata':{'rollback_digest':digest,'target_job_id':target_job_id,'expected_current_job_id':op['expected_current_job_id'],'expected_current_commit':op['expected_current_commit'],'target_commit':op['target_commit'],'target':'isolated-test','real_deploy':True}}}
                elif name=='approval.request-rollback-test':
                    required={'slug','target_job_id','expected_current_job_id','expected_current_commit','target_commit','reason'}
                    if not required.issubset(args) or not set(args).issubset(required|{'ttl_seconds'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']).strip();target_job_id=int(args['target_job_id']);current_job_id=int(args['expected_current_job_id']);current_commit=str(args['expected_current_commit']).strip();target_commit=str(args['target_commit']).strip();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if not client_id:raise ValueError('identified_client_required')
                    if slug!='sistema-de-biblioteca-teste' or target_job_id<1 or current_job_id<1 or len(current_commit)!=40 or len(target_commit)!=40 or not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=rollback_digest(client_id,slug,target_job_id,current_job_id,current_commit,target_commit)
                    created=approval_create_rollback_test(slug,client_id,reason,ttl,trace_id,digest,target_job_id,current_job_id,current_commit,target_commit)
                    if created.get('status')!='pending':raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'rollback_digest':digest,'side_effects':{'backup':False,'komodo':False,'rollback':False}}
                elif name=='deployment.rollback-test':
                    if set(args)!={'slug','target_job_id','expected_current_job_id','expected_current_commit','target_commit','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']).strip();target_job_id=int(args['target_job_id']);current_job_id=int(args['expected_current_job_id']);current_commit=str(args['expected_current_commit']).strip();target_commit=str(args['target_commit']).strip();approval_id=str(args['approval_id']).strip()
                    if not client_id:raise ValueError('identified_client_required')
                    if slug!='sistema-de-biblioteca-teste' or target_job_id<1 or current_job_id<1 or len(current_commit)!=40 or len(target_commit)!=40 or len(approval_id)!=24:raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=rollback_digest(client_id,slug,target_job_id,current_job_id,current_commit,target_commit);row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    expected_meta={'rollback_digest':digest,'target_job_id':target_job_id,'expected_current_job_id':current_job_id,'expected_current_commit':current_commit,'target_commit':target_commit,'target':'isolated-test','real_deploy':True}
                    reservation_id,execution_id=transaction_ids('deployment.rollback-test',approval_id,client_id,digest)
                    valid_status=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    if not row or not valid_status or row.get('project_slug')!=slug or row.get('action')!='deployment.rollback-test' or row.get('requested_by')!=client_id or not row.get('approved_by') or meta!=expected_meta:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if rc!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,data=rollback_effect_call(slug,target_job_id,current_job_id,current_commit,execution_id,900)
                    success=bool(code==200 and data.get('ok') and data.get('operation')=='manual_rollback' and data.get('status')=='published' and data.get('target_job_id')==target_job_id and data.get('backup_path') and data.get('migrations_applied')==0 and data.get('komodo_called') is True and (data.get('postcheck') or {}).get('status_ready') is True and (data.get('postcheck') or {}).get('http_smoke') is True)
                    current=approval_get(approval_id)
                    if success:
                        if current and current.get('status')!='consumed':
                            fc,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if fc!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data.pop('backup_path',None);data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};data['sanitized']=True;data['secrets_exposed']=False;content=data
                    else:
                        if current and current.get('status')=='reserved':
                            if data.get('effect_started') is False:approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                            else:approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'completed'})
                        raise ValueError(str(data.get('error') or data.get('failure') or 'rollback_failed'))
                elif name=='deployment.promote-test.status':
                    if set(args)!={'slug','job_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();job_id=int(args['job_id'])
                    if slug!='sistema-de-biblioteca-teste' or not (1<=job_id<=2147483647):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=deployment_status(job_id)
                    if code==404:raise ValueError('job_not_found')
                    if code!=200 or not data.get('ok') or data.get('read_only') is not True:raise ValueError('deployment_status_failed')
                    job=data.get('job') or {}
                    if job.get('project')!=slug:raise ValueError('job_project_mismatch')
                    safe={k:job.get(k) for k in ('id','created_at','scheduled_at','started_at','finished_at','version','commit_sha','status','dry_run','migration_count','migration_applied','release_id','release_url','message')}
                    content={'ok':True,'read_only':True,'project_slug':slug,'job':safe,'sanitized':True,'secrets_exposed':False,'automatic_retry':False,'automatic_rollback_triggered':False}
                elif name=='deployment.production.homologation.plan':
                    if set(args)!={'slug','build_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']);bid=str(args['build_id']);control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,pl=homologation_call('/v1/production-homologation-plan',{'project_slug':slug,'build_id':bid,'trace_id':trace_id});
                    if code!=200 or not pl.get('ok'):raise ValueError(pl.get('error') or 'homologation_plan_failed')
                    digest=homologation_digest(client_id,slug,bid,pl['homologation_digest']);content={'ok':True,'side_effect_free':True,'homologation_digest':digest,'broker_digest':pl['homologation_digest'],'operation':pl['operation'],'approval_required':True,'homologation_only':True,'production_enabled':False}
                elif name=='approval.request-production-homologation':
                    if not {'slug','operation','reason'}<=set(args) or not set(args).issubset({'slug','operation','build_id','reason','ttl_seconds'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']);operation=str(args['operation']);reason=str(args['reason']);ttl=int(args.get('ttl_seconds') or 900);control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if operation=='deploy':
                     bid=str(args.get('build_id') or '')
                     if not bid:raise ValueError('build_id obrigatório para deploy')
                     code,pl=homologation_call('/v1/production-homologation-plan',{'project_slug':slug,'build_id':bid,'trace_id':trace_id});
                     if code!=200 or not pl.get('ok'):raise ValueError(pl.get('error') or 'homologation_plan_failed')
                     broker_digest=pl['homologation_digest'];kind='deployment.production.homologation.deploy'
                    else:
                     bid='rollback';broker_digest='rollback';kind='deployment.production.homologation.rollback'
                    digest=homologation_digest(client_id,slug,bid,broker_digest);created=approval_create_homologation(slug,client_id,reason,ttl,trace_id,digest,bid,kind);content={'ok':True,'approval_id':created['approval_id'],'status':'pending','operation':operation,'homologation_digest':digest,'broker_digest':broker_digest,'homologation_only':True,'production_enabled':False}
                elif name in {'deployment.production.homologation.deploy','deployment.production.homologation.rollback'}:
                    required={'slug','approval_id'}|({'build_id'} if name.endswith('.deploy') else set())
                    if set(args)!=required:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']);aid=str(args['approval_id']);bid=str(args.get('build_id') or 'rollback');control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if name.endswith('.deploy'):
                     code,pl=homologation_call('/v1/production-homologation-plan',{'project_slug':slug,'build_id':bid,'trace_id':trace_id});
                     if code!=200 or not pl.get('ok'):raise ValueError(pl.get('error') or 'homologation_plan_failed')
                     broker_digest=pl['homologation_digest'];digest=homologation_digest(client_id,slug,bid,broker_digest)
                    else:broker_digest='rollback';digest=homologation_digest(client_id,slug,bid,broker_digest)
                    row=approval_get(aid);meta=json.loads(row.get('metadata_json') or '{}') if row else {};reservation_id,execution_id=transaction_ids(name,aid,client_id,digest)
                    valid=bool(row and row.get('status') in {'approved','reserved'} and row.get('project_slug')==slug and row.get('requested_by')==client_id and row.get('approved_by') and row.get('action')==name and meta.get('homologation_digest')==digest and meta.get('homologation_only') is True)
                    if not valid:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                     rc,res=approval_transition(aid,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900});
                     if rc!=200:raise ValueError('approval_reserve_failed')
                    payload={'project_slug':slug,'trace_id':'txn-'+execution_id,'execution_id':execution_id}
                    path='/v1/production-homologation-rollback'
                    if name.endswith('.deploy'):payload.update({'build_id':bid,'homologation_digest':broker_digest});path='/v1/production-homologation-deploy'
                    code,data=homologation_call(path,payload,300);current=approval_get(aid)
                    if code==200 and data.get('ok'):
                     if current and current.get('status')!='consumed':approval_transition(aid,'finalize',{'reservation_id':reservation_id,'result':'success'})
                     data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};content=data
                    else:
                     if current and current.get('status')=='reserved':approval_transition(aid,'finalize' if data.get('effect_started') else 'release',{'reservation_id':reservation_id,'result':'completed'} if data.get('effect_started') else {'reservation_id':reservation_id})
                     raise ValueError(data.get('error') or 'homologation_effect_failed')
                elif name in {'deployment.production.activation.plan','approval.request-production-activation'}:
                    required={'slug'}|({'reason'} if name.startswith('approval.') else set());allowed=required|({'ttl_seconds'} if name.startswith('approval.') else set())
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip();slug=str(args['slug']);control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,pl=production_info_call('/v1/production-activation-plan',{'project_slug':slug,'trace_id':trace_id})
                    if code!=200 or not pl.get('ok'):raise ValueError(pl.get('error') or 'activation_plan_failed')
                    if name=='deployment.production.activation.plan':content=pl
                    else:
                     ttl=int(args.get('ttl_seconds') or 900);payload={'project_slug':slug,'action':'deployment.production.activate','requested_by':client_id,'requester_role':'agent','self_authorize':False,'ttl_seconds':ttl,'reason':str(args['reason']),'trace_id':trace_id,'metadata':{'activation_digest':pl['activation_digest'],'window_digest_sha256':pl['operation'].get('window_digest_sha256'),'snapshot_sha256':pl['operation'].get('snapshot_sha256'),'target_url':pl['operation'].get('target_url'),'canary_a_sha256':pl['operation'].get('canary_a_sha256'),'canary_b_sha256':pl['operation'].get('canary_b_sha256'),'effect_tool_available':False,'activation_allowed':False}}
                     req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json'})
                     with urllib.request.urlopen(req,timeout=10) as x:created=json.load(x)
                     content={'ok':True,'approval_id':created['approval_id'],'status':created['status'],'activation_digest':pl['activation_digest'],'two_approvers_required':created.get('two_approvers_required') is True,'effect_tool_available':False,'activation_allowed':False,'production_enabled':False,'secrets_exposed':False}
                elif name=='deployment.production.readiness':
                    if set(args)!={'slug'}:raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=production_info_call('/v1/production-readiness',{'project_slug':slug,'trace_id':trace_id})
                    if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'production_readiness_failed'))
                    content=data
                elif name=='deployment.production.plan':
                    if set(args)!={'slug','commit_sha','version'}:raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip().lower();version=str(args['version']).strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=production_info_call('/v1/production-plan',{'project_slug':slug,'commit_sha':commit,'version':version,'trace_id':trace_id})
                    if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'production_plan_failed'))
                    content=data
                elif name in {'supabase.migrations.inspect','supabase.migrations.plan'}:
                    if set(args)!={'slug','commit_sha','version'}:raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip().lower();version=str(args['version']).strip()
                    if len(commit)!=40 or not version.startswith('v'):raise ValueError('argumentos inválidos')
                    if name.endswith('.plan') and slug!='sistema-de-biblioteca-teste':raise ValueError('project_not_allowed')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=migration_call('/v1/migrations-plan' if name.endswith('.plan') else '/v1/migrations-inspect',slug,commit,version,trace_id)
                    if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'migration_inspection_failed'))
                    raw=json.dumps(data).lower()
                    if '"content_b64":' in raw or 'create table' in raw or 'alter table' in raw:raise ValueError('migration_content_exposure_blocked')
                    content=data
                elif name in {'deployment.plan','approval.request-deploy'}:
                    required={'slug','commit_sha','version'}
                    allowed=required|({'reason','ttl_seconds'} if name=='approval.request-deploy' else set())
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();commit=str(args.get('commit_sha') or '').strip();version=str(args.get('version') or '').strip()
                    if not slug or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit) or not (5<=len(version)<=120):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=deployment_digest(client_id,slug,commit,version)
                    if name=='deployment.plan':
                        plan=deployment_call('/v1/plan',slug,commit,version,trace_id,30)
                        if not plan.get('ok') or plan.get('side_effect_free') is not True or plan.get('operation',{}).get('dry_run') is not True:raise ValueError('deployment_plan_failed')
                        content={'ok':True,'side_effect_free':True,'deployment_digest':digest,'operation':plan['operation'],'target':'validation-only','approval_requirements':{'action':'deployment.validate','requested_by':client_id,'metadata':{'deployment_digest':digest,'commit_sha':commit,'version':version,'dry_run':True}}}
                    else:
                        reason=str(args.get('reason') or '').strip();ttl=int(args.get('ttl_seconds') or 900)
                        if not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('aprovação inválida')
                        created=approval_create_deploy(slug,client_id,reason,ttl,trace_id,digest,commit,version)
                        if created.get('status')!='pending':raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'deployment_digest':digest,'side_effects':{'release':False,'backup':False,'migrations':False,'komodo':False}}
                elif name=='deployment.validate':
                    if set(args)!={'slug','commit_sha','version','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();commit=str(args['commit_sha']).strip();version=str(args['version']).strip();approval_id=str(args['approval_id']).strip()
                    if not slug or len(commit)!=40 or len(approval_id)!=24 or not (5<=len(version)<=120):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=deployment_digest(client_id,slug,commit,version);row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    expected_meta={'deployment_digest':digest,'commit_sha':commit,'version':version,'dry_run':True}
                    reservation_id,execution_id=transaction_ids('deployment.validate',approval_id,client_id,digest)
                    valid_status=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    if not row or not valid_status or row.get('project_slug')!=slug or row.get('action')!='deployment.validate' or row.get('requested_by')!=client_id or not row.get('approved_by') or meta!=expected_meta:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':600})
                        if rc!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,data=deployment_effect_call('/v1/validate',slug,commit,version,'txn-'+execution_id,execution_id,300)
                    if code==409 and data.get('error')=='execution_in_progress':raise ValueError('execution_in_progress')
                    if code==409 and data.get('error')=='execution_id_conflict':raise ValueError('execution_id_conflict')
                    success=bool(code==200 and data.get('ok') and data.get('status')=='validated' and data.get('dry_run') is True and not data.get('release_created') and not data.get('backup_created') and not data.get('migrations_applied') and not data.get('komodo_called'))
                    current=approval_get(approval_id)
                    if success:
                        if current and current.get('status')!='consumed':
                            fc,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if fc!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'}
                        content=data
                    else:
                        effect_started=bool(data.get('effect_started'))
                        if current and current.get('status')=='reserved':
                            op='finalize' if effect_started else 'release';payload={'reservation_id':reservation_id,'result':'completed'} if effect_started else {'reservation_id':reservation_id}
                            approval_transition(approval_id,op,payload)
                        raise ValueError('deployment_validation_failed')
                elif name=='approval.get':
                    if set(args)!={'slug','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();approval_id=str(args.get('approval_id') or '').strip()
                    if not slug or len(approval_id)!=24 or not approval_id.startswith('apr_') or any(c not in '0123456789abcdef' for c in approval_id[4:]):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    row=approval_get(approval_id)
                    if not row or row.get('project_slug')!=slug or row.get('requested_by')!=client_id:raise ValueError('approval_not_found')
                    try:metadata=json.loads(row.get('metadata_json') or '{}')
                    except Exception:metadata={}
                    content={'ok':True,'read_only':True,'approval':{'approval_id':row.get('approval_id'),'project_slug':row.get('project_slug'),'action':row.get('action'),'requested_by':row.get('requested_by'),'reason':row.get('reason'),'status':row.get('status'),'created_at':row.get('created_at'),'expires_at':row.get('expires_at'),'approved_at':row.get('approved_at'),'approved_by':row.get('approved_by'),'consumed_at':row.get('consumed_at'),'trace_id':row.get('trace_id'),'proposal_digest':metadata.get('proposal_digest'),'merge_digest':metadata.get('merge_digest'),'proposal_number':metadata.get('proposal_number'),'expected_head_sha':metadata.get('expected_head_sha'),'deployment_digest':metadata.get('deployment_digest'),'commit_sha':metadata.get('commit_sha'),'version':metadata.get('version'),'dry_run':metadata.get('dry_run'),'promotion_digest':metadata.get('promotion_digest'),'expected_previous_commit':metadata.get('expected_previous_commit'),'target':metadata.get('target'),'real_deploy':metadata.get('real_deploy')}}
                elif name in {'forgejo.proposal.merge.plan','approval.request-merge'}:
                    required={'slug','number','expected_head_sha'}
                    allowed=required|({'reason','ttl_seconds'} if name=='approval.request-merge' else set())
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();number=int(args.get('number'));sha=str(args.get('expected_head_sha') or '').strip()
                    if not slug or not (1<=number<=2147483647) or len(sha)!=40 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=merge_digest(client_id,slug,number,sha)
                    if name=='forgejo.proposal.merge.plan':content={'ok':True,'side_effect_free':True,'merge_digest':digest,'operation':{'action':'forgejo.proposal.merge','project_slug':slug,'proposal_number':number,'expected_head_sha':sha},'approval_requirements':{'action':'forgejo.proposal.merge','requested_by':client_id,'metadata':{'merge_digest':digest,'proposal_number':number,'expected_head_sha':sha}}}
                    else:
                        reason=str(args.get('reason') or '').strip();ttl=int(args.get('ttl_seconds') or 900)
                        if not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('aprovação inválida')
                        created=approval_create_merge(slug,client_id,reason,ttl,trace_id,digest,number,sha)
                        if created.get('status')!='pending':raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'merge_digest':digest,'side_effects':{'forgejo':False,'main_modified':False}}
                elif name=='forgejo.proposal.merge':
                    if set(args)!={'slug','number','expected_head_sha','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();number=int(args['number']);sha=str(args['expected_head_sha']).strip();approval_id=str(args['approval_id']).strip()
                    if not slug or not (1<=number<=2147483647) or len(sha)!=40 or len(approval_id)!=24:raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));digest=merge_digest(client_id,slug,number,sha);row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    expected_meta={'merge_digest':digest,'proposal_number':number,'expected_head_sha':sha}
                    reservation_id,execution_id=transaction_ids('forgejo.proposal.merge',approval_id,client_id,digest)
                    valid_status=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    if not row or not valid_status or row.get('project_slug')!=slug or row.get('action')!='forgejo.proposal.merge' or row.get('requested_by')!=client_id or not row.get('approved_by') or meta!=expected_meta:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':600})
                        if rc!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,data=forgejo_proposal_merge_txn(slug,number,sha,approval_id,client_id,reservation_id)
                    success=bool(code==200 and data.get('ok') and data.get('merged') and data.get('main_modified'))
                    current=approval_get(approval_id)
                    if success:
                        if current and current.get('status')!='consumed':
                            fc,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if fc!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data['transaction']={'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'}
                        content=data
                    else:
                        if code==409 and current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        raise ValueError(str(data.get('error') or 'proposal_merge_failed'))
                elif name in {'forgejo.proposal.close','forgejo.proposal.delete-branch'}:
                    if set(args)!={'slug','number'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip()
                    try:number=int(args.get('number'))
                    except Exception:raise ValueError('argumentos inválidos')
                    if not slug or not (1<=number<=2147483647):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    action='close' if name=='forgejo.proposal.close' else 'delete-branch'
                    data=forgejo_proposal_action(action,slug,number,client_id,trace_id)
                    if not data.get('ok'):raise ValueError(str(data.get('error') or 'forgejo_proposal_action_failed'))
                    content=data
                elif name=='forgejo.proposal.list':
                    if 'slug' not in args or not set(args).issubset({'slug','state','limit'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();state=str(args.get('state') or 'open').strip()
                    try:limit=int(args.get('limit') or 20)
                    except Exception:raise ValueError('argumentos inválidos')
                    if not slug or state not in {'open','closed','all'} or not (1<=limit<=50):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=forgejo_proposal_list(slug,state,limit)
                    if not data.get('ok') or data.get('read_only') is not True:raise ValueError('forgejo_proposal_list_failed')
                    content=data
                elif name in {'forgejo.propose-edit.plan','approval.request-proposal'}:
                    required={'slug','path','expected_sha256','find','replace','title','body'}
                    allowed=required|({'reason','ttl_seconds'} if name=='approval.request-proposal' else set())
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();path=str(args['path']).strip();expected=str(args['expected_sha256']).strip();find_text=str(args['find']);replace_text=str(args['replace']);title=str(args['title']).strip();body=str(args['body'])
                    if not slug or path.startswith('/') or '..' in path or not path.startswith('site/') or not path.endswith('.html'):raise ValueError('argumentos inválidos')
                    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('sha256 inválido')
                    if not (1<=len(find_text)<=512) or len(replace_text)>1024 or not (4<=len(title)<=160) or len(body)>4000:raise ValueError('limite inválido')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    digest=proposal_digest(slug,path,expected,find_text,replace_text,title,body)
                    operation={'action':'forgejo.propose-edit','project_slug':slug,'base_branch':'main','path':path,'expected_sha256':expected,'find':find_text,'replace':replace_text,'title':title,'body':body}
                    if name=='forgejo.propose-edit.plan':
                        content={'ok':True,'side_effect_free':True,'client_id':client_id,'proposal_digest':digest,'operation':operation,'approval_requirements':{'action':'forgejo.propose-edit','project_slug':slug,'requested_by':client_id,'metadata':{'proposal_digest':digest}}}
                    else:
                        reason=str(args.get('reason') or '').strip();ttl=int(args.get('ttl_seconds') or 900)
                        if not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('aprovação inválida')
                        created=approval_create(slug,client_id,reason,ttl,trace_id,digest)
                        if not created.get('ok') or created.get('status')!='pending':raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':'pending','expires_at':created['expires_at'],'proposal_digest':digest,'project_slug':slug,'requested_by':client_id,'action':'forgejo.propose-edit','side_effects':{'forgejo':False,'branch_created':False,'pull_request_created':False}}
                elif name=='forgejo.propose-edit':
                    required={'slug','approval_id','path','expected_sha256','find','replace','title','body'}
                    if set(args)!=required:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();approval_id=str(args['approval_id']).strip();path=str(args['path']).strip();expected=str(args['expected_sha256']).strip();find_text=str(args['find']);replace_text=str(args['replace']);title=str(args['title']).strip();body=str(args['body'])
                    if not slug or not approval_id.startswith('apr_'):raise ValueError('argumentos inválidos')
                    if path.startswith('/') or '..' in path or not path.startswith('site/') or not path.endswith('.html'):raise ValueError('path inválido')
                    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('sha256 inválido')
                    if not (1<=len(find_text)<=512) or len(replace_text)>1024 or not (4<=len(title)<=160) or len(body)>4000:raise ValueError('limite inválido')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    preview=workspace_edit_preview(slug,'main',path,expected,find_text,replace_text,trace_id)
                    if not preview.get('ok') or not (preview.get('result') or {}).get('valid'):raise ValueError('preview_validation_failed')
                    digest=proposal_digest(slug,path,expected,find_text,replace_text,title,body)
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    now=int(time.time())
                    if approval.get('status')!='approved' or int(approval.get('expires_at') or 0)<=now:raise ValueError('approval_not_approved')
                    if approval.get('project_slug')!=slug or approval.get('action')!='forgejo.propose-edit' or approval.get('requested_by')!=client_id:raise ValueError('approval_binding_mismatch')
                    if not hmac.compare_digest(str(metadata.get('proposal_digest') or ''),digest):raise ValueError('approval_digest_mismatch')
                    consumed=approval_consume(approval_id)
                    if consumed.get('status')!='consumed':raise ValueError('approval_consume_failed')
                    content=forgejo_propose({'project_slug':slug,'base_branch':'main','path':path,'expected_sha256':expected,'find':find_text,'replace':replace_text,'title':title,'body':body,'trace_id':trace_id,'approval_id':approval_id,'requested_by':client_id})
                    if not content.get('ok'):raise ValueError('forgejo_proposal_failed')
                    content['approval']={'approval_id':approval_id,'status':'consumed','proposal_digest':digest}
                    content['preview_validated']=True
                else: raise ValueError('tool desconhecida')
                result={'content':[{'type':'text','text':json.dumps(content,ensure_ascii=False,separators=(',',':'))}],'isError':False}
            else:self.sendj(200,{'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}});return
            self.sendj(200,{'jsonrpc':'2.0','id':rid,'result':result})
        except urllib.error.HTTPError as e:self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32004,'message':'Recurso não encontrado' if e.code==404 else 'Falha no plano de controle'}})
        except Exception as e:self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32602,'message':str(e)[:160]}})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
