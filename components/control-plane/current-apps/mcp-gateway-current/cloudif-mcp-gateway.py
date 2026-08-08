#!/usr/bin/env python3
import os,json,hmac,urllib.request,urllib.error,threading,time,uuid,hashlib,secrets,base64,re
import jsonschema
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,urlencode
HOST=os.environ.get('CLOUDIF_MCP_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_MCP_PORT','18198'))
TOKEN=os.environ.get('CLOUDIF_MCP_TOKEN','');CONTROL=os.environ.get('CLOUDIF_CONTROL_URL','http://127.0.0.1:18197').rstrip('/');CONTROL_TOKEN=os.environ.get('CLOUDIF_CONTROL_TOKEN','')
AUDIT_URL=os.environ.get('CLOUDIF_AUDIT_URL','http://127.0.0.1:18201').rstrip('/')
AUDIT_TOKEN=os.environ.get('CLOUDIF_AUDIT_TOKEN','')
AGENT_URL=os.environ.get('CLOUDIF_AGENT_URL','http://127.0.0.1:18203').rstrip('/')
AGENT_ADMIN_TOKEN=os.environ.get('CLOUDIF_AGENT_ADMIN_TOKEN','')
WORKSPACE_URL=os.environ.get('CLOUDIF_WORKSPACE_URL','http://127.0.0.1:18206').rstrip('/')
WORKSPACE_TOKEN=os.environ.get('CLOUDIF_WORKSPACE_TOKEN','')
SESSION_FILE_RESOLVER_URL=os.environ.get('CLOUDIF_SESSION_FILE_RESOLVER_URL','').strip()
SESSION_FILE_RESOLVER_TOKEN=os.environ.get('CLOUDIF_SESSION_FILE_RESOLVER_TOKEN','').strip()
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
MULTISERVICE_PREVIEW_URL=os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_URL','http://127.0.0.1:18228').rstrip('/')
MULTISERVICE_PREVIEW_TOKEN=os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_TOKEN','')
SUPABASE_MCP_URL=os.environ.get('CLOUDIF_SUPABASE_MCP_BROKER_URL','http://127.0.0.1:18218').rstrip('/')
SUPABASE_MCP_TOKEN=os.environ.get('CLOUDIF_SUPABASE_MCP_BROKER_TOKEN','')
PROJECT_CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
PROJECT_CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
RUNTIME_RECONCILER_URL=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_URL','http://127.0.0.1:18232').rstrip('/')
RUNTIME_RECONCILER_TOKEN=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_TOKEN','')
PROJECT_OBSERVABILITY_URL=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_URL','http://127.0.0.1:18233').rstrip('/')
PROJECT_OBSERVABILITY_TOKEN=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_TOKEN','')
PUBLIC_ORIGIN=os.environ.get('CLOUDIF_MCP_PUBLIC_ORIGIN','https://cloudiff.duckdns.org').rstrip('/')
MCP_RESOURCE=PUBLIC_ORIGIN+'/cloudiff/mcp'
OAUTH_ISSUER=PUBLIC_ORIGIN
OAUTH_CODES={};OAUTH_ACCESS={};OAUTH_REFRESH={};OAUTH_LOCK=threading.Lock()
OAUTH_ACCESS_TTL=3600;OAUTH_REFRESH_TTL=2592000

def _agent_clients():
    req=urllib.request.Request(AGENT_URL+'/v1/clients',headers={'Authorization':'Bearer '+AGENT_ADMIN_TOKEN,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as x:return json.load(x).get('clients') or []
def _oauth_client(client_id):return next((x for x in _agent_clients() if x.get('client_id')==client_id and x.get('status')=='active'),None)
def _client_projects(row):
    if not row:return []
    raw=row.get('project_slugs_json') if isinstance(row,dict) else None
    try:projects=json.loads(raw or '[]') if isinstance(raw,str) else list(row.get('project_slugs') or [])
    except Exception:projects=[]
    return [str(x).strip() for x in projects if str(x).strip()]
def _header_groups(value):
    return {x.strip().casefold() for x in re.split(r'[|,;]',str(value or '')) if x.strip()}
PROJECT_ROLE_RANK={'none':0,'viewer':10,'member':50,'developer':60,'editor':65,'maintainer':80,'admin':90,'administrator':90,'owner':100}
def _public_oauth_client(client_id,username,groups_header):
    row=_oauth_client(client_id);projects=_client_projects(row)
    if not row or len(projects)!=1 or not username:return None
    slug=projects[0]
    try:data=control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
    except Exception:return None
    project=data.get('project') or {};acl=data.get('acl') or []
    user=str(username).strip().casefold();groups=_header_groups(groups_header);role='none'
    if user==str(project.get('owner') or row.get('owner_user') or '').strip().casefold():role='owner'
    for item in acl:
        kind=str(item.get('subject_type') or '').strip().casefold();subject=str(item.get('subject') or '').strip().casefold();candidate=str(item.get('role') or 'viewer').strip().casefold()
        matched=(kind=='user' and subject==user) or (kind=='group' and subject in groups)
        if matched and PROJECT_ROLE_RANK.get(candidate,0)>PROJECT_ROLE_RANK.get(role,0):role=candidate
    if PROJECT_ROLE_RANK.get(role,0)<=0:return None
    return {'client_id':client_id,'project_slug':slug,'authorized_user':str(username).strip(),'authorized_groups':sorted(groups),'project_role':role,'public_client':True,'owner_user':str(row.get('owner_user') or '')}
def _callback_mode(uri):
    try:u=urlparse(uri)
    except Exception:return ''
    if u.scheme=='https' and u.netloc=='claude.ai' and u.path=='/api/mcp/auth_callback':return 'pkce'
    if u.scheme=='https' and u.netloc=='chatgpt.com' and u.path.startswith('/connector/oauth/') and len(u.path)>len('/connector/oauth/'):return 'pkce'
    if u.scheme=='http' and u.hostname in {'127.0.0.1','localhost','::1'} and u.port:return 'pkce'
    if u.scheme=='https' and u.netloc in {'chat.openai.com','chatgpt.com'} and re.fullmatch(r'/aip/g-[A-Za-z0-9_-]{16,160}/oauth/callback',u.path):return 'chatgpt_actions'
    return ''
def _callback_allowed(uri):return bool(_callback_mode(uri))
def _validate_client_secret(client_id,secret):
    row=_oauth_client(client_id)
    if not row or not secret:return None
    slugs=json.loads(row.get('project_slugs_json') or '[]') if isinstance(row.get('project_slugs_json'),str) else (row.get('project_slugs') or [])
    slug=str((slugs or [''])[0])
    payload=json.dumps({'client_id':client_id,'token':secret,'scope':'project:read','project_slug':slug},separators=(',',':')).encode()
    req=urllib.request.Request(AGENT_URL+'/v1/validate',data=payload,method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+AGENT_ADMIN_TOKEN})
    try:
        with urllib.request.urlopen(req,timeout=5) as x:data=json.load(x)
    except Exception:return None
    return {'client_id':client_id,'secret':secret,'project_slug':slug} if data.get('ok') else None
def _pkce_ok(verifier,challenge):
    if not challenge:return True
    digest=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return hmac.compare_digest(digest,challenge)
def _oauth_token(client):
    now=int(time.time());access=secrets.token_urlsafe(36);refresh=secrets.token_urlsafe(36)
    with OAUTH_LOCK:
        OAUTH_ACCESS[access]={**client,'expires_at':now+OAUTH_ACCESS_TTL}
        OAUTH_REFRESH[refresh]={**client,'expires_at':now+OAUTH_REFRESH_TTL}
    return {'access_token':access,'token_type':'Bearer','expires_in':OAUTH_ACCESS_TTL,'refresh_token':refresh,'scope':'mcp offline_access'}
def _oauth_cleanup():
    now=time.time()
    with OAUTH_LOCK:
        for store in (OAUTH_CODES,OAUTH_ACCESS,OAUTH_REFRESH):
            for key in [k for k,v in store.items() if float(v.get('expires_at') or 0)<=now]:store.pop(key,None)

def _oauth_metadata(resource=False):
    if resource:return {'resource':MCP_RESOURCE,'authorization_servers':[OAUTH_ISSUER],'bearer_methods_supported':['header'],'scopes_supported':['mcp','offline_access']}
    return {'issuer':OAUTH_ISSUER,'authorization_endpoint':OAUTH_ISSUER+'/cloudiff/mcp/oauth/authorize','token_endpoint':OAUTH_ISSUER+'/cloudiff/mcp/oauth/token','revocation_endpoint':OAUTH_ISSUER+'/cloudiff/mcp/oauth/revoke','response_types_supported':['code'],'grant_types_supported':['authorization_code','refresh_token'],'code_challenge_methods_supported':['S256'],'token_endpoint_auth_methods_supported':['none','client_secret_post','client_secret_basic'],'scopes_supported':['mcp','offline_access'],'resource':MCP_RESOURCE}

class ToolInputError(ValueError):
    def __init__(self, payload):
        self.payload = payload
        super().__init__(str(payload.get('message') or payload.get('code') or 'invalid_arguments'))


class ToolStateError(RuntimeError):
    def __init__(self, payload):
        self.payload = dict(payload or {})
        super().__init__(str(self.payload.get('message') or self.payload.get('code') or 'tool_state_error'))


def _unwrap_tool_arguments(raw):
    if not isinstance(raw, dict):
        return {}, []
    current = raw
    wrappers = []
    wrapper_names = ('arguments', 'input', 'payload', 'request', 'data')
    for _ in range(3):
        selected = next((name for name in wrapper_names if isinstance(current.get(name), dict)), None)
        if not selected:
            break
        business = set(current) - {selected, 'tool', 'name', 'metadata'}
        if business:
            break
        wrappers.append(selected)
        current = current[selected]
    return dict(current), wrappers


def _tool_input_error(code, field, message, received, example, documentation, **extra):
    payload = {
        'code': code,
        'field': field,
        'path': '$.' + field if field else '$',
        'message': message,
        'receivedFields': sorted(str(key) for key in received),
        'example': example,
        'documentation': documentation,
    }
    payload.update(extra)
    raise ToolInputError(payload)


def canonical_tool_arguments(raw, required, allowed, example, documentation, aliases=None):
    args, wrappers = _unwrap_tool_arguments(raw)
    aliases = aliases or {}
    used_aliases = {}
    for alias, canonical_name in aliases.items():
        if canonical_name not in args and alias in args:
            args[canonical_name] = args.pop(alias)
            used_aliases[alias] = canonical_name
    missing = sorted(set(required) - set(args))
    if missing:
        field = missing[0]
        _tool_input_error(
            'missing_field', field, f'O campo {field} é obrigatório.', args, example, documentation,
            missingFields=missing, wrappersRemoved=wrappers, aliasesApplied=used_aliases,
        )
    unknown = sorted(set(args) - set(allowed))
    if unknown:
        field = unknown[0]
        _tool_input_error(
            'unknown_field', field, f'O campo {field} não é aceito por esta ferramenta.', args, example, documentation,
            unknownFields=unknown, allowedFields=sorted(allowed), wrappersRemoved=wrappers, aliasesApplied=used_aliases,
        )
    return args, {'wrappersRemoved': wrappers, 'aliasesApplied': used_aliases}


def require_tool_pattern(args, field, pattern, example, documentation, message):
    value = str(args.get(field) or '').strip()
    if not re.fullmatch(pattern, value):
        _tool_input_error('invalid_field_format', field, message, args, example, documentation, expectedPattern=pattern)
    return value


def audit_async(event):
    if not AUDIT_TOKEN:return
    def run():
        try:
            req=urllib.request.Request(AUDIT_URL+'/v1/events',data=json.dumps(event,separators=(',',':')).encode(),method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+AUDIT_TOKEN})
            urllib.request.urlopen(req,timeout=2).read()
        except Exception:pass
    threading.Thread(target=run,daemon=True).start()
ENVIRONMENT_NAME_SCHEMA={'type':'string','enum':['development','preview','homologation','production']}
ENVIRONMENT_SERVICE_SCHEMA={'type':'string','pattern':'^[a-z][a-z0-9-]{0,31}$'}
ENVIRONMENT_VARIABLE_SCHEMA={'type':'string','pattern':'^[A-Z_][A-Z0-9_]{0,127}$'}
ENVIRONMENT_CHANGE_SCHEMA={
 'type':'array','minItems':1,'maxItems':256,
 'items':{
  'type':'object','additionalProperties':False,
  'properties':{
   'operation':{'type':'string','enum':['upsert','delete']},
   'name':ENVIRONMENT_VARIABLE_SCHEMA,
   'service':ENVIRONMENT_SERVICE_SCHEMA,
   'value':{},
   'secret_reference':{'type':'string','pattern':'^[a-z][a-z0-9_.:/-]{2,255}$'},
   'definition':{
    'type':'object','additionalProperties':False,
    'properties':{
     'required':{'type':'boolean'},'secret':{'type':'boolean'},'description':{'type':'string','maxLength':1000},
     'scope':{'type':'string','enum':['project','environment','service']},'exposeToClient':{'type':'boolean'},
     'immutable':{'type':'boolean'},'restartRequired':{'type':'boolean'},'buildTime':{'type':'boolean'},'runtime':{'type':'boolean'},
     'allowedValues':{'type':'array','maxItems':256},'pattern':{'type':'string','maxLength':512},
     'validation':{'type':'object','additionalProperties':True}
    }
   }
  },
  'required':['name']
 }
}

SECRET_REFERENCE_SCHEMA={'type':'string','pattern':'^cloudiff-secret://[a-z0-9][A-Za-z0-9_.:/-]{2,255}$'}
SECRET_STAGE_SCHEMA={'type':'string','pattern':'^stage_[a-f0-9]{24}$'}
SECRET_DEFINITION_SCHEMA={'type':'object','additionalProperties':False,'properties':{
 'required':{'type':'boolean'},'secret':{'type':'boolean','const':True},'description':{'type':'string','maxLength':1000},
 'scope':{'type':'string','enum':['project','environment','service']},'exposeToClient':{'type':'boolean','const':False},
 'immutable':{'type':'boolean'},'restartRequired':{'type':'boolean'},'buildTime':{'type':'boolean'},'runtime':{'type':'boolean'},
 'allowedValues':{'type':'array','maxItems':256},'pattern':{'type':'string','maxLength':512},'validation':{'type':'object','additionalProperties':True}
}}

TOOLS=[
 {'name':'project.list','description':'Lista projetos registrados na CloudIFF','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'project.get','description':'Obtém projeto pelo slug','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.connectors','description':'Lista conectores e ACL do projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.technologies.detect','description':'Detecta recursivamente todos os componentes e serviços do repositório autorizado sem alterar arquivos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.manifest.validate','description':'Valida cloudiff.yaml, normaliza serviços e retorna erros acionáveis sem efeitos persistentes','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'manifest':{'oneOf':[{'type':'string','minLength':1,'maxLength':1048576},{'type':'object','properties':{},'additionalProperties':True}]},'overrides':{'type':'object','properties':{},'additionalProperties':True}},'required':['slug','manifest'],'additionalProperties':False}},
 {'name':'project.configuration.get','description':'Consulta a revisão e a configuração efetiva do projeto sem expor valores secretos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.configuration.status','description':'Consulta o estado reconciliado por ambiente sem executar correções','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA},'required':['slug'],'additionalProperties':False}},
 {'name':'project.configuration.drift','description':'Lista somente ambientes com drift, rebuild/restart pendente, variável ausente, imagem desatualizada, unhealthy ou bloqueio','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA},'required':['slug'],'additionalProperties':False}},
 {'name':'project.configuration.reconcile.plan','description':'Recalcula o drift e gera um plano sem efeitos que aponta os fluxos aprovados necessários para correção','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','environment'],'additionalProperties':False}},
 {'name':'project.observability.get','description':'Consulta métricas consolidadas de runtime, ambiente, segredos, build e toolchain sem valores ou referências secretas','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.observability.alerts','description':'Lista alertas atuais de drift, variáveis ausentes, segredos expirados, runtime unhealthy e falhas de build/toolchain','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.environment.list','description':'Lista metadados e configuração de variáveis por ambiente e serviço sem revelar segredos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA,'include_public_values':{'type':'boolean'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.environment.get','description':'Consulta uma variável específica; valores secretos nunca são retornados','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA,'name':ENVIRONMENT_VARIABLE_SCHEMA,'include_public_value':{'type':'boolean'}},'required':['slug','environment','name'],'additionalProperties':False}},
 {'name':'project.environment.validate','description':'Valida alterações de ambiente e calcula serviços afetados sem persistir valores','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'changes':ENVIRONMENT_CHANGE_SCHEMA},'required':['slug','environment','changes'],'additionalProperties':False}},
 {'name':'project.environment.change.plan','description':'Cria plano versionado de alteração de variáveis sem reiniciar ou reconstruir serviços','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'changes':ENVIRONMENT_CHANGE_SCHEMA,'expected_revision':{'type':'integer','minimum':0},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','environment','changes','expected_revision'],'additionalProperties':False}},
 {'name':'approval.request-environment-change','description':'Solicita aprovação humana vinculada ao digest e revisão exatos da alteração de ambiente','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.change.execute','description':'Aplica alteração de ambiente aprovada usando reserve-effect-finalize; containers não são alterados nesta fase','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'project.environment.promote.plan','description':'Planeja cópia explícita de variáveis entre ambientes sem modificar a origem','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'source_environment':ENVIRONMENT_NAME_SCHEMA,'target_environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA,'expected_revision':{'type':'integer','minimum':0},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','source_environment','target_environment','expected_revision'],'additionalProperties':False}},
 {'name':'approval.request-environment-promotion','description':'Solicita aprovação humana vinculada à promoção de ambiente planejada','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.promote.execute','description':'Executa promoção aprovada usando reserve-effect-finalize sem reiniciar containers','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'project.environment.history','description':'Consulta histórico sanitizado de alterações de ambiente','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'limit':{'type':'integer','minimum':1,'maximum':500}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.environment.import.plan','description':'Analisa conteúdo .env enviado explicitamente e cria plano somente para variáveis públicas; valores classificados como segredo são descartados e encaminhados ao ciclo seguro de segredos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA,'content':{'type':'string','minLength':1,'maxLength':262144},'secret_names':{'type':'array','items':ENVIRONMENT_VARIABLE_SCHEMA,'maxItems':256,'uniqueItems':True},'expected_revision':{'type':'integer','minimum':0},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','environment','content','expected_revision'],'additionalProperties':False}},
 {'name':'project.environment.export','description':'Exporta somente nomes e metadados das variáveis e um .env.example sem valores ou referências secretas','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA},'required':['slug','environment'],'additionalProperties':False}},
 {'name':'project.environment.secret.list','description':'Lista somente metadados, versões, referências opacas e estado dos segredos; nunca retorna valores ou ciphertext','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA},'required':['slug'],'additionalProperties':False}},
 {'name':'project.environment.secret.history','description':'Consulta a trilha de auditoria sanitizada do ciclo de vida de segredos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'limit':{'type':'integer','minimum':1,'maximum':500}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.environment.secret.stage','description':'Criptografa e armazena temporariamente um novo valor secreto sem ativá-lo no projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'service':ENVIRONMENT_SERVICE_SCHEMA,'name':ENVIRONMENT_VARIABLE_SCHEMA,'secret_value':{'type':'string','minLength':1,'maxLength':65536},'ttl_seconds':{'type':'integer','minimum':60,'maximum':3600}},'required':['slug','environment','name','secret_value'],'additionalProperties':False}},
 {'name':'project.environment.secret.rotate.plan','description':'Planeja uma rotação usando um segredo staged; não ativa nem revela o valor','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'stage_id':SECRET_STAGE_SCHEMA,'expected_revision':{'type':'integer','minimum':0},'reason':{'type':'string','minLength':4,'maxLength':500},'definition':SECRET_DEFINITION_SCHEMA,'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400},'active_ttl_seconds':{'type':'integer','minimum':0,'maximum':31536000}},'required':['slug','stage_id','expected_revision','reason'],'additionalProperties':False}},
 {'name':'approval.request-secret-rotation','description':'Solicita aprovação humana vinculada ao digest exato da rotação de segredo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.secret.rotate.execute','description':'Ativa a rotação aprovada usando reserve-effect-finalize','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'stage_id':SECRET_STAGE_SCHEMA,'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','stage_id','approval_id'],'additionalProperties':False}},
 {'name':'project.environment.secret.revoke.plan','description':'Planeja a revogação de uma referência secreta ativa sem executar efeito','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'secret_reference':SECRET_REFERENCE_SCHEMA,'expected_revision':{'type':'integer','minimum':0},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','secret_reference','expected_revision','reason'],'additionalProperties':False}},
 {'name':'approval.request-secret-revocation','description':'Solicita aprovação humana vinculada à revogação exata do segredo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.secret.revoke.execute','description':'Executa revogação aprovada usando reserve-effect-finalize','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'secret_reference':SECRET_REFERENCE_SCHEMA,'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','secret_reference','approval_id'],'additionalProperties':False}},
 {'name':'project.environment.secret.promote.plan','description':'Planeja promoção criptografada de um segredo ativo para outro ambiente sem revelar o valor','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'source_secret_reference':SECRET_REFERENCE_SCHEMA,'target_environment':ENVIRONMENT_NAME_SCHEMA,'expected_revision':{'type':'integer','minimum':0},'reason':{'type':'string','minLength':4,'maxLength':500},'definition':SECRET_DEFINITION_SCHEMA,'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400},'active_ttl_seconds':{'type':'integer','minimum':0,'maximum':31536000}},'required':['slug','source_secret_reference','target_environment','expected_revision','reason'],'additionalProperties':False}},
 {'name':'approval.request-secret-promotion','description':'Solicita aprovação humana vinculada à promoção exata do segredo entre ambientes','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.secret.promote.execute','description':'Executa promoção aprovada e recriptografa o segredo no ambiente de destino','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'source_secret_reference':SECRET_REFERENCE_SCHEMA,'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','source_secret_reference','approval_id'],'additionalProperties':False}},

 {'name':'project.environment.secret.read.plan','description':'Planeja uma leitura excepcional e única do valor real de um segredo ativo; o plano não revela o valor','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'secret_reference':SECRET_REFERENCE_SCHEMA,'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':900}},'required':['slug','secret_reference','reason'],'additionalProperties':False}},
 {'name':'approval.request-secret-read','description':'Solicita aprovação humana crítica vinculada à leitura única de um segredo real','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':900}},'required':['slug','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.environment.secret.read.execute','description':'Executa uma leitura excepcional aprovada e retorna o valor uma única vez com no-store; a leitura é auditada e o plano é consumido','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'secret_reference':SECRET_REFERENCE_SCHEMA,'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','plan_digest','secret_reference','approval_id'],'additionalProperties':False}},
 {'name':'runtime.catalog','description':'Lista política homologada de runtimes e frameworks sem efeitos','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'runtime.detect','description':'Detecta framework a partir de evidências sanitizadas do workspace autorizado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'runtime.plan','description':'Gera plano declarativo usando somente templates homologados','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'runtime.validate','description':'Valida plano declarativo contra a política server-side','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'project.toolchain.get','description':'Consulta configuração, imagens reutilizáveis e ativações da toolchain sem executar build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.toolchain.validate','description':'Valida catálogo, archive e script de provisionamento em modo side-effect-free','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':0}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.toolchain.plan','description':'Planeja imagens imutáveis por serviço, digests, catálogo, scanner e reutilização sem construir imagens','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':0}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.toolchain.build.plan','description':'Alias explícito do plano de construção da toolchain; não cria imagem','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':0}},'required':['slug'],'additionalProperties':False}},
 {'name':'approval.request-toolchain-build','description':'Solicita aprovação humana vinculada ao plano, revisão, archive e digests da toolchain','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':1},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','expected_revision','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.toolchain.build.execute','description':'Enfileira build aprovado da toolchain usando reserve-effect-finalize; não ativa imagens','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':1},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','expected_revision','plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'project.toolchain.build.status','description':'Consulta estado e resultado sanitizado de um build de toolchain','inputSchema':{'type':'object','properties':{'job_id':{'type':'string','pattern':'^toolchain_[a-f0-9]{24}$'}},'required':['job_id'],'additionalProperties':False}},
 {'name':'project.toolchain.logs.read','description':'Lê log sanitizado do broker da toolchain sem retornar segredos','inputSchema':{'type':'object','properties':{'job_id':{'type':'string','pattern':'^toolchain_[a-f0-9]{24}$'}},'required':['job_id'],'additionalProperties':False}},
 {'name':'project.toolchain.image.list','description':'Lista imagens imutáveis, SBOM, scanner, assinatura e ambientes ativos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'service':{'type':'string','pattern':'^[a-z][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'project.toolchain.image.get','description':'Consulta metadados sanitizados de uma imagem de toolchain','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'image_record_id':{'type':'string','pattern':'^img_[a-f0-9]{24}$'}},'required':['slug','image_record_id'],'additionalProperties':False}},
 {'name':'project.toolchain.image.activate.plan','description':'Planeja ativação ou rollback de um conjunto de imagens por ambiente sem alterar containers','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'job_id':{'type':'string','pattern':'^toolchain_[a-f0-9]{24}$'},'expected_revision':{'type':'integer','minimum':0}},'required':['slug','environment','job_id','expected_revision'],'additionalProperties':False}},
 {'name':'approval.request-toolchain-activation','description':'Solicita aprovação humana vinculada ao conjunto exato de imagens e ambiente','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'job_id':{'type':'string','pattern':'^toolchain_[a-f0-9]{24}$'},'expected_revision':{'type':'integer','minimum':0},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','environment','job_id','expected_revision','plan_digest','reason'],'additionalProperties':False}},
 {'name':'project.toolchain.image.activate','description':'Ativa ou restaura imagens aprovadas; registra ponteiro e deixa rebuild pendente sem alterar containers','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'environment':ENVIRONMENT_NAME_SCHEMA,'job_id':{'type':'string','pattern':'^toolchain_[a-f0-9]{24}$'},'expected_revision':{'type':'integer','minimum':0},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','environment','job_id','expected_revision','plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'build.multiservice.plan','description':'Gera o plano único de build multissserviço vinculado à configuração, toolchain, archive, SBOM, scanner e assinatura','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'environment':ENVIRONMENT_NAME_SCHEMA,'expected_revision':{'type':'integer','minimum':1}},'required':['slug'],'additionalProperties':False}},
 {'name':'build.multiservice.status','description':'Consulta o estado e os artefatos de um build multissserviço sem revelar o payload interno','inputSchema':{'type':'object','properties':{'job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'}},'required':['job_id'],'additionalProperties':False}},
 {'name':'approval.request-multiservice-build','description':'Cria aprovação humana vinculada ao plano, revisão, archive e digests exatos do build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'expected_revision':{'type':'integer','minimum':1},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','expected_revision','plan_digest','reason'],'additionalProperties':False}},
 {'name':'build.multiservice.execute','description':'Enfileira o build multissserviço aprovado usando reserve-effect-finalize e retorna o job_id','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'environment':ENVIRONMENT_NAME_SCHEMA,'expected_revision':{'type':'integer','minimum':1},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','expected_revision','plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'build.plan','description':'Gera plano de build imutável, side-effect-free e derivado da política homologada','inputSchema':{'type':'object','properties':{'framework':{'type':'string','enum':['static','react','vite','nextjs','vue','nuxt','angular','svelte','sveltekit','astro','express','nestjs','node']},'runtime_version':{'type':'string','enum':['20','22','24']},'package_manager':{'type':'string','enum':['npm','pnpm','yarn']}},'required':['framework'],'additionalProperties':False}},
 {'name':'build.request','description':'Reserva build estático idempotente na fila durável; Node permanece fail-closed','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'framework':{'type':'string','enum':['static']},'build_plan_digest':{'type':'string','pattern':'^[0-9a-f]{64}$'}},'required':['slug','ref','framework','build_plan_digest'],'additionalProperties':False}},
 {'name':'build.status','description':'Consulta status sanitizado de build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'build.logs.read','description':'Lê logs sanitizados de build','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'build.artifact.get','description':'Obtém metadados imutáveis do artefato sem segredo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_id':{'type':'string','pattern':'^[0-9a-f-]+$'}},'required':['slug','build_id'],'additionalProperties':False}},
 {'name':'preview.multiservice.plan','description':'Planeja preview autenticado multissserviço a partir de build imutável concluído','inputSchema':{'type':'object','properties':{'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string','pattern':'^/'},'service':{'type':'string','pattern':'^[a-z][a-z0-9-]*$'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}},'ttl_seconds':{'type':'integer','minimum':300,'maximum':7200}},'required':['build_job_id'],'additionalProperties':False}},
 {'name':'approval.request-multiservice-preview','description':'Cria aprovação humana vinculada ao digest, build, configuração, archive, rotas e TTL do preview','inputSchema':{'type':'object','properties':{'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string'},'service':{'type':'string'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}},'ttl_seconds':{'type':'integer','minimum':300,'maximum':7200},'preview_plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'approval_ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['build_job_id','preview_plan_digest','reason'],'additionalProperties':False}},
 {'name':'preview.multiservice.create','description':'Cria preview multissserviço aprovado com rede interna, containers isolados e proxy autenticado','inputSchema':{'type':'object','properties':{'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string'},'service':{'type':'string'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}},'ttl_seconds':{'type':'integer','minimum':300,'maximum':7200},'preview_plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['build_job_id','preview_plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'preview.multiservice.status','description':'Consulta estado, URL autenticada, serviços e expiração do preview multissserviço','inputSchema':{'type':'object','properties':{'preview_id':{'type':'string','pattern':'^pv_[a-f0-9]{24}$'}},'required':['preview_id'],'additionalProperties':False}},
 {'name':'preview.multiservice.delete','description':'Remove antecipadamente um preview multissserviço autorizado','inputSchema':{'type':'object','properties':{'preview_id':{'type':'string','pattern':'^pv_[a-f0-9]{24}$'}},'required':['preview_id'],'additionalProperties':False}},
 {'name':'deployment.multiservice.plan','description':'Gera resumo único e plano de deploy multissserviço vinculado ao build, revisão, variáveis, rotas e reconciliação, sem criar containers','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'environment':{'type':'string','enum':['homologation','production']},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string','pattern':'^/'},'service':{'type':'string','pattern':'^[a-z][a-z0-9-]*$'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}}},'required':['slug','build_job_id','environment'],'additionalProperties':False}},
 {'name':'approval.request-multiservice-deployment','description':'Cria aprovação humana vinculada ao plano, build, revisão, ACL, variáveis por digest, rotas e ambiente do deploy','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'environment':{'type':'string','enum':['homologation','production']},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string','pattern':'^/'},'service':{'type':'string','pattern':'^[a-z][a-z0-9-]*$'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}},'deployment_plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','build_job_id','environment','deployment_plan_digest','reason'],'additionalProperties':False}},
 {'name':'deployment.multiservice.execute','description':'Executa deploy multissserviço aprovado usando reserve-effect-finalize; valores protegidos são resolvidos somente durante o efeito','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'build_job_id':{'type':'string','pattern':'^build_[a-f0-9]{24}$'},'environment':{'type':'string','enum':['homologation','production']},'routes':{'type':'array','items':{'type':'object','properties':{'pathPrefix':{'type':'string','pattern':'^/'},'service':{'type':'string','pattern':'^[a-z][a-z0-9-]*$'},'stripPrefix':{'type':'boolean'}},'required':['pathPrefix','service'],'additionalProperties':False}},'deployment_plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','build_job_id','environment','deployment_plan_digest','approval_id'],'additionalProperties':False}},
 {'name':'deployment.multiservice.status','description':'Consulta estado sanitizado do deploy sem retornar valores de variáveis ou portas internas do host','inputSchema':{'type':'object','properties':{'deployment_id':{'type':'string','pattern':'^dep_[a-f0-9]{24}$'}},'required':['deployment_id'],'additionalProperties':False}},
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
 {'name':'workspace.normalize.plan','description':'Analisa o snapshot e propõe cloudiff.yaml como change set revisável, sem alterar o repositório','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'title':{'type':'string','minLength':4,'maxLength':160},'description':{'type':'string','maxLength':4000},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400}},'required':['slug'],'additionalProperties':False}},
 {'name':'workspace.artifact.upload.start','description':'Inicia upload temporário de artefato binário vinculado ao projeto, tamanho e SHA-256 esperados','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'filename':{'type':'string','minLength':1,'maxLength':240},'expected_size':{'type':'integer','minimum':0,'maximum':67108864},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400}},'required':['slug','filename','expected_size','expected_sha256'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','filename':'documentos-anonimizados.zip','expected_size':1390970,'expected_sha256':'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','ttl_seconds':3600}]}},
 {'name':'workspace.artifact.upload.chunk','description':'Envia um chunk Base64 pequeno e sequencial para um artifact_id; retries idênticos são idempotentes','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'},'chunk_index':{'type':'integer','minimum':0,'maximum':65535},'content_base64':{'type':'string','minLength':1,'maxLength':262144},'chunk_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},'required':['slug','artifact_id','chunk_index','content_base64','chunk_sha256'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','artifact_id':'art_111111111111111111111111','chunk_index':0,'content_base64':'eA==','chunk_sha256':'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'}]}},
 {'name':'workspace.artifact.upload.batch','description':'Envia até 16 chunks pequenos de até 8 KiB raw cada em uma chamada; ideal quando strings Base64 maiores são truncadas pelo cliente','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'},'chunks':{'type':'array','minItems':1,'maxItems':16,'items':{'type':'object','properties':{'chunk_index':{'type':'integer','minimum':0,'maximum':65535},'content_base64':{'type':'string','minLength':1,'maxLength':11000},'chunk_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},'required':['chunk_index','content_base64','chunk_sha256'],'additionalProperties':False}}},'required':['slug','artifact_id','chunks'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','artifact_id':'art_111111111111111111111111','chunks':[{'chunk_index':0,'content_base64':'eA==','chunk_sha256':'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'}]}]}},
 {'name':'workspace.artifact.import','description':'Importa um arquivo já disponível no provedor da sessão por file_id, valida tamanho e SHA-256 e retorna artifact_id selado; exige resolver server-side configurado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'file_id':{'type':'string','minLength':6,'maxLength':192,'pattern':'^[A-Za-z0-9_-]+$'},'filename':{'type':'string','minLength':1,'maxLength':240},'expected_size':{'type':'integer','minimum':0,'maximum':67108864},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400}},'required':['slug','file_id','filename','expected_size','expected_sha256'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','file_id':'file_1111111111111111','filename':'documentos-anonimizados.zip','expected_size':1390970,'expected_sha256':'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','ttl_seconds':3600}]}},
 {'name':'workspace.artifact.upload.ticket','description':'Gera um link HTTPS temporário do Portal para enviar o arquivo binário diretamente pelo navegador, sem Base64; vinculado ao artifact_id, tamanho e SHA-256 já registrados','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'},'ttl_seconds':{'type':'integer','minimum':60,'maximum':1800}},'required':['slug','artifact_id'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','artifact_id':'art_111111111111111111111111','ttl_seconds':900}]}},
 {'name':'workspace.artifact.upload.complete','description':'Conclui o upload, verifica tamanho e SHA-256 integrais e sela o artefato para uso por artifact_id','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'}},'required':['slug','artifact_id'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','artifact_id':'art_111111111111111111111111'}]}},
 {'name':'workspace.change-set.validate','description':'Aplica temporariamente create, update, delete e mkdir, valida o resultado e sela o conjunto completo por digest','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'ref':{'type':'string','pattern':'^[A-Za-z0-9._/-]+$'},'title':{'type':'string','minLength':4,'maxLength':160},'description':{'type':'string','maxLength':4000},'ttl_seconds':{'type':'integer','minimum':300,'maximum':86400},'changes':{'type':'array','minItems':1,'maxItems':100,'items':{'type':'object','properties':{'operation':{'type':'string','enum':['create','update','delete','mkdir']},'path':{'type':'string','minLength':1,'maxLength':240},'content_base64':{'type':'string','maxLength':349528},'artifact_id':{'type':'string','pattern':'^art_[a-f0-9]{24}$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},'required':['operation','path'],'additionalProperties':False}}},'required':['slug','title','description','changes'],'additionalProperties':False}},
 {'name':'forgejo.proposal.change-set.plan','description':'Confirma o snapshot selado e apresenta o plano completo sem criar aprovação, branch ou PR','inputSchema':{'type':'object','properties':{'slug':{'type':'string','description':'Slug do projeto autorizado','pattern':'^[a-z0-9][a-z0-9-]*$'},'workspace_id':{'type':'string','description':'Workspace selado retornado pela validação','pattern':'^ws_[a-f0-9]{24}$'},'change_set_digest':{'type':'string','description':'Digest SHA-256 canônico do change set','pattern':'^[a-f0-9]{64}$'}},'required':['slug','workspace_id','change_set_digest'],'additionalProperties':False,'examples':[{'slug':'meu-projeto','workspace_id':'ws_0123456789abcdef01234567','change_set_digest':'0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'}]}},
 {'name':'approval.request-change-set-proposal','description':'Cria aprovação humana vinculada ao workspace e digest completos, sem armazenar conteúdos nos metadados','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'workspace_id':{'type':'string','pattern':'^ws_[a-f0-9]{24}$'},'change_set_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','workspace_id','change_set_digest','reason'],'additionalProperties':False}},
 {'name':'forgejo.proposal.change-set.create','description':'Cria branch e PR rascunho com o change set aprovado usando reserve-effect-finalize','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'workspace_id':{'type':'string','pattern':'^ws_[a-f0-9]{24}$'},'change_set_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','workspace_id','change_set_digest','approval_id'],'additionalProperties':False}},
 {'name':'forgejo.propose-edit','description':'Cria branch isolada e pull request rascunho após preview e aprovação vinculada de uso único','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000}},'required':['slug','approval_id','path','expected_sha256','find','replace','title','body'],'additionalProperties':False}},
 {'name':'forgejo.propose-edit.plan','description':'Calcula o digest canônico e o plano de uma proposta sem criar aprovação, branch ou pull request','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000}},'required':['slug','path','expected_sha256','find','replace','title','body'],'additionalProperties':False}},
 {'name':'approval.request-proposal','description':'Cria uma aprovação pendente vinculada ao digest canônico de uma proposta Forgejo','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'path':{'type':'string','minLength':10,'maxLength':240,'pattern':'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+[.]html$'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'find':{'type':'string','minLength':1,'maxLength':512},'replace':{'type':'string','maxLength':1024},'title':{'type':'string','minLength':4,'maxLength':160},'body':{'type':'string','maxLength':4000},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','path','expected_sha256','find','replace','title','body','reason'],'additionalProperties':False}},
 {'name':'approval.get','description':'Consulta uma aprovação própria vinculada ao projeto autorizado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','approval_id'],'additionalProperties':False}},
 {'name':'approval.cancel','description':'Cancela uma aprovação pendente solicitada pelo próprio cliente e libera uma nova solicitação corrigida','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'},'reason':{'type':'string','minLength':4,'maxLength':500}},'required':['slug','approval_id','reason'],'additionalProperties':False}},
 {'name':'forgejo.proposal.list','description':'Lista pull requests do projeto autorizado por meio do agente da forja, sem efeitos persistentes','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'state':{'type':'string','enum':['open','closed','all']},'limit':{'type':'integer','minimum':1,'maximum':50}},'required':['slug'],'additionalProperties':False}},
 {'name':'forgejo.proposal.close','description':'Fecha um pull request CloudIFF controlado sem excluir a branch','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','number'],'additionalProperties':False}},
 {'name':'forgejo.proposal.delete-branch','description':'Exclui a branch cloudif-proposal de um pull request já fechado ou mesclado','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647}},'required':['slug','number'],'additionalProperties':False}},
 {'name':'forgejo.proposal.merge.plan','description':'Calcula o digest canônico para merge aprovado de um PR CloudIFF','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'}},'required':['slug','number','expected_head_sha'],'additionalProperties':False}},
 {'name':'approval.request-merge','description':'Cria aprovação pendente vinculada ao merge de um PR e SHA específicos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','number','expected_head_sha','reason'],'additionalProperties':False}},
 {'name':'forgejo.proposal.merge','description':'Mescla PR CloudIFF após aprovação humana persistente de uso único','inputSchema':{'type':'object','properties':{'slug':{'type':'string','minLength':1,'maxLength':63,'pattern':'^[a-z0-9][a-z0-9-]*$'},'number':{'type':'integer','minimum':1,'maximum':2147483647},'expected_head_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','number','expected_head_sha','approval_id'],'additionalProperties':False}},
 {'name':'supabase.tables.list','description':'Lista tabelas e views do banco Supabase vinculado ao projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'schemas':{'type':'array','items':{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'maxItems':20},'include_system':{'type':'boolean'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.records.select','description':'Consulta registros de uma tabela com colunas, filtros, ordenação e limite estruturados','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'schema':{'type':'string','default':'public','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'table':{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'columns':{'type':'array','items':{'type':'string'},'maxItems':64},'filters':{'type':'object','properties':{},'additionalProperties':True},'order_by':{'type':'array','items':{'type':'string'},'maxItems':8},'limit':{'type':'integer','minimum':1,'maximum':500},'offset':{'type':'integer','minimum':0,'maximum':100000},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','table'],'additionalProperties':False}},
 {'name':'supabase.sql.query','description':'Executa SQL somente leitura em transação read-only com timeout e limite de linhas','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'sql':{'type':'string','minLength':1,'maxLength':65536},'max_rows':{'type':'integer','minimum':1,'maximum':500},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','sql'],'additionalProperties':False}},
 {'name':'supabase.auth.users.list','description':'Lista usuários do Supabase Auth sem tokens, senhas ou fatores secretos','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'page':{'type':'integer','minimum':1},'per_page':{'type':'integer','minimum':1,'maximum':100},'email':{'type':'string','maxLength':320}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.storage.buckets.list','description':'Lista buckets do Supabase Storage do projeto','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.storage.objects.list','description':'Lista objetos de um bucket do Supabase Storage','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'bucket':{'type':'string','minLength':1,'maxLength':100},'prefix':{'type':'string','maxLength':512},'limit':{'type':'integer','minimum':1,'maximum':1000},'offset':{'type':'integer','minimum':0,'maximum':100000},'sort_column':{'type':'string','enum':['name','created_at','updated_at','last_accessed_at']},'order':{'type':'string','enum':['asc','desc']}},'required':['slug','bucket'],'additionalProperties':False}},
 {'name':'supabase.storage.object.read','description':'Lê um arquivo do Supabase Storage com limite de tamanho e retorno UTF-8 ou base64','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'bucket':{'type':'string','minLength':1,'maxLength':100},'path':{'type':'string','minLength':1,'maxLength':1024},'max_bytes':{'type':'integer','minimum':1,'maximum':1048576}},'required':['slug','bucket','path'],'additionalProperties':False}},
 {'name':'supabase.secrets.list','description':'Lista nomes, estado e valores mascarados das variáveis protegidas do tenant','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.rls.inspect','description':'Consulta ativação de RLS e políticas existentes sem alterar o banco','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'schema':{'type':'string','default':'public','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'table':{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.schema.inspect','description':'Inspeciona tabelas, views, funções, triggers, índices e tipos do schema','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'schema':{'type':'string','default':'public','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'object_type':{'type':'string','enum':['all','table','view','function','trigger','index','type']},'name':{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.logs.read','description':'Lê logs sanitizados dos serviços Supabase sem expor tokens e senhas','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'service':{'type':'string','enum':['db','auth','rest','storage','realtime','kong','studio','functions','meta','supavisor']},'lines':{'type':'integer','minimum':1,'maximum':1000},'since_seconds':{'type':'integer','minimum':1,'maximum':604800}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.admin.config.read','description':'Consulta configuração administrativa sanitizada e saúde dos serviços do tenant','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'}},'required':['slug'],'additionalProperties':False}},
 {'name':'supabase.records.change.plan','description':'Planeja insert, update ou delete estruturado e calcula o digest sem alterar registros','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'schema':{'type':'string','default':'public','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'table':{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_$]*$'},'action':{'type':'string','enum':['insert','update','delete']},'values':{'type':'object','properties':{},'additionalProperties':True},'filters':{'type':'object','properties':{},'additionalProperties':True},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','table','action'],'additionalProperties':False}},
 {'name':'supabase.sql.change.plan','description':'Valida e planeja SQL com efeito, bloqueando capacidades de servidor e credenciais','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'sql':{'type':'string','minLength':1,'maxLength':65536},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','sql'],'additionalProperties':False}},
 {'name':'supabase.rls.change.plan','description':'Planeja CREATE, ALTER ou DROP POLICY e mudanças de ROW LEVEL SECURITY','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'sql':{'type':'string','minLength':1,'maxLength':65536},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','sql'],'additionalProperties':False}},
 {'name':'supabase.schema.change.plan','description':'Planeja criação ou alteração de tabelas, funções, triggers, índices, views, tipos ou sequências','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'sql':{'type':'string','minLength':1,'maxLength':65536},'timeout_ms':{'type':'integer','minimum':500,'maximum':30000}},'required':['slug','sql'],'additionalProperties':False}},
 {'name':'supabase.secrets.read.plan','description':'Planeja a exibição única de segredos selecionados sem retornar os valores','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'names':{'type':'array','items':{'type':'string','pattern':'^[A-Z_][A-Z0-9_]*$'},'minItems':1,'maxItems':20}},'required':['slug','names'],'additionalProperties':False}},
 {'name':'approval.request-supabase-operation','description':'Cria aprovação humana vinculada ao digest e ao payload exato de uma operação Supabase','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'operation':{'type':'string','enum':['records.change','sql.change','rls.change','schema.change','secrets.read']},'payload':{'type':'object','properties':{},'additionalProperties':True},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'reason':{'type':'string','minLength':4,'maxLength':500},'ttl_seconds':{'type':'integer','minimum':60,'maximum':86400}},'required':['slug','operation','payload','plan_digest','reason'],'additionalProperties':False}},
 {'name':'supabase.operation.execute','description':'Executa a operação Supabase aprovada com reserve-effect-finalize e vínculo ao digest','inputSchema':{'type':'object','properties':{'slug':{'type':'string','pattern':'^[a-z0-9][a-z0-9-]*$'},'operation':{'type':'string','enum':['records.change','sql.change','rls.change','schema.change','secrets.read']},'payload':{'type':'object','properties':{},'additionalProperties':True},'plan_digest':{'type':'string','pattern':'^[a-f0-9]{64}$'},'approval_id':{'type':'string','pattern':'^apr_[a-f0-9]{20}$'}},'required':['slug','operation','payload','plan_digest','approval_id'],'additionalProperties':False}},
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

def _tool_definition(tool_name):
    return next((item for item in TOOLS if item.get('name') == tool_name), None)


def _schema_type(schema):
    if not isinstance(schema, dict):
        return 'any'
    declared = schema.get('type')
    if isinstance(declared, list):
        return '|'.join(str(item) for item in declared)
    if declared:
        return str(declared)
    variants = schema.get('oneOf') or schema.get('anyOf') or []
    if variants:
        values=[]
        for variant in variants:
            value=_schema_type(variant)
            if value not in values:values.append(value)
        return '|'.join(values) if values else 'any'
    return 'any'


def _example_for_schema(schema, field='', include_optional=True, depth=0):
    if depth > 4 or not isinstance(schema, dict):
        return None
    if 'const' in schema:return schema['const']
    enum=schema.get('enum')
    if isinstance(enum,list) and enum:return enum[0]
    variants=schema.get('oneOf') or schema.get('anyOf') or []
    if variants:return _example_for_schema(variants[0],field,include_optional,depth+1)
    kind=schema.get('type')
    if isinstance(kind,list):kind=next((item for item in kind if item!='null'),kind[0] if kind else None)
    key=str(field or '').lower()
    if kind=='object' or ('properties' in schema and kind is None):
        properties=schema.get('properties') or {};required=set(schema.get('required') or [])
        result={}
        for name,child in properties.items():
            if include_optional or name in required:
                result[name]=_example_for_schema(child,name,include_optional,depth+1)
        return result
    if kind=='array':
        item=_example_for_schema(schema.get('items') or {},field,include_optional,depth+1)
        return [item] if item is not None else []
    if kind in ('integer','number'):
        minimum=schema.get('minimum')
        if minimum is not None:return minimum
        return 1
    if kind=='boolean':return True if key=='runtime' else False
    if kind=='null':return None
    if kind=='string' or kind is None:
        pattern=str(schema.get('pattern') or '')
        if key in {'slug','project_slug'}:return 'meu-projeto'
        if key=='workspace_id':return 'ws_'+'1'*24
        if key=='artifact_id':return 'art_'+'1'*24
        if key=='file_id':return 'file_'+'1'*16
        if 'digest' in key or key.endswith('sha256') or key=='expected_sha256':return 'a'*64
        if key=='approval_id':return 'apr_'+'1'*20
        if key in {'commit_sha','expected_head_sha','expected_previous_commit','expected_current_commit','target_commit','head_sha'}:return 'a'*40
        if key in {'environment','source_environment','target_environment'}:return 'preview'
        if key=='service':return 'api'
        if key in {'ref','commit_ref'}:return 'main'
        if key=='reason':return 'Operação revisada e autorizada'
        if key in {'name','names'} and ('A-Z' in pattern or not pattern):return 'APP_NAME'
        if key=='path':return 'site/index.html'
        if 'url' in key:return 'https://example.invalid'
        if key in {'secret_reference','source_secret_reference'}:
            if pattern.startswith('^cloudiff-secret://'):return 'cloudiff-secret://meu-projeto/preview/api/DATABASE_URL/v1'
            return 'vault://project/meu-projeto/secret'
        if key=='stage_id':return 'stage_'+'1'*24
        prefix_match=re.fullmatch(r'\^([A-Za-z][A-Za-z0-9_-]*)\_\[a-f0-9\]\{(\d+)\}\\$',pattern)
        if prefix_match:return prefix_match.group(1)+'_'+('1'*int(prefix_match.group(2)))
        fixed_hex=re.fullmatch(r'\^\[a-f0-9\]\{(\d+)\}\\$',pattern) or re.fullmatch(r'\^\[0-9a-f\]\{(\d+)\}\\$',pattern)
        if fixed_hex:return 'a'*int(fixed_hex.group(1))
        fixed_hex_dash=re.fullmatch(r'\^\[0-9a-f-\]\{(\d+)\}\\$',pattern)
        if fixed_hex_dash:return '1'*int(fixed_hex_dash.group(1))
        if pattern=='^[0-9a-f-]+$':return '1'*32
        if pattern.startswith('^[A-Z_') or pattern.startswith('^[A-Z]'):return 'APP_NAME'
        if pattern.startswith('^/'):return '/'
        if key=='job_id':
            if pattern.startswith('^toolchain_'):return 'toolchain_'+'1'*24
            return 'build_'+'1'*24
        if key=='build_job_id':return 'build_'+'1'*24
        if key=='image_record_id':return 'img_'+'1'*24
        if key=='preview_id':return ('prv_'+'1'*20) if pattern.startswith('^prv_') else ('pv_'+'1'*24)
        if key=='deployment_id':return 'dep_'+'1'*24
        if key=='build_id':return '1'*36 if '{36}' in pattern else '1'*32
        min_length=max(1,int(schema.get('minLength') or 1))
        return 'valor' if min_length<=5 else ('x'*min(min_length,32))
    return None


def _schema_contract(schema, required=False, depth=0):
    if depth > 3 or not isinstance(schema,dict):return {'type':'any','required':bool(required)}
    result={'type':_schema_type(schema),'required':bool(required)}
    for source,target in (
        ('description','description'),('enum','allowedValues'),('pattern','pattern'),
        ('minimum','minimum'),('maximum','maximum'),('minLength','minLength'),('maxLength','maxLength'),
        ('minItems','minItems'),('maxItems','maxItems'),
    ):
        if source in schema:result[target]=schema[source]
    if schema.get('items') is not None:
        result['items']=_schema_contract(schema.get('items') or {},False,depth+1)
    if schema.get('properties'):
        child_required=set(schema.get('required') or [])
        result['properties']={name:_schema_contract(child,name in child_required,depth+1) for name,child in schema['properties'].items()}
    variants=schema.get('oneOf') or schema.get('anyOf')
    if variants:result['variants']=[_schema_contract(item,False,depth+1) for item in variants[:6]]
    return result


def tool_usage(tool_name):
    definition=_tool_definition(tool_name)
    if not definition:
        return {'tool':tool_name,'known':False}
    schema=definition.get('inputSchema') or {'type':'object','properties':{}}
    properties=schema.get('properties') or {};required=list(schema.get('required') or [])
    optional=[name for name in properties if name not in set(required)]
    return {
        'tool':tool_name,
        'known':True,
        'description':definition.get('description') or '',
        'requiredParameters':required,
        'optionalParameters':optional,
        'parameters':{name:_schema_contract(child,name in set(required)) for name,child in properties.items()},
        'additionalPropertiesAllowed':schema.get('additionalProperties',True) is not False,
        'minimumExample':_example_for_schema(schema,'',False),
        'completeExample':(schema.get('examples') or [None])[0] or _example_for_schema(schema,'',True),
    }


def _validation_issue_payload(tool_name,args,issue):
    path='.'.join(str(part) for part in issue.absolute_path)
    code='invalid_arguments';field=path
    message=issue.message
    if issue.validator=='required':
        missing=next((name for name in issue.validator_value if name not in issue.instance),'')
        field='.'.join(filter(None,[path,missing]));code='missing_field';message=f'O campo {field or missing} é obrigatório.'
    elif issue.validator=='type':
        code='invalid_field_type';expected=issue.validator_value
        message=f'O campo {field or "arguments"} deve ser do tipo {expected}.'
    elif issue.validator=='enum':
        code='invalid_field_value';message=f'O campo {field or "arguments"} deve usar um dos valores permitidos.'
    elif issue.validator=='pattern':
        code='invalid_field_format';message=f'O campo {field or "arguments"} possui formato inválido.'
    elif issue.validator=='additionalProperties':
        code='unknown_field';known=set((issue.schema.get('properties') or {}).keys()) if isinstance(issue.schema,dict) else set()
        extras=sorted(set(issue.instance or {})-known) if isinstance(issue.instance,dict) else []
        if extras:field='.'.join(filter(None,[path,extras[0]]));message=f'O campo {field} não é aceito por esta ferramenta.'
    elif issue.validator in {'minimum','maximum','minLength','maxLength','minItems','maxItems'}:
        code='field_limit_violation';message=f'O campo {field or "arguments"} está fora dos limites permitidos.'
    return {
        'code':code,'field':field,'path':'$.'+field if field else '$','message':message,
        'receivedFields':sorted(str(key) for key in args) if isinstance(args,dict) else [],
        'usage':tool_usage(tool_name),
    }


def validate_tool_arguments(tool_name,args):
    definition=_tool_definition(tool_name)
    if not definition:return
    schema=definition.get('inputSchema') or {'type':'object'}
    validator=jsonschema.Draft202012Validator(schema)
    issues=sorted(validator.iter_errors(args),key=lambda item:(list(item.absolute_path),str(item.message)))
    if issues:raise ToolInputError(_validation_issue_payload(tool_name,args,issues[0]))


def enrich_tool_error(tool_name,args,error_payload=None,message='Parâmetros inválidos.'):
    payload=dict(error_payload or {})
    payload.setdefault('code','invalid_arguments')
    payload.setdefault('message',str(message or 'Parâmetros inválidos.')[:240])
    payload.setdefault('field','')
    payload.setdefault('path','$.'+payload['field'] if payload.get('field') else '$')
    payload.setdefault('receivedFields',sorted(str(key) for key in args) if isinstance(args,dict) else [])
    payload['tool']=tool_name or payload.get('tool') or ''
    payload.setdefault('usage',tool_usage(tool_name))
    return payload


READ_ONLY_TOOLS={
 'project.list','project.get','project.connectors','project.technologies.detect','project.manifest.validate','project.configuration.get','project.configuration.status','project.configuration.drift','project.configuration.reconcile.plan','project.observability.get','project.observability.alerts','project.environment.list','project.environment.get','project.environment.validate','project.environment.change.plan','project.environment.promote.plan','project.environment.history','project.environment.import.plan','project.environment.export','project.environment.secret.list','project.environment.secret.history','project.environment.secret.rotate.plan','project.environment.secret.revoke.plan','project.environment.secret.promote.plan','project.environment.secret.read.plan','workspace.normalize.plan','workspace.change-set.validate','forgejo.proposal.change-set.plan','runtime.catalog','runtime.detect','runtime.plan','runtime.validate',
 'build.plan','build.status','build.logs.read','build.artifact.get','deployment.preview.plan','deployment.preview.status',
 'approval.get','forgejo.proposal.list','forgejo.proposal.merge.plan','supabase.migrations.inspect','supabase.migrations.plan',
 'deployment.production.activation.plan','deployment.production.readiness','deployment.production.homologation.plan',
 'deployment.multiservice.plan','deployment.multiservice.status','deployment.production.plan','deployment.plan','deployment.promote-test.plan','deployment.promote-test.status','deployment.rollback-test.plan',
 'supabase.tables.list','supabase.records.select','supabase.sql.query','supabase.auth.users.list',
 'supabase.storage.buckets.list','supabase.storage.objects.list','supabase.storage.object.read','supabase.secrets.list',
 'supabase.rls.inspect','supabase.schema.inspect','supabase.logs.read','supabase.admin.config.read',
 'supabase.records.change.plan','supabase.sql.change.plan','supabase.rls.change.plan','supabase.schema.change.plan','supabase.secrets.read.plan'
,'project.toolchain.get','project.toolchain.validate','project.toolchain.plan','project.toolchain.build.plan','project.toolchain.build.status','project.toolchain.logs.read','project.toolchain.image.list','project.toolchain.image.get','project.toolchain.image.activate.plan','build.multiservice.plan','build.multiservice.status','preview.multiservice.plan','preview.multiservice.status'}
DESTRUCTIVE_TOOLS={
 'forgejo.proposal.delete-branch','forgejo.proposal.merge','deployment.production.homologation.deploy',
 'deployment.production.homologation.rollback','deployment.promote-test','deployment.rollback-test','supabase.operation.execute','forgejo.proposal.change-set.create'
,'build.multiservice.execute','deployment.multiservice.execute','preview.multiservice.create','preview.multiservice.delete','project.environment.change.execute','project.environment.promote.execute','project.environment.secret.stage','project.environment.secret.rotate.execute','project.environment.secret.revoke.execute','project.environment.secret.promote.execute','project.environment.secret.read.execute','project.toolchain.build.execute','project.toolchain.image.activate'}
OPEN_WORLD_PREFIXES=('forgejo.','supabase.','deployment.','approval.','build.')
for _tool in TOOLS:
    _name=str(_tool.get('name') or '')
    _readonly=_name in READ_ONLY_TOOLS
    _tool['annotations']={
        'title':_name.replace('.',' ').replace('-',' ').title(),
        'readOnlyHint':_readonly,
        'destructiveHint':_name in DESTRUCTIVE_TOOLS,
        'idempotentHint':_readonly,
        'openWorldHint':_name.startswith(OPEN_WORLD_PREFIXES),
    }
def control(path):
    r=urllib.request.Request(CONTROL+path,headers={'Authorization':'Bearer '+CONTROL_TOKEN,'Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=8) as x:return json.loads(x.read().decode())
def _tool_row(name):return next((x for x in TOOLS if x.get('name')==name),None)
def _client_scopes(row):
    if not row:return []
    raw=row.get('scopes_json')
    try:return json.loads(raw or '[]') if isinstance(raw,str) else list(row.get('scopes') or [])
    except Exception:return []
def _client_tool_names(row):
    scopes=set(_client_scopes(row));out=[]
    for tool in TOOLS:
        name=str(tool.get('name') or '');scope=SCOPE_BY_TOOL.get(name,'project:read')
        if '*' in scopes or scope in scopes:out.append(name)
    return out
def _action_schema(client_id):
    row=_oauth_client(client_id);projects=_client_projects(row)
    if not row or len(projects)!=1:return None
    slug=projects[0];available=_client_tool_names(row)
    read_tools=[x for x in available if x in READ_ONLY_TOOLS]
    write_tools=[x for x in available if x not in READ_ONLY_TOOLS]
    base='/cloudiff/mcp/actions/v1';security=[{'cloudiffOAuth':['mcp']}]
    responses={
      '200':{'description':'Resposta do conector CloudIFF','content':{'application/json':{'schema':{'$ref':'#/components/schemas/ActionResponse'}}}},
      '401':{'description':'Autenticação necessária'},
      '403':{'description':'Projeto ou ferramenta não autorizado'},
      '422':{'description':'Parâmetros inválidos'},
    }
    paths={
      base+'/project':{'get':{'operationId':'getCloudIFFProject','summary':'Consultar o projeto CloudIFF vinculado','description':'Retorna somente o projeto associado ao Client ID autenticado.','security':security,'x-openai-isConsequential':False,'responses':responses}},
      base+'/connectors':{'get':{'operationId':'getCloudIFFProjectConnectors','summary':'Consultar conectores do projeto','description':'Retorna Forgejo, Supabase, Komodo, MCP e ACL sanitizada do projeto vinculado.','security':security,'x-openai-isConsequential':False,'responses':responses}},
      base+'/tools':{'get':{'operationId':'listCloudIFFProjectTools','summary':'Listar ferramentas autorizadas','description':'Lista as ferramentas realmente liberadas para a identidade deste projeto.','security':security,'x-openai-isConsequential':False,'responses':responses}},
    }
    if read_tools:
        paths[base+'/read']={'post':{'operationId':'callCloudIFFReadTool','summary':'Executar ferramenta de consulta','description':'Executa somente ferramentas classificadas pelo servidor como leitura, plano ou inspeção sem efeito persistente. O projeto é imposto pelo token OAuth.','security':security,'x-openai-isConsequential':False,'requestBody':{'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/ReadToolRequest'}}}},'responses':responses}}
    if write_tools:
        paths[base+'/write']={'post':{'operationId':'callCloudIFFProjectTool','summary':'Executar operação controlada do projeto','description':'Executa uma ferramenta com efeito ou solicitação de aprovação. Aprovações humanas e políticas da CloudIFF continuam obrigatórias.','security':security,'x-openai-isConsequential':True,'requestBody':{'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/WriteToolRequest'}}}},'responses':responses}}
    schemas={
      'ActionArguments':{
        'type':'object',
        'description':'Parâmetros da ferramenta. O slug do projeto é sempre imposto pelo servidor.',
        'properties':{},
        'additionalProperties':True,
      },
      'ActionResponse':{
        'type':'object',
        'properties':{
          'ok':{'type':'boolean','description':'Indica se a operação foi concluída.'},
          'project_slug':{'type':'string','description':'Projeto vinculado à identidade OAuth.'},
          'tool':{'type':'string','description':'Ferramenta executada, quando aplicável.'},
          'result':{'description':'Resultado sanitizado retornado pela ferramenta.'},
          'error':{'type':'string','description':'Código de erro, quando aplicável.'},
        },
        'additionalProperties':True,
      },
      'ReadToolRequest':{
        'type':'object',
        'properties':{
          'tool':{'type':'string','enum':read_tools,'description':'Ferramenta autorizada de leitura, plano ou inspeção.'},
          'arguments':{'$ref':'#/components/schemas/ActionArguments'},
        },
        'required':['tool'],
        'additionalProperties':False,
      },
      'WriteToolRequest':{
        'type':'object',
        'properties':{
          'tool':{'type':'string','enum':write_tools,'description':'Ferramenta controlada com possível efeito persistente.'},
          'arguments':{'$ref':'#/components/schemas/ActionArguments'},
        },
        'required':['tool'],
        'additionalProperties':False,
      },
    }
    return {
      'openapi':'3.1.0',
      'info':{
        'title':'CloudIFF Actions — '+slug,
        'version':'1.0.1',
        'description':'Ações do projeto '+slug+' com OAuth público, PKCE, ACL por projeto e aprovações humanas server-side.',
        'termsOfService':PUBLIC_ORIGIN+'/cloudiff/mcp/privacy',
        'x-privacy-policy-url':PUBLIC_ORIGIN+'/cloudiff/mcp/privacy',
      },
      'servers':[{'url':PUBLIC_ORIGIN}],
      'externalDocs':{'description':'Política de privacidade do conector CloudIFF','url':PUBLIC_ORIGIN+'/cloudiff/mcp/privacy'},
      'components':{
        'schemas':schemas,
        'securitySchemes':{
          'cloudiffOAuth':{
            'type':'oauth2',
            'flows':{
              'authorizationCode':{
                'authorizationUrl':PUBLIC_ORIGIN+'/cloudiff/mcp/oauth/authorize',
                'tokenUrl':PUBLIC_ORIGIN+'/cloudiff/mcp/oauth/token',
                'scopes':{
                  'mcp':'Acesso às ferramentas MCP autorizadas do projeto',
                  'offline_access':'Renovação da sessão OAuth',
                },
              },
            },
          },
        },
      },
      'paths':paths,
      'x-cloudiff-project':slug,
      'x-cloudiff-client-id':client_id,
    }
def _privacy_html():
    return '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Privacidade do conector CloudIFF</title><style>body{font-family:Inter,Arial,sans-serif;max-width:760px;margin:0 auto;padding:48px 24px;line-height:1.65;color:#122018}h1{font-size:2rem}h2{margin-top:2rem}code{background:#eef3ee;padding:.15rem .35rem;border-radius:.35rem}</style></head><body><h1>Privacidade do conector CloudIFF</h1><p>O conector usa OAuth com PKCE e vincula cada sessão aos projetos autorizados para o usuário autenticado. O Client Secret não é necessário.</p><h2>Dados processados</h2><p>Identidade institucional, Client ID do projeto, ferramentas chamadas, projeto vinculado, resultado sanitizado e registros técnicos de auditoria.</p><h2>Limites</h2><p>O conector não entrega chaves privadas, senhas de banco ou tokens internos. Operações sensíveis continuam sujeitas às permissões e aprovações do Portal CloudIFF.</p><h2>Revogação</h2><p>A sessão pode ser revogada no endpoint <code>/cloudiff/mcp/oauth/revoke</code> ou pela remoção do usuário/projeto no Portal.</p></body></html>'
def workspace_probe(slug,trace_id):
    payload=json.dumps({'project_slug':slug,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/probe',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=15) as x:return json.loads(x.read().decode())
def multiservice_preview_call(method,path,payload=None,authz=None,timeout=180):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    headers={'Authorization':'Bearer '+MULTISERVICE_PREVIEW_TOKEN,'Content-Type':'application/json','Accept':'application/json'}
    if authz:
        headers['X-CloudIF-Actor-User']=supabase_actor_user(authz)
        headers['X-CloudIF-Actor-Groups']='|'.join(str(x) for x in (authz.get('authorized_groups') or []))
    request=urllib.request.Request(MULTISERVICE_PREVIEW_URL+path,data=raw,method=method,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'preview_broker_error','message':'Falha no coordenador de preview.'}}
        return error.code,data

def multiservice_preview_plan(build_job_id,routes,ttl_seconds,authz):
    payload={'build_job_id':build_job_id,'ttl_seconds':ttl_seconds,'actor_user':supabase_actor_user(authz),'actor_groups':list(authz.get('authorized_groups') or [])}
    if routes is not None:payload['routes']=routes
    code,data=multiservice_preview_call('POST','/v1/plan',payload,authz,180)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'multiservice_preview_plan_failed'))
    return data

def approval_create_multiservice_preview(slug,client_id,authz,plan,reason,ttl,trace_id):
    metadata={'preview_plan_digest':plan.get('preview_plan_digest'),'build_job_id':plan.get('build_job_id'),'build_plan_digest':plan.get('build_plan_digest'),'config_revision':plan.get('config_revision'),'config_digest':plan.get('config_digest'),'archive_sha256':plan.get('archive_sha256'),'preview_ttl_seconds':plan.get('ttl_seconds'),'summary':plan.get('summary') or {},'content_stored':False,'secret_values_in_metadata':False}
    payload={'project_slug':slug,'action':'preview.multiservice','requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

def build_broker_call(method,path,payload=None,timeout=180):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    request=urllib.request.Request(BUILD_URL+path,data=raw,method=method,headers={'Authorization':'Bearer '+BUILD_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'build_broker_error','message':'Falha no Build Broker.'}}
        return error.code,data

def multiservice_build_plan(slug,ref,expected_revision,trace_id):
    code,data=build_broker_call('POST','/v1/multiservice/plan',{'project_slug':slug,'ref':ref,'expected_revision':expected_revision,'trace_id':trace_id},timeout=180)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {}
        message=error.get('message') if isinstance(error,dict) else str(error)
        raise ValueError(message or 'multiservice_build_plan_failed')
    return data

def approval_create_multiservice_build(slug,client_id,authz,plan,reason,ttl,trace_id):
    metadata={
        'plan_digest':plan.get('plan_digest'),'config_revision':plan.get('config_revision'),
        'config_digest':plan.get('config_digest'),'toolchain_digest':plan.get('toolchain_digest'),
        'archive_sha256':plan.get('archive_sha256'),'ref':plan.get('ref'),'summary':plan.get('summary') or {},
        'content_stored':False,'secret_values_in_metadata':False,
    }
    payload={'project_slug':slug,'action':'build.multiservice','requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

def toolchain_broker_plan(slug,ref,expected_revision,trace_id,validate=False):
    path='/v1/toolchain/validate' if validate else '/v1/toolchain/plan'
    code,data=build_broker_call('POST',path,{'project_slug':slug,'ref':ref,'expected_revision':expected_revision,'trace_id':trace_id},timeout=900 if validate else 180)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};message=error.get('message') if isinstance(error,dict) else str(error)
        raise ValueError(message or 'toolchain_plan_failed')
    return data


def approval_create_toolchain(slug,client_id,authz,action,plan,reason,ttl,trace_id):
    if action=='project.toolchain.build':
        metadata={
            'toolchain_plan_digest':plan.get('plan_digest'),'config_revision':plan.get('config_revision'),
            'config_digest':plan.get('config_digest'),'requested_toolchain_digest':plan.get('requested_toolchain_digest'),
            'archive_sha256':plan.get('archive_sha256'),'ref':plan.get('ref'),
            'services':[{'service':item.get('service'),'toolchainDigest':item.get('toolchainDigest')} for item in plan.get('services') or []],
            'summary':plan.get('summary') or {},'content_stored':False,'secret_values_in_metadata':False,
        }
    else:
        metadata={
            'activation_plan_digest':plan.get('plan_digest'),'environment':plan.get('environment'),
            'job_id':plan.get('job_id'),'expected_revision':plan.get('expected_revision'),
            'after':plan.get('after') or [],'content_stored':False,'secret_values_in_metadata':False,
        }
    payload={'project_slug':slug,'action':action,'requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error


def toolchain_activation_plan(slug,environment,job_id,expected_revision,trace_id):
    code,data=build_broker_call('POST','/v1/toolchain/activation/plan',{'project_slug':slug,'environment':environment,'job_id':job_id,'expected_revision':expected_revision,'trace_id':trace_id},timeout=90)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};message=error.get('message') if isinstance(error,dict) else str(error)
        raise ValueError(message or 'toolchain_activation_plan_failed')
    return data


def workspace_prepare(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/prepare',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=45) as x:return json.loads(x.read().decode())
def workspace_detect_multiservice(slug,ref,trace_id):
    payload=json.dumps({'project_slug':slug,'ref':ref,'trace_id':trace_id},separators=(',',':')).encode()
    r=urllib.request.Request(WORKSPACE_URL+'/v1/detect-multiservice',data=payload,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode())
def project_config_call(method,path,payload=None,timeout=45):
    raw=json.dumps(payload,separators=(',',':')).encode() if payload is not None else None
    r=urllib.request.Request(PROJECT_CONFIG_URL+path,data=raw,method=method,headers={'Authorization':'Bearer '+PROJECT_CONFIG_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={'ok':False,'error':{'code':'project_config_error','message':'Falha ao consultar a configuração do projeto.'}}
        return e.code,data
def toolchain_configuration_revision(slug,expected_revision=0):
    code,current=project_config_call('GET','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration')
    actual=int(current.get('currentRevision') or 0) if isinstance(current,dict) else 0
    if code!=200 or actual<1:
        raise ToolStateError({
            'code':'toolchain_not_configured',
            'message':'O projeto ainda não possui configuração ou imagem de toolchain ativa. Aprove o cloudiff.yaml para criar a revisão 1 antes de usar a toolchain.',
            'currentRevision':actual,'minimumRevision':1,'configured':False,
            'nextAction':'Criar e aprovar o cloudiff.yaml para tornar o projeto configured e iniciar a revisão 1.',
        })
    expected=int(expected_revision or 0)
    if expected>=1 and expected!=actual:
        raise ToolStateError({
            'code':'revision_conflict',
            'message':f'A revisão esperada ({expected}) não corresponde à revisão atual ({actual}).',
            'expectedRevision':expected,'currentRevision':actual,'minimumRevision':1,'configured':True,
        })
    return actual


def project_environment_call(method,slug,path='',payload=None,query=None,timeout=45):
    suffix='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment'+path
    if query:suffix+='?'+urllib.parse.urlencode(query)
    return project_config_call(method,suffix,payload,timeout)

def project_secret_call(method,slug,path='',payload=None,query=None,timeout=45):
    suffix='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/secrets'+path
    if query:suffix+='?'+urllib.parse.urlencode(query)
    return project_config_call(method,suffix,payload,timeout)

def secret_plan_get(slug,plan_digest):
    code,data=project_secret_call('GET',slug,'/plans/'+urllib.parse.quote(plan_digest,safe=''))
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'secret_plan_not_found'))
    if data.get('secretValueIncluded') is not False or data.get('ciphertextIncluded') is not False:raise ValueError('secret_plan_public_contract_invalid')
    return data

def secret_approval_create(slug,client_id,authz,plan,reason,ttl,trace_id):
    actions={'rotate':'project.environment.secret.rotation','revoke':'project.environment.secret.revocation','promote':'project.environment.secret.promotion','read':'project.environment.secret.read'}
    action=actions.get(str(plan.get('action') or ''))
    if not action:raise ValueError('unsupported_secret_action')
    metadata={
      'secret_plan_digest':plan.get('planDigest'),'secret_action':plan.get('action'),
      'environment':plan.get('environment'),'service':plan.get('service'),'name':plan.get('name'),
      'stage_id':plan.get('stageId'),'secret_reference':plan.get('secretReference'),'source_secret_reference':plan.get('sourceSecretReference'),
      'expected_revision':plan.get('expectedRevision'),'target_version':plan.get('targetVersion'),
      'content_stored':False,'secret_values_in_metadata':False,'ciphertext_in_metadata':False,
    }
    payload={'project_slug':slug,'action':action,'requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

def secret_plan_metadata(plan):
    return {
      'secret_plan_digest':plan.get('planDigest'),'secret_action':plan.get('action'),
      'environment':plan.get('environment'),'service':plan.get('service'),'name':plan.get('name'),
      'stage_id':plan.get('stageId'),'secret_reference':plan.get('secretReference'),'source_secret_reference':plan.get('sourceSecretReference'),
      'expected_revision':plan.get('expectedRevision'),'target_version':plan.get('targetVersion'),
      'content_stored':False,'secret_values_in_metadata':False,'ciphertext_in_metadata':False,
    }

SECRET_READ_PLAN_TOOLS={'project.environment.secret.list','project.environment.secret.history','project.environment.secret.stage','project.environment.secret.rotate.plan','project.environment.secret.revoke.plan','project.environment.secret.promote.plan','project.environment.secret.read.plan'}
SECRET_APPROVAL_TOOLS={'approval.request-secret-rotation','approval.request-secret-revocation','approval.request-secret-promotion','approval.request-secret-read'}
SECRET_EXECUTE_TOOLS={'project.environment.secret.rotate.execute','project.environment.secret.revoke.execute','project.environment.secret.promote.execute','project.environment.secret.read.execute'}

def secret_mcp_read_or_plan(name,args,authz,client_id,trace_id):
    slug=str(args.get('slug') or '').strip();actor=supabase_actor_user(authz) or client_id
    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
    if name=='project.environment.secret.list':
        query={}
        if args.get('environment'):query['environment']=str(args['environment'])
        if args.get('service'):query['service']=str(args['service'])
        code,data=project_secret_call('GET',slug,query=query)
    elif name=='project.environment.secret.history':
        code,data=project_secret_call('GET',slug,'/history',query={'limit':int(args.get('limit') or 100)})
    elif name=='project.environment.secret.stage':
        secret_value=args.get('secret_value')
        try:
            payload={'environment':args['environment'],'service':str(args.get('service') or ''),'name':args['name'],'secretValue':secret_value,'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':actor}
            code,data=project_secret_call('POST',slug,'/stage',payload,timeout=30)
        finally:
            secret_value=None
    elif name=='project.environment.secret.rotate.plan':
        payload={'stageId':args['stage_id'],'expectedRevision':int(args['expected_revision']),'reason':args['reason'],'definition':args.get('definition') or {},'ttlSeconds':int(args.get('ttl_seconds') or 900),'activeTtlSeconds':int(args.get('active_ttl_seconds') or 0),'actor':actor}
        code,data=project_secret_call('POST',slug,'/rotate/plan',payload)
    elif name=='project.environment.secret.revoke.plan':
        payload={'secretReference':args['secret_reference'],'expectedRevision':int(args['expected_revision']),'reason':args['reason'],'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':actor}
        code,data=project_secret_call('POST',slug,'/revoke/plan',payload)
    elif name=='project.environment.secret.promote.plan':
        payload={'sourceSecretReference':args['source_secret_reference'],'targetEnvironment':args['target_environment'],'expectedRevision':int(args['expected_revision']),'reason':args['reason'],'definition':args.get('definition') or {},'ttlSeconds':int(args.get('ttl_seconds') or 900),'activeTtlSeconds':int(args.get('active_ttl_seconds') or 0),'actor':actor}
        code,data=project_secret_call('POST',slug,'/promote/plan',payload)
    else:
        payload={'secretReference':args['secret_reference'],'reason':args['reason'],'ttlSeconds':int(args.get('ttl_seconds') or 300),'actor':actor}
        code,data=project_secret_call('POST',slug,'/read/plan',payload)
    if code not in {200,201} or not data.get('ok'):
        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'secret_operation_failed'))
    if data.get('secretValueIncluded') is True or data.get('secretValuesIncluded') is True or data.get('ciphertextIncluded') is True or data.get('ciphertextsIncluded') is True:raise ValueError('secret_public_contract_violation')
    return data

def secret_mcp_request_approval(name,args,authz,client_id,trace_id):
    slug=str(args['slug']).strip();plan_digest=str(args['plan_digest']).strip().lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
    control('/v1/projects/'+urllib.parse.quote(slug,safe=''));plan=secret_plan_get(slug,plan_digest)
    expected_action={'approval.request-secret-rotation':'rotate','approval.request-secret-revocation':'revoke','approval.request-secret-promotion':'promote','approval.request-secret-read':'read'}[name]
    if plan.get('action')!=expected_action:raise ValueError('secret_plan_action_mismatch')
    if plan.get('consumed') or plan.get('status')!='planned' or int(plan.get('expiresAt') or 0)<=int(time.time()):raise ValueError('secret_plan_unavailable')
    created=secret_approval_create(slug,client_id,authz,plan,reason,ttl,trace_id)
    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
    return {'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'plan_digest':plan_digest,'secret_action':expected_action,'side_effects':False,'content_stored_in_approval':False,'secret_values_in_metadata':False,'ciphertext_in_metadata':False}

def secret_mcp_execute(name,args,authz,client_id,trace_id):
    slug=str(args['slug']).strip();plan_digest=str(args['plan_digest']).strip().lower();approval_id=str(args['approval_id']).strip();plan=secret_plan_get(slug,plan_digest)
    action_key={'project.environment.secret.rotate.execute':'rotate','project.environment.secret.revoke.execute':'revoke','project.environment.secret.promote.execute':'promote','project.environment.secret.read.execute':'read'}[name]
    if plan.get('action')!=action_key:raise ValueError('secret_plan_action_mismatch')
    if action_key=='rotate' and not hmac.compare_digest(str(args['stage_id']),str(plan.get('stageId') or '')):raise ValueError('secret_stage_binding_mismatch')
    if action_key=='revoke' and not hmac.compare_digest(str(args['secret_reference']),str(plan.get('secretReference') or '')):raise ValueError('secret_reference_binding_mismatch')
    if action_key=='promote' and not hmac.compare_digest(str(args['source_secret_reference']),str(plan.get('sourceSecretReference') or '')):raise ValueError('source_secret_reference_binding_mismatch')
    if action_key=='read' and not hmac.compare_digest(str(args['secret_reference']),str(plan.get('secretReference') or '')):raise ValueError('secret_reference_binding_mismatch')
    approval=approval_get(approval_id)
    if not approval:raise ValueError('approval_not_found')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise ValueError('approval_metadata_invalid')
    approval_action={'rotate':'project.environment.secret.rotation','revoke':'project.environment.secret.revocation','promote':'project.environment.secret.promotion','read':'project.environment.secret.read'}[action_key]
    reservation_id,execution_id=transaction_ids(approval_action,approval_id,client_id,plan_digest)
    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
    expected=secret_plan_metadata(plan)
    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')==approval_action and approval.get('requested_by')==client_id and approval.get('approved_by') and all(metadata.get(key)==value for key,value in expected.items()))
    if not valid:raise ValueError('approval_binding_mismatch')
    if approval.get('status')=='approved':
        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
    actor=supabase_actor_user(authz) or client_id;payload={'planDigest':plan_digest,'expectedRevision':int(plan['expectedRevision']),'approved':True,'actor':actor,'executionId':execution_id}
    if action_key=='rotate':payload['stageId']=args['stage_id'];path='/rotate/apply'
    elif action_key=='revoke':payload['secretReference']=args['secret_reference'];path='/revoke/apply'
    elif action_key=='promote':payload['sourceSecretReference']=args['source_secret_reference'];path='/promote/apply'
    else:payload['secretReference']=args['secret_reference'];path='/read/apply'
    code,data=project_secret_call('POST',slug,path,payload,timeout=120);current=approval_get(approval_id)
    if code==200 and data.get('ok'):
        if action_key=='read':
            if data.get('secretValueIncluded') is not True or not isinstance(data.get('secretValue'),str) or data.get('ciphertextIncluded') is True:raise ValueError('secret_read_contract_invalid')
        elif data.get('secretValueIncluded') is True or data.get('ciphertextIncluded') is True:raise ValueError('secret_public_contract_violation')
        if current and current.get('status')!='consumed':
            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
        data['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};data['ciphertextIncluded']=False
        if action_key=='read':data['secretValuesIncluded']=True;data['oneTime']=True;data['cacheControl']='no-store'
        else:data.pop('secretValue',None);data['secretValueIncluded']=False;data['secretValuesIncluded']=False
        return data
    if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'secret_apply_failed'))

def environment_plan_get(slug,plan_digest):
    code,data=project_environment_call('GET',slug,'/plans/'+urllib.parse.quote(plan_digest,safe=''))
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'environment_plan_not_found'))
    return data

def environment_approval_create(slug,client_id,authz,plan,reason,ttl,trace_id):
    action='project.environment.promotion' if plan.get('action')=='promotion' else 'project.environment.change'
    metadata={
      'environment_plan_digest':plan.get('planDigest'),'environment_action':plan.get('action'),
      'source_environment':plan.get('sourceEnvironment'),'target_environment':plan.get('targetEnvironment'),
      'expected_revision':plan.get('expectedRevision'),'summary':plan.get('summary') or {},
      'content_stored':False,'secret_values_in_metadata':False,
    }
    payload={'project_slug':slug,'action':action,'requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

def project_observability_call(path,slug,timeout=45):
    url=PROJECT_OBSERVABILITY_URL+path+'?'+urllib.parse.urlencode({'slug':slug})
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+PROJECT_OBSERVABILITY_TOKEN,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':'observability_unavailable'}
        return error.code,data

def runtime_reconciler_call(method,path,payload=None,timeout=90):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    request=urllib.request.Request(RUNTIME_RECONCILER_URL+path,data=raw,method=method,headers={'Authorization':'Bearer '+RUNTIME_RECONCILER_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':'runtime_reconciler_unavailable'}
        return error.code,data

def workspace_broker_post(path,payload,timeout=120):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    req=urllib.request.Request(WORKSPACE_URL+path,data=raw,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'workspace_broker_error','message':'Falha no Workspace Broker.'}}
        return error.code,data

def change_set_resolve(slug,workspace_id,digest_value,trace_id):
    code,data=workspace_broker_post('/v1/change-set/resolve',{'project_slug':slug,'trace_id':trace_id,'workspace_id':workspace_id,'change_set_digest':digest_value},timeout=90)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {}
        raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'workspace_resolve_failed'))
    result=data.get('result') or {}
    if not result.get('sealed') or not result.get('sourceUnchanged'):raise ValueError('workspace_not_sealed_or_source_changed')
    return result

def approval_create_change_set(slug,client_id,authz,workspace_id,digest_value,archive_sha,summary,reason,ttl,trace_id):
    payload={'project_slug':slug,'action':'forgejo.propose-change-set','requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':{'workspace_id':workspace_id,'change_set_digest':digest_value,'archive_sha256':archive_sha,'summary':summary,'secret_values_in_metadata':False,'content_stored':False}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

def session_file_resolve(file_id,expected_size,expected_sha256,trace_id):
    if not SESSION_FILE_RESOLVER_URL or not SESSION_FILE_RESOLVER_TOKEN:
        raise ValueError('O importador de arquivos da sessão ainda não está configurado no servidor. Use workspace.artifact.upload.batch para enviar chunks pequenos.')
    parsed=urlparse(SESSION_FILE_RESOLVER_URL)
    loopback_hosts={'127.0.0.1','localhost','::1'}
    if not parsed.hostname or parsed.scheme not in {'https','http'} or (parsed.scheme=='http' and parsed.hostname not in loopback_hosts):
        raise ValueError('session_file_resolver_invalid')
    payload=json.dumps({'file_id':file_id,'trace_id':trace_id},separators=(',',':')).encode()
    req=urllib.request.Request(SESSION_FILE_RESOLVER_URL,data=payload,method='POST',headers={'Authorization':'Bearer '+SESSION_FILE_RESOLVER_TOKEN,'Content-Type':'application/json','Accept':'application/octet-stream'})
    try:
        with urllib.request.urlopen(req,timeout=120) as response:
            header_length=response.headers.get('Content-Length')
            if header_length is not None and int(header_length)!=int(expected_size):raise ValueError('session_file_size_mismatch')
            raw=response.read(int(expected_size)+1);headers=response.headers
    except urllib.error.HTTPError as error:
        raise ValueError('session_file_resolver_rejected') from error
    except urllib.error.URLError as error:
        raise ValueError('session_file_resolver_unavailable') from error
    if len(raw)!=int(expected_size) or len(raw)>64*1024*1024:raise ValueError('session_file_size_mismatch')
    digest=hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(digest,str(expected_sha256).lower()):raise ValueError('session_file_sha256_mismatch')
    returned_id=str(headers.get('X-CloudIF-File-Id') or '')
    if returned_id and returned_id!=file_id:raise ValueError('session_file_id_mismatch')
    returned_sha=str(headers.get('X-CloudIF-File-Sha256') or '').lower()
    if returned_sha and not hmac.compare_digest(returned_sha,digest):raise ValueError('session_file_resolver_digest_mismatch')
    return raw

def workspace_artifact_import_bytes(slug,filename,raw,expected_sha256,ttl_seconds,trace_id):
    start_payload={'project_slug':slug,'trace_id':trace_id,'filename':filename,'expected_size':len(raw),'expected_sha256':expected_sha256,'ttl_seconds':ttl_seconds}
    code,data=workspace_broker_post('/v1/artifact/start',start_payload,timeout=90)
    if code not in {200,201} or not data.get('ok'):raise ValueError('artifact_import_start_failed')
    started=data.get('result') or data;artifact_id=str(started.get('artifact_id') or '')
    index=0
    stride=8*1024*16
    for offset in range(0,len(raw),stride):
        group=[];part=raw[offset:offset+stride]
        for inner in range(0,len(part),8*1024):
            chunk=part[inner:inner+8*1024]
            group.append({'chunk_index':index,'content_base64':base64.b64encode(chunk).decode(),'chunk_sha256':hashlib.sha256(chunk).hexdigest()});index+=1
        code,batch=workspace_broker_post('/v1/artifact/batch',{'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id,'chunks':group},timeout=90)
        if code not in {200,201} or not batch.get('ok'):raise ValueError('artifact_import_batch_failed')
    code,done=workspace_broker_post('/v1/artifact/complete',{'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id},timeout=90)
    if code not in {200,201} or not done.get('ok'):raise ValueError('artifact_import_complete_failed')
    result=done.get('result') or done
    if result.get('sha256')!=expected_sha256 or int(result.get('size') or -1)!=len(raw):raise ValueError('artifact_import_integrity_failed')
    result.update({'imported':True,'transport':'session_file_resolver','batch_calls':(index+15)//16})
    return result

def workspace_artifact_read(slug,artifact_id,expected_sha256,expected_size,trace_id):
    payload={'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id,'expected_sha256':expected_sha256,'expected_size':int(expected_size)}
    raw=json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(WORKSPACE_URL+'/v1/artifact/read',data=raw,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/octet-stream'})
    try:
        with urllib.request.urlopen(req,timeout=120) as response:
            body=response.read(64*1024*1024+1);headers=response.headers
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(((data.get('error') or {}).get('message') if isinstance(data.get('error'),dict) else data.get('error')) or 'artifact_read_failed')) from error
    if len(body)>64*1024*1024:raise ValueError('artifact_too_large')
    got_id=str(headers.get('X-CloudIF-Artifact-Id') or '');got_sha=str(headers.get('X-CloudIF-Artifact-Sha256') or '').lower();got_size=int(headers.get('X-CloudIF-Artifact-Size') or '-1');expires=int(headers.get('X-CloudIF-Artifact-Expires') or '0')
    if got_id!=artifact_id or got_sha!=expected_sha256 or got_size!=int(expected_size) or len(body)!=got_size or hashlib.sha256(body).hexdigest()!=got_sha or expires<=int(time.time()):raise ValueError('artifact_read_integrity_failed')
    return body,{'artifact_id':got_id,'sha256':got_sha,'size':got_size,'expires_at':expires}

def forgejo_artifact_stage(slug,metadata,raw):
    req=urllib.request.Request(FORJA_URL+'/project/proposal/artifact/stage',data=raw,method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Authorization':'Bearer '+FORJA_TOKEN,'Content-Type':'application/octet-stream','Accept':'application/json','X-CloudIF-Artifact-Id':metadata['artifact_id'],'X-CloudIF-Project-Slug':slug,'X-CloudIF-Artifact-Sha256':metadata['sha256'],'X-CloudIF-Artifact-Size':str(metadata['size']),'X-CloudIF-Artifact-Expires':str(metadata['expires_at'])})
    try:
        with urllib.request.urlopen(req,timeout=180) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        return error.code,data
    except Exception:return 599,{'ok':False,'error':'artifact_stage_response_unknown'}

def stage_change_set_artifacts(slug,changes,trace_id):
    staged=[]
    for item in changes or []:
        artifact_id=str(item.get('artifact_id') or '')
        if not artifact_id:continue
        digest=str(item.get('content_sha256') or '').lower();size=int(item.get('size') or 0)
        raw,metadata=workspace_artifact_read(slug,artifact_id,digest,size,trace_id)
        code,result=forgejo_artifact_stage(slug,metadata,raw)
        if code not in {200,201} or not result.get('ok'):raise ValueError(str(result.get('error') or 'artifact_stage_failed'))
        staged.append({'artifact_id':artifact_id,'sha256':digest,'size':size})
    return staged

def forgejo_change_set_create(payload):
    req=urllib.request.Request(FORJA_URL+'/project/proposal/change-set/create',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'X-CloudIF-Token':FORJA_TOKEN,'Authorization':'Bearer '+FORJA_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=180) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        return error.code,data
    except Exception:
        return 599,{'ok':False,'error':'forgejo_response_unknown'}

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
def supabase_actor_user(authz):return str(authz.get('authorized_user') or authz.get('owner_user') or '')
def supabase_broker_call(path,slug,authz,payload=None,action='',operation='',plan_digest='',execution_id='',timeout=60):
    body={'project_slug':slug,'actor_user':supabase_actor_user(authz),'actor_groups':list(authz.get('authorized_groups') or []),'payload':payload or {}}
    if action:body['action']=action
    if operation:body['operation']=operation
    if plan_digest:body['plan_digest']=plan_digest
    if execution_id:body['execution_id']=execution_id
    req=urllib.request.Request(SUPABASE_MCP_URL+path,data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+SUPABASE_MCP_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as x:return x.status,json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        return e.code,data
    except Exception:
        return 599,{'ok':False,'error':'supabase_mcp_broker_unavailable'}
def supabase_operation_action(operation):
    if operation not in {'records.change','sql.change','rls.change','schema.change','secrets.read'}:raise ValueError('invalid_supabase_operation')
    return 'supabase.operation.'+operation
def supabase_approval_create(slug,client_id,authz,operation,digest,summary,reason,ttl,trace_id):
    action=supabase_operation_action(operation)
    payload={'project_slug':slug,'action':action,'requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':{'supabase_operation':operation,'supabase_plan_digest':digest,'summary':summary,'actor_user':supabase_actor_user(authz),'secret_values_in_metadata':False}}
    req=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:data=json.load(e)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from e
def supabase_plan(slug,authz,operation,payload):
    code,data=supabase_broker_call('/v1/plan',slug,authz,payload=payload,operation=operation,timeout=45)
    if code!=200 or not data.get('ok') or data.get('side_effect_free') is not True:raise ValueError(str(data.get('error') or 'supabase_plan_failed'))
    return data
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
def deployment_multiservice_plan_call(payload,timeout=120):
    request=urllib.request.Request(DEPLOYMENT_URL+'/v1/multiservice-plan',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'deployment_plan_failed','message':'Falha ao planejar o deploy.'}}
        return error.code,data

def deployment_multiservice_status_call(deployment_id,timeout=60):
    query=urllib.parse.urlencode({'deployment_id':deployment_id})
    request=urllib.request.Request(DEPLOYMENT_URL+'/v1/multiservice-status?'+query,headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'deployment_status_failed','message':'Falha ao consultar o deploy.'}}
        return error.code,data

def deployment_multiservice_execute_call(payload,timeout=660):
    request=urllib.request.Request(DEPLOYMENT_URL+'/v1/multiservice-deploy',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+DEPLOYMENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'deployment_execute_failed','message':'Falha ao executar o deploy.'}}
        return error.code,data

def approval_create_multiservice_deployment(slug,client_id,authz,plan,reason,ttl,trace_id):
    operation=plan.get('operation') or {};reconciliation=plan.get('reconciliation') or {}
    metadata={
        'deployment_plan_digest':plan.get('deployment_plan_digest'),'environment':plan.get('environment'),
        'build_job_id':operation.get('build_job_id'),'build_plan_digest':operation.get('build_plan_digest'),
        'config_revision':operation.get('config_revision'),'config_digest':operation.get('config_digest'),
        'toolchain_digest':operation.get('toolchain_digest'),'archive_sha256':operation.get('archive_sha256'),
        'variables_digest':plan.get('variables_digest'),'routes':operation.get('routes') or [],
        'membership_revision':reconciliation.get('membershipRevision'),'acl_digest':reconciliation.get('aclDigest'),
        'summary':plan.get('summary') or {},'content_stored':False,'secret_values_in_metadata':False,
    }
    payload={'project_slug':slug,'action':'deployment.multiservice','requested_by':client_id,'requester_role':str(authz.get('project_role') or 'agent'),'ttl_seconds':ttl,'reason':reason,'trace_id':trace_id,'metadata':metadata}
    request=urllib.request.Request(APPROVAL_URL+'/v1/approvals',data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={}
        raise ValueError(str(data.get('error') or 'approval_create_failed')) from error

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
 'project.environment.list':'project:environment-read','project.environment.get':'project:environment-read','project.environment.validate':'project:environment-plan','project.environment.change.plan':'project:environment-plan','approval.request-environment-change':'approval:request-environment-change','project.environment.change.execute':'project:environment-execute','project.environment.promote.plan':'project:environment-plan','approval.request-environment-promotion':'approval:request-environment-promotion','project.environment.promote.execute':'project:environment-promote','project.environment.history':'project:environment-read','project.environment.import.plan':'project:environment-plan','project.environment.export':'project:environment-read',
 'project.environment.secret.list':'project:environment-secret-read','project.environment.secret.history':'project:environment-secret-read','project.environment.secret.stage':'project:environment-secret-stage','project.environment.secret.rotate.plan':'project:environment-secret-plan','approval.request-secret-rotation':'approval:request-secret-rotation','project.environment.secret.rotate.execute':'project:environment-secret-execute','project.environment.secret.revoke.plan':'project:environment-secret-plan','approval.request-secret-revocation':'approval:request-secret-revocation','project.environment.secret.revoke.execute':'project:environment-secret-execute','project.environment.secret.promote.plan':'project:environment-secret-plan','approval.request-secret-promotion':'approval:request-secret-promotion','project.environment.secret.promote.execute':'project:environment-secret-execute','project.environment.secret.read.plan':'project:environment-secret-read-plan','approval.request-secret-read':'approval:request-secret-read','project.environment.secret.read.execute':'project:environment-secret-read-execute',
 'project.toolchain.get':'project:toolchain-read','project.toolchain.validate':'project:toolchain-plan','project.toolchain.plan':'project:toolchain-plan','project.toolchain.build.plan':'project:toolchain-plan','approval.request-toolchain-build':'approval:request-toolchain-build','project.toolchain.build.execute':'project:toolchain-build-execute','project.toolchain.build.status':'project:toolchain-read','project.toolchain.logs.read':'project:toolchain-read','project.toolchain.image.list':'project:toolchain-read','project.toolchain.image.get':'project:toolchain-read','project.toolchain.image.activate.plan':'project:toolchain-activate-plan','approval.request-toolchain-activation':'approval:request-toolchain-activation','project.toolchain.image.activate':'project:toolchain-activate-execute',
 'runtime.catalog':'project:read','runtime.detect':'project:read','runtime.plan':'project:read','runtime.validate':'project:read','project.technologies.detect':'workspace:detect-multiservice','project.manifest.validate':'project:configuration-read','project.configuration.get':'project:configuration-read','project.configuration.status':'project:runtime-status-read','project.configuration.drift':'project:runtime-status-read','project.configuration.reconcile.plan':'project:runtime-reconcile-plan','project.observability.get':'project:observability-read','project.observability.alerts':'project:observability-read','build.plan':'project:read','build.multiservice.plan':'build:multiservice-plan','build.multiservice.status':'build:multiservice-plan','approval.request-multiservice-build':'approval:request-multiservice-build','build.multiservice.execute':'build:multiservice-execute','preview.multiservice.plan':'preview:multiservice-plan','preview.multiservice.status':'preview:multiservice-plan','approval.request-multiservice-preview':'approval:request-multiservice-preview','preview.multiservice.create':'preview:multiservice-execute','preview.multiservice.delete':'preview:multiservice-delete','build.request':'workspace:test-static','build.status':'project:read','build.logs.read':'project:read','build.artifact.get':'project:read','deployment.multiservice.plan':'deployment:multiservice-plan','deployment.multiservice.status':'deployment:multiservice-plan','approval.request-multiservice-deployment':'approval:request-multiservice-deployment','deployment.multiservice.execute':'deployment:multiservice-execute','deployment.preview.plan':'project:read','deployment.preview.status':'project:read','approval.request-preview':'approval:request-preview','deployment.preview':'deployment:preview',
 'workspace.probe':'workspace:probe','workspace.prepare':'workspace:prepare','workspace.validate':'workspace:validate','workspace.test-static':'workspace:test-static','workspace.preview-static':'workspace:preview-static','workspace.edit-preview':'workspace:edit-preview',
 'forgejo.propose-edit':'forgejo:propose-edit','forgejo.propose-edit.plan':'forgejo:plan-edit','approval.request-proposal':'approval:request-proposal','workspace.normalize.plan':'workspace:change-set-plan','workspace.artifact.upload.start':'workspace:change-set-plan','workspace.artifact.upload.chunk':'workspace:change-set-plan','workspace.artifact.upload.batch':'workspace:change-set-plan','workspace.artifact.import':'workspace:change-set-plan','workspace.artifact.upload.ticket':'workspace:change-set-plan','workspace.artifact.upload.complete':'workspace:change-set-plan','workspace.change-set.validate':'workspace:change-set-plan','forgejo.proposal.change-set.plan':'workspace:change-set-plan','approval.request-change-set-proposal':'approval:request-change-set','forgejo.proposal.change-set.create':'forgejo:propose-change-set','approval.get':'approval:read-own','approval.cancel':'approval:read-own','forgejo.proposal.list':'forgejo:proposal-read','forgejo.proposal.close':'forgejo:proposal-close','forgejo.proposal.delete-branch':'forgejo:proposal-delete-branch','forgejo.proposal.merge.plan':'forgejo:proposal-merge-plan','approval.request-merge':'approval:request-merge','forgejo.proposal.merge':'forgejo:proposal-merge',
 'deployment.production.homologation.plan':'deployment:production-plan','approval.request-production-homologation':'approval:request-deploy','deployment.production.homologation.deploy':'deployment:production-plan','deployment.production.homologation.rollback':'deployment:production-plan','deployment.production.activation.plan':'deployment:production-plan','approval.request-production-activation':'approval:request-deploy','deployment.production.readiness':'project:read','deployment.production.plan':'deployment:production-plan','supabase.migrations.inspect':'supabase:migration-inspect','supabase.migrations.plan':'supabase:migration-plan','deployment.plan':'deployment:plan','approval.request-deploy':'approval:request-deploy','deployment.validate':'deployment:validate','deployment.promote-test.plan':'deployment:promote-test-plan','approval.request-promote-test':'approval:request-promote-test','deployment.promote-test':'deployment:promote-test','deployment.promote-test.status':'deployment:promote-test-status','deployment.rollback-test.plan':'deployment:rollback-test-plan','approval.request-rollback-test':'approval:request-rollback-test','deployment.rollback-test':'deployment:rollback-test',
 'supabase.tables.list':'supabase:database-read','supabase.records.select':'supabase:database-read','supabase.sql.query':'supabase:database-read','supabase.rls.inspect':'supabase:database-read','supabase.schema.inspect':'supabase:database-read',
 'supabase.auth.users.list':'supabase:auth-read','supabase.storage.buckets.list':'supabase:storage-read','supabase.storage.objects.list':'supabase:storage-read','supabase.storage.object.read':'supabase:storage-read',
 'supabase.secrets.list':'supabase:admin-read','supabase.logs.read':'supabase:admin-read','supabase.admin.config.read':'supabase:admin-read',
 'supabase.records.change.plan':'supabase:change-plan','supabase.sql.change.plan':'supabase:change-plan','supabase.rls.change.plan':'supabase:change-plan','supabase.schema.change.plan':'supabase:change-plan','supabase.secrets.read.plan':'supabase:change-plan',
 'approval.request-supabase-operation':'approval:request-supabase','supabase.operation.execute':'supabase:change-execute'
}
SUPABASE_READ_TOOL_ACTIONS={
 'supabase.tables.list':'tables.list','supabase.records.select':'records.select','supabase.sql.query':'sql.query',
 'supabase.auth.users.list':'auth.users.list','supabase.storage.buckets.list':'storage.buckets.list',
 'supabase.storage.objects.list':'storage.objects.list','supabase.storage.object.read':'storage.object.read',
 'supabase.secrets.list':'secrets.list','supabase.rls.inspect':'rls.inspect','supabase.schema.inspect':'schema.inspect',
 'supabase.logs.read':'logs.read','supabase.admin.config.read':'admin.config.read'
}
SUPABASE_PLAN_TOOL_OPERATIONS={
 'supabase.records.change.plan':'records.change','supabase.sql.change.plan':'sql.change',
 'supabase.rls.change.plan':'rls.change','supabase.schema.change.plan':'schema.change',
 'supabase.secrets.read.plan':'secrets.read'
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
    def sendhtml(self,code,text):
        raw=str(text).encode();self.send_response(code);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','public, max-age=300');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'");self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def _action_identity(self):
        if not self.auth():self.sendj(401,{'ok':False,'error':'unauthorized'});return None
        client_id=self.headers.get('X-CloudIF-Client','').strip();row=_oauth_client(client_id);projects=_client_projects(row)
        if not row or len(projects)!=1:self.sendj(403,{'ok':False,'error':'project_identity_invalid'});return None
        oauth=getattr(self,'_oauth',None) or {};slug=str(oauth.get('project_slug') or projects[0])
        if slug!=projects[0]:self.sendj(403,{'ok':False,'error':'project_denied'});return None
        return {'client_id':client_id,'project_slug':slug,'row':row,'tools':_client_tool_names(row)}
    def _action_rpc(self,identity,tool,args):
        toolrow=_tool_row(tool)
        if not toolrow or tool not in identity['tools']:raise PermissionError('tool_denied')
        clean=dict(args or {});props=(toolrow.get('inputSchema') or {}).get('properties') or {}
        if 'slug' in props:clean['slug']=identity['project_slug']
        body=json.dumps({'jsonrpc':'2.0','id':'action-'+uuid.uuid4().hex,'method':'tools/call','params':{'name':tool,'arguments':clean}},ensure_ascii=False,separators=(',',':')).encode()
        headers={'Content-Type':'application/json','Authorization':self.headers.get('Authorization',''),'X-CloudIF-Client':identity['client_id'],'X-CloudIF-Trace-Id':self.headers.get('X-CloudIF-Trace-Id') or uuid.uuid4().hex}
        req=urllib.request.Request(f'http://127.0.0.1:{PORT}/mcp',data=body,method='POST',headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=180) as x:data=json.load(x)
        except urllib.error.HTTPError as e:
            try:data=json.load(e)
            except Exception:data={'error':{'message':'connector_request_failed'}}
            raise ValueError(str((data.get('error') or {}).get('message') or 'connector_request_failed')) from e
        if data.get('error'):raise ValueError(str((data.get('error') or {}).get('message') or 'tool_failed'))
        result=data.get('result') or {};items=result.get('content') or []
        text=items[0].get('text') if items and isinstance(items[0],dict) else None
        if isinstance(text,str):
            try:return json.loads(text)
            except Exception:return text
        return result
    def auth(self):
        got=self.headers.get('Authorization','');raw=got[7:] if got.startswith('Bearer ') else ''
        _oauth_cleanup();oauth=OAUTH_ACCESS.get(raw)
        if oauth:
            self._oauth=oauth
            if not self.headers.get('X-CloudIF-Client'):self.headers['X-CloudIF-Client']=oauth['client_id']
            if not oauth.get('public_client'):
                self.headers.replace_header('Authorization','Bearer '+oauth['secret'])
            return True
        client=self.headers.get('X-CloudIF-Client','').strip()
        if client:return got.startswith('Bearer ') and len(got)>20
        return bool(TOKEN) and hmac.compare_digest(got,'Bearer '+TOKEN)
    def authorize_client(self,scope,slug):
        client=self.headers.get('X-CloudIF-Client','').strip()
        if not client:return {'ok':True,'legacy':True,'client_id':'internal'}
        oauth=getattr(self,'_oauth',None) or {}
        if oauth.get('public_client'):
            project_slug=str(oauth.get('project_slug') or '')
            if slug and slug!=project_slug:return {'ok':False,'reason':'project_denied'}
            payload=json.dumps({'client_id':client,'scope':scope,'project_slug':slug or project_slug,'authorized_user':oauth.get('authorized_user','')},separators=(',',':')).encode()
            path='/v1/authorize-public'
        else:
            raw=self.headers.get('Authorization','')[7:]
            payload=json.dumps({'client_id':client,'token':raw,'scope':scope,'project_slug':slug},separators=(',',':')).encode()
            path='/v1/authorize'
        req=urllib.request.Request(AGENT_URL+path,data=payload,method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+AGENT_ADMIN_TOKEN})
        with urllib.request.urlopen(req,timeout=5) as x:data=json.load(x)
        if oauth.get('public_client'):
            data.update({'authorized_user':oauth.get('authorized_user',''),'authorized_groups':oauth.get('authorized_groups',[]),'project_role':oauth.get('project_role','viewer')})
        else:data.setdefault('project_role','service')
        return data
    def redirect(self,url):self.send_response(302);self.send_header('Location',url);self.send_header('Cache-Control','no-store');self.end_headers()
    def do_HEAD(self):
        path=urlparse(self.path).path
        content_type='';length=0
        if path=='/cloudiff/mcp/privacy':
            raw=_privacy_html().encode();content_type='text/html; charset=utf-8';length=len(raw)
        else:
            match=re.fullmatch(r'/cloudiff/mcp/openapi/([A-Za-z0-9._-]{3,160})[.]json',path)
            schema=_action_schema(match.group(1)) if match else None
            if schema:
                raw=json.dumps(schema,ensure_ascii=False,separators=(',',':')).encode();content_type='application/json';length=len(raw)
        if not content_type:self.send_response(404);self.send_header('Cache-Control','no-store');self.end_headers();return
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(length));self.send_header('Cache-Control','public, max-age=300');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
    def do_GET(self):
        parsed=urlparse(self.path);path=parsed.path
        if path in {'/.well-known/oauth-authorization-server','/cloudiff/mcp/.well-known/oauth-authorization-server','/oauth/.well-known/oauth-authorization-server'}:return self.sendj(200,_oauth_metadata())
        if path in {'/.well-known/oauth-protected-resource','/.well-known/oauth-protected-resource/cloudiff/mcp','/cloudiff/mcp/.well-known/oauth-protected-resource'}:return self.sendj(200,_oauth_metadata(True))
        if path=='/cloudiff/mcp/privacy':return self.sendhtml(200,_privacy_html())
        match=re.fullmatch(r'/cloudiff/mcp/openapi/([A-Za-z0-9._-]{3,160})[.]json',path)
        if match:
            schema=_action_schema(match.group(1));return self.sendj(200,schema) if schema else self.sendj(404,{'ok':False,'error':'schema_not_found'})
        if path in {'/cloudiff/mcp/actions/v1/project','/cloudiff/mcp/actions/v1/connectors','/cloudiff/mcp/actions/v1/tools'}:
            identity=self._action_identity()
            if not identity:return
            try:
                if path.endswith('/project'):result=self._action_rpc(identity,'project.get',{})
                elif path.endswith('/connectors'):result=self._action_rpc(identity,'project.connectors',{})
                else:result=[{'name':name,'description':(_tool_row(name) or {}).get('description',''),'annotations':(_tool_row(name) or {}).get('annotations',{})} for name in identity['tools']]
                return self.sendj(200,{'ok':True,'project_slug':identity['project_slug'],'result':result})
            except PermissionError as e:return self.sendj(403,{'ok':False,'error':str(e)})
            except Exception as e:return self.sendj(422,{'ok':False,'error':str(e)})
        if path in {'/authorize','/oauth/authorize','/cloudiff/mcp/oauth/authorize'}:
            q=parse_qs(parsed.query);client_id=(q.get('client_id') or [''])[0];redirect_uri=(q.get('redirect_uri') or [''])[0];state=(q.get('state') or [''])[0];challenge=(q.get('code_challenge') or [''])[0];method=(q.get('code_challenge_method') or [''])[0]
            username=self.headers.get('X-authentik-username','').strip();groups=self.headers.get('X-authentik-groups','')
            client=_public_oauth_client(client_id,username,groups);flow=_callback_mode(redirect_uri)
            pkce_valid=flow=='pkce' and method=='S256' and bool(challenge)
            actions_valid=flow=='chatgpt_actions' and not challenge and not method
            if (q.get('response_type') or [''])[0]!='code' or not client or not (pkce_valid or actions_valid):return self.sendj(400,{'error':'invalid_request'})
            ttl=180 if flow=='chatgpt_actions' else 300
            code=secrets.token_urlsafe(32);OAUTH_CODES[code]={**client,'redirect_uri':redirect_uri,'code_challenge':challenge,'oauth_flow':flow,'expires_at':time.time()+ttl}
            return self.redirect(redirect_uri+('&' if '?' in redirect_uri else '?')+urlencode({'code':code,**({'state':state} if state else {})}))
        if path=='/health':
            try: h=control('/health');self.sendj(200,{'ok':True,'service':'cloudif-mcp-gateway','control_plane':bool(h.get('ok')),'oauth':True})
            except Exception:self.sendj(503,{'ok':False,'error':'control_plane_unavailable'})
        else:self.sendj(404,{'ok':False,'error':'not_found'})
    def do_POST(self):
        path=urlparse(self.path).path
        if path in {'/cloudiff/mcp/actions/v1/read','/cloudiff/mcp/actions/v1/write'}:
            identity=self._action_identity()
            if not identity:return
            try:
                n=int(self.headers.get('Content-Length','0'));payload=json.loads(self.rfile.read(min(n,1048576)) or b'{}');tool=str(payload.get('tool') or '');args=payload.get('arguments') or {}
                if not isinstance(args,dict) or not tool:raise ValueError('invalid_request')
                readonly=tool in READ_ONLY_TOOLS
                if path.endswith('/read') and not readonly:raise PermissionError('write_tool_not_allowed_on_read_endpoint')
                if path.endswith('/write') and readonly:raise PermissionError('read_tool_not_allowed_on_write_endpoint')
                result=self._action_rpc(identity,tool,args)
                return self.sendj(200,{'ok':True,'project_slug':identity['project_slug'],'tool':tool,'result':result})
            except PermissionError as e:return self.sendj(403,{'ok':False,'error':str(e)})
            except Exception as e:return self.sendj(422,{'ok':False,'error':str(e)})
        if path in {'/token','/oauth/token','/cloudiff/mcp/oauth/token'}:
            n=int(self.headers.get('Content-Length','0'));form=parse_qs(self.rfile.read(min(n,65536)).decode());client_id=(form.get('client_id') or [''])[0];secret=(form.get('client_secret') or [''])[0]
            basic=self.headers.get('Authorization','')
            if basic.startswith('Basic '):
                try:client_id,secret=base64.b64decode(basic[6:]).decode().split(':',1)
                except Exception:return self.sendj(401,{'error':'invalid_client'})
            grant=(form.get('grant_type') or [''])[0]
            if grant=='authorization_code':
                code=(form.get('code') or [''])[0];row=OAUTH_CODES.pop(code,None);redirect=(form.get('redirect_uri') or [''])[0]
                if not row or row['client_id']!=client_id or row['redirect_uri']!=redirect:return self.sendj(400,{'error':'invalid_grant'})
                flow=row.get('oauth_flow') or 'pkce'
                if flow=='pkce' and not _pkce_ok((form.get('code_verifier') or [''])[0],row.get('code_challenge')):return self.sendj(400,{'error':'invalid_grant'})
                if flow=='chatgpt_actions' and _callback_mode(redirect)!='chatgpt_actions':return self.sendj(400,{'error':'invalid_grant'})
                client=_validate_client_secret(client_id,secret) if secret else (row if row.get('public_client') else None)
            elif grant=='refresh_token':
                ref=(form.get('refresh_token') or [''])[0];saved=OAUTH_REFRESH.pop(ref,None)
                client=(_validate_client_secret(client_id,secret) if secret else saved) if saved and saved.get('client_id')==client_id else None
            else:return self.sendj(400,{'error':'unsupported_grant_type'})
            return self.sendj(200,_oauth_token(client)) if client else self.sendj(401,{'error':'invalid_client'})
        if path in {'/revoke','/oauth/revoke','/cloudiff/mcp/oauth/revoke'}:
            n=int(self.headers.get('Content-Length','0'));form=parse_qs(self.rfile.read(min(n,65536)).decode());token=(form.get('token') or [''])[0]
            OAUTH_ACCESS.pop(token,None);OAUTH_REFRESH.pop(token,None);return self.sendj(200,{'ok':True})
        if path!='/mcp':self.sendj(404,{'ok':False,'error':'not_found'});return
        if not self.auth():self.sendj(401,{'ok':False,'error':'unauthorized'});return
        try:
            n=int(self.headers.get('Content-Length','0')); raw=self.rfile.read(min(n,1048576)); req=json.loads(raw or b'{}')
            rid=req.get('id'); method=req.get('method'); params=req.get('params') or {}
            raw_args=params.get('arguments') or {};tool=params.get('name') if method=='tools/call' else method
            args,input_wrappers=_unwrap_tool_arguments(raw_args)
            validate_tool_arguments(tool,args)
            auth_args=args
            slug=str(auth_args.get('slug') or auth_args.get('project_slug') or '')
            if method=='resources/read':
                resource_uri=str(params.get('uri') or '')
                if resource_uri.startswith('cloudiff://guide/project/'):slug=resource_uri.rsplit('/',1)[-1].strip()
            elif method=='prompts/get':
                slug=str((params.get('arguments') or {}).get('slug') or '')
            scope=SCOPE_BY_TOOL.get(tool,'project:read')
            trace_id=self.headers.get('X-CloudIF-Trace-Id') or uuid.uuid4().hex
            authz=self.authorize_client(scope,slug)
            client_id=self.headers.get('X-CloudIF-Client','').strip() or 'internal'
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
                if name=='project.list': data=control('/v1/projects');allowed=set(authz.get('project_slugs') or []);content=[x for x in data.get('projects',[]) if not allowed or x.get('slug') in allowed]
                elif name in {'project.get','project.connectors','project.configuration.get'}:
                    if set(args)!={'slug'}:raise ValueError('O campo slug é obrigatório. Exemplo: {"slug":"meu-projeto"}')
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('O campo slug é obrigatório. Exemplo: {"slug":"meu-projeto"}')
                    data=control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if name=='project.get':content=data.get('project')
                    elif name=='project.connectors':content={'connectors':data.get('connectors',[]),'acl':data.get('acl',[])}
                    else:
                        code,configured=project_config_call('GET','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration')
                        if code not in {200,404}:raise ValueError('Falha ao consultar a configuração efetiva do projeto.')
                        content=configured
                elif name in {'project.observability.get','project.observability.alerts'}:
                    slug=str(args.get('slug') or '').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    path='/v1/alerts' if name.endswith('.alerts') else '/v1/snapshot';code,data=project_observability_call(path,slug)
                    if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'observability_unavailable'))
                    if data.get('effectsExecuted') is not False or data.get('secretValuesIncluded') is not False or data.get('secretReferencesIncluded') is not False:raise ValueError('observability_contract_invalid')
                    content=data
                elif name in {'project.configuration.status','project.configuration.drift','project.configuration.reconcile.plan'}:
                    slug=str(args.get('slug') or '').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if name in {'project.configuration.status','project.configuration.drift'}:
                        path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/runtime-state';environment=str(args.get('environment') or '')
                        if environment:path+='?'+urllib.parse.urlencode({'environment':environment})
                        code,data=runtime_reconciler_call('GET',path)
                        if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'runtime_reconciler_unavailable'))
                        states=data.get('states') or []
                        if name=='project.configuration.drift':states=[item for item in states if item.get('status')!='synchronized']
                        content={'ok':True,'projectSlug':slug,'environment':environment or None,'states':states,'count':len(states),'driftOnly':name.endswith('.drift'),'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}
                    else:
                        payload={'environment':str(args.get('environment') or ''),'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':supabase_actor_user(authz) or client_id}
                        code,data=runtime_reconciler_call('POST','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/reconcile-plan',payload)
                        if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'runtime_reconcile_plan_failed'))
                        if data.get('effectsExecuted') is not False or data.get('secretValuesIncluded') is not False or data.get('secretReferencesIncluded') is not False:raise ValueError('runtime_reconcile_contract_invalid')
                        content=data
                elif name in SECRET_READ_PLAN_TOOLS:
                    content=secret_mcp_read_or_plan(name,args,authz,client_id,trace_id)
                elif name in SECRET_APPROVAL_TOOLS:
                    content=secret_mcp_request_approval(name,args,authz,client_id,trace_id)
                elif name in SECRET_EXECUTE_TOOLS:
                    content=secret_mcp_execute(name,args,authz,client_id,trace_id)
                elif name in {'project.environment.list','project.environment.get','project.environment.validate','project.environment.change.plan','project.environment.promote.plan','project.environment.history','project.environment.import.plan','project.environment.export'}:
                    args,input_normalization=_unwrap_tool_arguments(args)
                    slug=str(args.get('slug') or '').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if not slug:raise ValueError('O campo slug é obrigatório.')
                    if name=='project.environment.list':
                        allowed={'slug','environment','service','include_public_values'}
                        if not set(args).issubset(allowed):raise ValueError('Campos permitidos: slug, environment, service e include_public_values.')
                        query={}
                        if args.get('environment'):query['environment']=str(args['environment'])
                        if args.get('service'):query['service']=str(args['service'])
                        if args.get('include_public_values'):query['includeValues']='true'
                        code,data=project_environment_call('GET',slug,query=query)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or 'Falha ao listar variáveis.'))
                        data['input_normalization']={'wrappersRemoved':input_normalization};content=data
                    elif name=='project.environment.get':
                        required={'slug','environment','name'};allowed=required|{'service','include_public_value'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, environment e name são obrigatórios.')
                        query={'environment':str(args['environment'])}
                        if args.get('service'):query['service']=str(args['service'])
                        if args.get('include_public_value'):query['includeValues']='true'
                        code,data=project_environment_call('GET',slug,query=query)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or 'Falha ao consultar variável.'))
                        target=next((item for item in data.get('entries') or [] if item.get('name')==str(args['name']).strip().upper() and item.get('service','')==str(args.get('service') or '')),None)
                        if not target:raise ValueError('Variável não encontrada no escopo informado.')
                        content={'ok':True,'projectSlug':slug,'entry':target,'revision':data.get('revision'),'environmentDigest':data.get('environmentDigest'),'secretValuesIncluded':False}
                    elif name=='project.environment.history':
                        if not set(args).issubset({'slug','limit'}):raise ValueError('Campos permitidos: slug e limit.')
                        code,data=project_environment_call('GET',slug,'/history',query={'limit':int(args.get('limit') or 100)})
                        if code!=200 or not data.get('ok'):raise ValueError('Falha ao consultar histórico de ambiente.')
                        content=data
                    elif name=='project.environment.export':
                        required={'slug','environment'};allowed=required|{'service'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug e environment são obrigatórios.')
                        query={'environment':str(args['environment'])}
                        if args.get('service'):query['service']=str(args['service'])
                        code,data=project_environment_call('GET',slug,'/export',query=query)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or 'Falha ao exportar metadados.'))
                        if data.get('valuesIncluded') is not False or data.get('secretValuesIncluded') is not False or data.get('secretReferencesIncluded') is not False:raise ValueError('environment_export_contract_invalid')
                        content=data
                    elif name=='project.environment.import.plan':
                        required={'slug','environment','content','expected_revision'};allowed=required|{'service','secret_names','ttl_seconds'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, environment, content e expected_revision são obrigatórios.')
                        payload={'environment':args['environment'],'service':str(args.get('service') or ''),'content':args['content'],'secretNames':args.get('secret_names') or [],'expectedRevision':int(args['expected_revision']),'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':supabase_actor_user(authz) or client_id}
                        code,data=project_environment_call('POST',slug,'/import/plan',payload)
                        payload['content']='';payload.pop('content',None)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'Plano de importação falhou.'))
                        if data.get('secretValuesIncluded') is not False or data.get('secretValuesImported') is not False or data.get('contentStored') is not False:raise ValueError('environment_import_contract_invalid')
                        content=data
                    elif name=='project.environment.validate':
                        required={'slug','environment','changes'}
                        if set(args)!=required:raise ValueError('slug, environment e changes são obrigatórios.')
                        payload={'environment':args['environment'],'changes':args['changes'],'actor':supabase_actor_user(authz) or client_id}
                        code,data=project_environment_call('POST',slug,'/validate',payload)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'Validação de ambiente falhou.'))
                        content=data
                    elif name=='project.environment.change.plan':
                        required={'slug','environment','changes','expected_revision'};allowed=required|{'ttl_seconds'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, environment, changes e expected_revision são obrigatórios.')
                        payload={'environment':args['environment'],'changes':args['changes'],'expectedRevision':int(args['expected_revision']),'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':supabase_actor_user(authz) or client_id}
                        code,data=project_environment_call('POST',slug,'/change/plan',payload)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'Plano de ambiente falhou.'))
                        content=data
                    else:
                        required={'slug','source_environment','target_environment','expected_revision'};allowed=required|{'service','ttl_seconds'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, source_environment, target_environment e expected_revision são obrigatórios.')
                        payload={'sourceEnvironment':args['source_environment'],'targetEnvironment':args['target_environment'],'service':str(args.get('service') or ''),'expectedRevision':int(args['expected_revision']),'ttlSeconds':int(args.get('ttl_seconds') or 900),'actor':supabase_actor_user(authz) or client_id}
                        code,data=project_environment_call('POST',slug,'/promote/plan',payload)
                        if code!=200 or not data.get('ok'):raise ValueError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'Plano de promoção falhou.'))
                        content=data
                elif name in {'approval.request-environment-change','approval.request-environment-promotion'}:
                    args,_wrappers=_unwrap_tool_arguments(args);required={'slug','plan_digest','reason'};allowed=required|{'ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, plan_digest e reason são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();plan_digest_value=str(args['plan_digest']).strip().lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if not re.fullmatch(r'[a-f0-9]{64}',plan_digest_value) or not 4<=len(reason)<=500 or not 60<=ttl<=86400:raise ValueError('plan_digest, reason ou ttl_seconds incompatível.')
                    plan=environment_plan_get(slug,plan_digest_value)
                    expected_action='promotion' if name.endswith('promotion') else 'change'
                    if plan.get('action')!=expected_action:raise ValueError('environment_plan_action_mismatch')
                    if plan.get('consumed') or int(plan.get('expiresAt') or 0)<=int(time.time()):raise ValueError('environment_plan_unavailable')
                    created=environment_approval_create(slug,client_id,authz,plan,reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'plan_digest':plan_digest_value,'environment_action':expected_action,'side_effects':False,'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name in {'project.environment.change.execute','project.environment.promote.execute'}:
                    args,_wrappers=_unwrap_tool_arguments(args);required={'slug','plan_digest','approval_id'}
                    if set(args)!=required:raise ValueError('slug, plan_digest e approval_id são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();plan_digest_value=str(args['plan_digest']).strip().lower();approval_id=str(args['approval_id']).strip()
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=environment_plan_get(slug,plan_digest_value)
                    expected_action='promotion' if name=='project.environment.promote.execute' else 'change'
                    if plan.get('action')!=expected_action:raise ValueError('environment_plan_action_mismatch')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    approval_action='project.environment.promotion' if expected_action=='promotion' else 'project.environment.change'
                    reservation_id,execution_id=transaction_ids(approval_action,approval_id,client_id,plan_digest_value)
                    valid_status=bool(approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id))
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')==approval_action and approval.get('requested_by')==client_id and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('environment_plan_digest') or ''),plan_digest_value) and metadata.get('environment_action')==expected_action and int(metadata.get('expected_revision') or 0)==int(plan.get('expectedRevision') or 0) and metadata.get('target_environment')==plan.get('targetEnvironment') and metadata.get('source_environment')==plan.get('sourceEnvironment') and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    path='/promote/apply' if expected_action=='promotion' else '/change/apply'
                    payload={'planDigest':plan_digest_value,'expectedRevision':int(plan['expectedRevision']),'approved':True,'actor':supabase_actor_user(authz) or client_id,'executionId':execution_id}
                    code,data=project_environment_call('POST',slug,path,payload)
                    current=approval_get(approval_id)
                    if code==200 and data.get('ok'):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};data['secretValuesIncluded']=False;content=data
                    else:
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'environment_apply_failed'))
                elif name in {'project.toolchain.get','project.toolchain.validate','project.toolchain.plan','project.toolchain.build.plan','project.toolchain.build.status','project.toolchain.logs.read','project.toolchain.image.list','project.toolchain.image.get','project.toolchain.image.activate.plan'}:
                    args,_wrappers=_unwrap_tool_arguments(args)
                    if name in {'project.toolchain.build.status','project.toolchain.logs.read'}:
                        if set(args)!={'job_id'}:raise ValueError('O campo job_id é obrigatório.')
                        job_id=str(args.get('job_id') or '').strip()
                        if not re.fullmatch(r'toolchain_[a-f0-9]{24}',job_id):raise ValueError('job_id incompatível.')
                        suffix='/logs' if name=='project.toolchain.logs.read' else ''
                        code,data=build_broker_call('GET','/v1/toolchain/jobs/'+urllib.parse.quote(job_id,safe='')+suffix,timeout=90)
                        if code==404:raise ValueError('Job de toolchain não encontrado.')
                        if code!=200 or not data.get('ok'):raise ValueError('Falha ao consultar o job da toolchain.')
                        data['secret_values_included']=False;content=data
                    elif name in {'project.toolchain.image.list','project.toolchain.image.get'}:
                        required={'slug'}|({'image_record_id'} if name.endswith('.get') else set());allowed=required|({'service'} if name.endswith('.list') else set())
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Campos da consulta de imagem incompatíveis.')
                        slug=str(args.get('slug') or '').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                        if name.endswith('.list'):
                            query='';service=str(args.get('service') or '').strip()
                            if service:query='?'+urllib.parse.urlencode({'service':service})
                            path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain/images'+query
                        else:
                            image_record_id=str(args.get('image_record_id') or '').strip()
                            if not re.fullmatch(r'img_[a-f0-9]{24}',image_record_id):raise ValueError('image_record_id incompatível.')
                            path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain/images/'+urllib.parse.quote(image_record_id,safe='')
                        code,data=build_broker_call('GET',path,timeout=90)
                        if code==404:raise ValueError('Imagem de toolchain não encontrada.')
                        if code!=200 or not data.get('ok'):raise ValueError('Falha ao consultar imagens da toolchain.')
                        data['secret_values_included']=False;content=data
                    elif name=='project.toolchain.image.activate.plan':
                        required={'slug','environment','job_id','expected_revision'}
                        if set(args)!=required:raise ValueError('slug, environment, job_id e expected_revision são obrigatórios.')
                        slug=str(args['slug']).strip();environment=str(args['environment']).strip();job_id=str(args['job_id']).strip();expected=int(args['expected_revision'])
                        control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                        content=toolchain_activation_plan(slug,environment,job_id,expected,trace_id)
                    elif name=='project.toolchain.get':
                        required={'slug'};allowed=required|{'ref'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug é obrigatório; ref é opcional.')
                        slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                        code,data=build_broker_call('GET','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain?'+urllib.parse.urlencode({'ref':ref}),timeout=180)
                        if code!=200 or not data.get('ok'):
                            error=data.get('error') or {};error_code=str(error.get('code') if isinstance(error,dict) else error or 'toolchain_query_failed')
                            if error_code in {'configuration_required','toolchain_not_configured'}:
                                toolchain_configuration_revision(slug,0)
                            message=str(error.get('message') if isinstance(error,dict) else '') or 'Falha ao consultar a toolchain.'
                            raise ToolStateError({'code':error_code,'message':message})
                        data['secret_values_included']=False;content=data
                    else:
                        required={'slug'};allowed=required|{'ref','expected_revision'}
                        if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug é obrigatório; ref e expected_revision são opcionais.')
                        slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();expected=int(args.get('expected_revision') or 0)
                        control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                        expected=toolchain_configuration_revision(slug,expected)
                        content=toolchain_broker_plan(slug,ref,expected,trace_id,validate=name=='project.toolchain.validate')
                elif name=='approval.request-toolchain-build':
                    required={'slug','expected_revision','plan_digest','reason'};allowed=required|{'ref','ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, expected_revision, plan_digest e reason são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();expected=int(args['expected_revision']);digest_value=str(args['plan_digest']).strip().lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if expected<1 or not re.fullmatch(r'[a-f0-9]{64}',digest_value) or not 4<=len(reason)<=500 or not 60<=ttl<=86400:raise ValueError('Parâmetros da aprovação da toolchain são incompatíveis.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=toolchain_broker_plan(slug,ref,expected,trace_id,validate=True)
                    if plan.get('blocked') or not plan.get('valid'):raise ValueError('A toolchain está bloqueada pela política ou pelo script.')
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value):raise ValueError('O plano da toolchain mudou.')
                    created=approval_create_toolchain(slug,client_id,authz,'project.toolchain.build',plan,reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'plan_digest':digest_value,'action':'project.toolchain.build','images_created':False,'images_activated':False,'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name=='project.toolchain.build.execute':
                    required={'slug','expected_revision','plan_digest','approval_id'};allowed=required|{'ref'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, expected_revision, plan_digest e approval_id são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();expected=int(args['expected_revision']);digest_value=str(args['plan_digest']).strip().lower();approval_id=str(args['approval_id']).strip()
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=toolchain_broker_plan(slug,ref,expected,trace_id,validate=True)
                    if plan.get('blocked') or not plan.get('valid') or not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value):raise ValueError('toolchain_plan_mismatch_or_blocked')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    reservation_id,execution_id=transaction_ids('project.toolchain.build',approval_id,client_id,digest_value)
                    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
                    expected_services=[{'service':item.get('service'),'toolchainDigest':item.get('toolchainDigest')} for item in plan.get('services') or []]
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='project.toolchain.build' and approval.get('requested_by')==client_id and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('toolchain_plan_digest') or ''),digest_value) and int(metadata.get('config_revision') or 0)==expected and hmac.compare_digest(str(metadata.get('config_digest') or ''),str(plan.get('config_digest') or '')) and hmac.compare_digest(str(metadata.get('requested_toolchain_digest') or ''),str(plan.get('requested_toolchain_digest') or '')) and hmac.compare_digest(str(metadata.get('archive_sha256') or ''),str(plan.get('archive_sha256') or '')) and metadata.get('ref')==ref and metadata.get('services')==expected_services and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,queued=build_broker_call('POST','/v1/toolchain/build',{'project_slug':slug,'ref':ref,'expected_revision':expected,'plan_digest':digest_value,'approved':True,'trace_id':'txn-'+reservation_id},timeout=900)
                    current=approval_get(approval_id)
                    if code in {200,202} and (queued.get('ok') or queued.get('status') in {'queued','running','succeeded'}):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        queued['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};queued['images_activated']=False;queued['containers_changed']=False;content=queued
                    else:
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=queued.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'toolchain_build_queue_failed'))
                elif name=='approval.request-toolchain-activation':
                    required={'slug','environment','job_id','expected_revision','plan_digest','reason'};allowed=required|{'ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Parâmetros da aprovação de ativação estão incompletos.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();environment=str(args['environment']).strip();job_id=str(args['job_id']).strip();expected=int(args['expected_revision']);digest_value=str(args['plan_digest']).strip().lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=toolchain_activation_plan(slug,environment,job_id,expected,trace_id)
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value) or not 4<=len(reason)<=500 or not 60<=ttl<=86400:raise ValueError('O plano de ativação mudou ou a solicitação é inválida.')
                    created=approval_create_toolchain(slug,client_id,authz,'project.toolchain.activation',plan,reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'environment':environment,'plan_digest':digest_value,'action':'project.toolchain.activation','containers_changed':False,'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name=='project.toolchain.image.activate':
                    required={'slug','environment','job_id','expected_revision','plan_digest','approval_id'}
                    if set(args)!=required:raise ValueError('Parâmetros da ativação estão incompletos.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();environment=str(args['environment']).strip();job_id=str(args['job_id']).strip();expected=int(args['expected_revision']);digest_value=str(args['plan_digest']).strip().lower();approval_id=str(args['approval_id']).strip()
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=toolchain_activation_plan(slug,environment,job_id,expected,trace_id)
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value):raise ValueError('activation_plan_digest_mismatch')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    reservation_id,execution_id=transaction_ids('project.toolchain.activation',approval_id,client_id,digest_value)
                    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='project.toolchain.activation' and approval.get('requested_by')==client_id and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('activation_plan_digest') or ''),digest_value) and metadata.get('environment')==environment and metadata.get('job_id')==job_id and int(metadata.get('expected_revision') or 0)==expected and metadata.get('after')==(plan.get('after') or []) and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,result=build_broker_call('POST','/v1/toolchain/activation/apply',{'project_slug':slug,'environment':environment,'job_id':job_id,'expected_revision':expected,'plan_digest':digest_value,'approval_id':approval_id,'approved':True,'actor':supabase_actor_user(authz) or client_id},timeout=180)
                    current=approval_get(approval_id)
                    if code==200 and result.get('ok'):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        result['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};result['containers_changed']=False;content=result
                    else:
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=result.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'toolchain_activation_failed'))
                elif name=='runtime.catalog':
                    if args:raise ValueError('argumentos inválidos')
                    content=runtime_call('/v1/catalog')
                elif name=='runtime.detect':
                    if 'slug' not in args or not set(args).issubset({'slug','ref'}):raise ValueError('argumentos inválidos')
                    slug=str(args['slug']).strip();ref=str(args.get('ref') or 'main').strip();control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    evidence=workspace_validate(slug,ref,trace_id).get('result') or {}
                    safe={k:evidence.get(k) for k in ('technologies','compose','static')};content=runtime_call('/v1/detect',safe);content['project_slug']=slug;content['ref']=ref
                elif name=='build.multiservice.plan':
                    allowed={'slug','ref','environment','expected_revision'}
                    if 'slug' not in args or not set(args).issubset(allowed):raise ValueError('O campo slug é obrigatório. Campos permitidos: slug, ref e expected_revision.')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();expected=int(args.get('expected_revision') or 0)
                    if not slug:raise ValueError('O campo slug é obrigatório.')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('O campo ref deve ser uma referência relativa como main.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if expected<1:
                        code,current=project_config_call('GET','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration')
                        if code!=200 or int(current.get('currentRevision') or 0)<1:raise ValueError('O projeto precisa de cloudiff.yaml ou configuração aprovada antes do build.')
                        expected=int(current['currentRevision'])
                    plan=multiservice_build_plan(slug,ref,expected,trace_id)
                    content=plan
                elif name=='build.multiservice.status':
                    if set(args)!={'job_id'}:raise ValueError('O campo job_id é obrigatório. Exemplo: {"job_id":"build_0123456789abcdef01234567"}')
                    job_id=str(args.get('job_id') or '').strip()
                    if not re.fullmatch(r'build_[a-f0-9]{24}',job_id):raise ValueError('O campo job_id é incompatível.')
                    code,status=build_broker_call('GET','/v1/multiservice/jobs/'+urllib.parse.quote(job_id,safe=''),timeout=60)
                    if code==404:raise ValueError('Build não encontrado.')
                    if code!=200 or not status.get('ok'):raise ValueError('Falha ao consultar o build.')
                    content=status
                elif name=='approval.request-multiservice-build':
                    required={'slug','expected_revision','plan_digest','reason'};allowed=required|{'ref','ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Os campos slug, expected_revision, plan_digest e reason são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();expected=int(args.get('expected_revision') or 0);digest_value=str(args.get('plan_digest') or '').strip().lower();reason=str(args.get('reason') or '').strip();ttl=int(args.get('ttl_seconds') or 900)
                    if not slug or expected<1 or not re.fullmatch(r'[a-f0-9]{64}',digest_value):raise ValueError('slug, expected_revision ou plan_digest incompatível.')
                    if not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('reason deve ter 4 a 500 caracteres e ttl_seconds deve estar entre 60 e 86400.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=multiservice_build_plan(slug,ref,expected,trace_id)
                    if plan.get('blocked'):raise ValueError('O plano contém runtimes bloqueados pela política de segurança.')
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value):raise ValueError('O plano mudou. Gere um novo plano antes de solicitar aprovação.')
                    created=approval_create_multiservice_build(slug,client_id,authz,plan,reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'plan_digest':digest_value,'config_revision':expected,'archive_sha256':plan.get('archive_sha256'),'action':'build.multiservice','side_effects':{'build_queued':False,'images_created':False},'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name=='build.multiservice.execute':
                    required={'slug','expected_revision','plan_digest','approval_id'};allowed=required|{'ref'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Os campos slug, expected_revision, plan_digest e approval_id são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();expected=int(args.get('expected_revision') or 0);digest_value=str(args.get('plan_digest') or '').strip().lower();approval_id=str(args.get('approval_id') or '').strip()
                    if not slug or expected<1 or not re.fullmatch(r'[a-f0-9]{64}',digest_value) or not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):raise ValueError('Parâmetros do build incompatíveis.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=multiservice_build_plan(slug,ref,expected,trace_id)
                    if plan.get('blocked'):raise ValueError('O plano contém runtimes bloqueados pela política de segurança.')
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest_value):raise ValueError('plan_digest_mismatch')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    reservation_id,execution_id=transaction_ids('build.multiservice',approval_id,client_id,digest_value)
                    valid_status=bool(approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id))
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='build.multiservice' and approval.get('requested_by')==client_id and int(metadata.get('config_revision') or 0)==expected and hmac.compare_digest(str(metadata.get('plan_digest') or ''),digest_value) and hmac.compare_digest(str(metadata.get('config_digest') or ''),str(plan.get('config_digest') or '')) and hmac.compare_digest(str(metadata.get('toolchain_digest') or ''),str(plan.get('toolchain_digest') or '')) and hmac.compare_digest(str(metadata.get('archive_sha256') or ''),str(plan.get('archive_sha256') or '')) and metadata.get('content_stored') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,queued=build_broker_call('POST','/v1/multiservice/execute',{'project_slug':slug,'ref':ref,'expected_revision':expected,'plan_digest':digest_value,'approved':True,'trace_id':'txn-'+reservation_id},timeout=180)
                    current=approval_get(approval_id)
                    if code in {200,202} and (queued.get('ok') or queued.get('status') in {'queued','running','succeeded'}):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        queued['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'}
                        queued['plan_validated']=True;queued['configuration_revision']=expected;queued['archive_sha256']=plan.get('archive_sha256');content=queued
                    else:
                        if current and current.get('status')=='reserved' and code in {400,403,404,409,422}:approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=queued.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'multiservice_build_queue_failed'))

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
                elif name=='preview.multiservice.plan':
                    if 'build_job_id' not in args or not set(args).issubset({'build_job_id','routes','ttl_seconds'}):raise ValueError('O campo build_job_id é obrigatório. Campos permitidos: build_job_id, routes e ttl_seconds.')
                    build_job_id=str(args.get('build_job_id') or '').strip();ttl=int(args.get('ttl_seconds') or 1800);routes=args.get('routes')
                    if not re.fullmatch(r'build_[a-f0-9]{24}',build_job_id):raise ValueError('build_job_id incompatível.')
                    content=multiservice_preview_plan(build_job_id,routes,ttl,authz)
                elif name=='approval.request-multiservice-preview':
                    required={'build_job_id','preview_plan_digest','reason'};allowed=required|{'routes','ttl_seconds','approval_ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('build_job_id, preview_plan_digest e reason são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    job_id=str(args['build_job_id']);digest=str(args['preview_plan_digest']).lower();ttl=int(args.get('ttl_seconds') or 1800);approval_ttl=int(args.get('approval_ttl_seconds') or 900);reason=str(args['reason']).strip();routes=args.get('routes')
                    if not re.fullmatch(r'build_[a-f0-9]{24}',job_id) or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('build_job_id ou preview_plan_digest incompatível.')
                    if not 4<=len(reason)<=500 or not 60<=approval_ttl<=86400:raise ValueError('reason ou approval_ttl_seconds incompatível.')
                    plan=multiservice_preview_plan(job_id,routes,ttl,authz);slug=str(plan.get('project_slug') or '')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if not hmac.compare_digest(str(plan.get('preview_plan_digest') or ''),digest):raise ValueError('O plano do preview mudou.')
                    created=approval_create_multiservice_preview(slug,client_id,authz,plan,reason,approval_ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'preview_plan_digest':digest,'build_job_id':job_id,'side_effects':False,'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name=='preview.multiservice.create':
                    required={'build_job_id','preview_plan_digest','approval_id'};allowed=required|{'routes','ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('build_job_id, preview_plan_digest e approval_id são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    build_job_id=str(args.get('build_job_id') or '').strip();digest=str(args['preview_plan_digest']).lower();approval_id=str(args['approval_id']);ttl=int(args.get('ttl_seconds') or 1800);routes=args.get('routes')
                    if not re.fullmatch(r'build_[a-f0-9]{24}',build_job_id):raise ValueError('build_job_id incompatível.')
                    plan=multiservice_preview_plan(build_job_id,routes,ttl,authz);slug=str(plan.get('project_slug') or '')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if not hmac.compare_digest(str(plan.get('preview_plan_digest') or ''),digest):raise ValueError('preview_plan_digest_mismatch')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    reservation_id,execution_id=transaction_ids('preview.multiservice',approval_id,client_id,digest)
                    valid_status=bool(approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id))
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='preview.multiservice' and approval.get('requested_by')==client_id and hmac.compare_digest(str(metadata.get('preview_plan_digest') or ''),digest) and hmac.compare_digest(str(metadata.get('build_plan_digest') or ''),str(plan.get('build_plan_digest') or '')) and hmac.compare_digest(str(metadata.get('config_digest') or ''),str(plan.get('config_digest') or '')) and hmac.compare_digest(str(metadata.get('archive_sha256') or ''),str(plan.get('archive_sha256') or '')) and int(metadata.get('preview_ttl_seconds') or 0)==ttl and metadata.get('content_stored') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    payload={'build_job_id':build_job_id,'preview_plan_digest':digest,'ttl_seconds':ttl,'actor_user':supabase_actor_user(authz),'actor_groups':list(authz.get('authorized_groups') or [])}
                    if routes is not None:payload['routes']=routes
                    code,created=multiservice_preview_call('POST','/v1/previews',payload,authz,240)
                    current=approval_get(approval_id)
                    if code in {200,201} and created.get('ok'):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        created['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};content=created
                    else:
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=created.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'preview_create_failed'))
                elif name=='preview.multiservice.status':
                    if set(args)!={'preview_id'}:raise ValueError('O campo preview_id é obrigatório.')
                    preview_id=str(args.get('preview_id') or '')
                    if not re.fullmatch(r'pv_[a-f0-9]{24}',preview_id):raise ValueError('preview_id incompatível.')
                    code,data=multiservice_preview_call('GET','/v1/previews/'+urllib.parse.quote(preview_id,safe=''),None,authz,60)
                    if code!=200 or not data.get('ok'):raise ValueError('Preview não encontrado ou não autorizado.')
                    content=data
                elif name=='preview.multiservice.delete':
                    if set(args)!={'preview_id'}:raise ValueError('O campo preview_id é obrigatório.')
                    preview_id=str(args.get('preview_id') or '')
                    if not re.fullmatch(r'pv_[a-f0-9]{24}',preview_id):raise ValueError('preview_id incompatível.')
                    code,data=multiservice_preview_call('DELETE','/v1/previews/'+urllib.parse.quote(preview_id,safe=''),None,authz,90)
                    if code not in {200,404} or not data.get('ok'):raise ValueError('O preview não pôde ser removido.')
                    content=data
                elif name=='deployment.multiservice.plan':
                    required={'slug','build_job_id','environment'};allowed=required|{'routes'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Os campos slug, build_job_id e environment são obrigatórios.')
                    slug=str(args['slug']).strip();build_job_id=str(args.get('build_job_id') or '').strip();environment=str(args['environment']).strip()
                    if not re.fullmatch(r'build_[a-f0-9]{24}',build_job_id):raise ValueError('build_job_id incompatível.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    payload={'project_slug':slug,'build_job_id':build_job_id,'environment':environment,'trace_id':trace_id}
                    if args.get('routes') is not None:payload['routes']=args['routes']
                    code,data=deployment_multiservice_plan_call(payload)
                    if code!=200 or not data.get('ok'):
                        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'deployment_plan_failed'))
                    content=data
                elif name=='approval.request-multiservice-deployment':
                    required={'slug','build_job_id','environment','deployment_plan_digest','reason'};allowed=required|{'routes','ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, build_job_id, environment, deployment_plan_digest e reason são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();build_job_id=str(args.get('build_job_id') or '').strip();environment=str(args['environment']).strip();digest=str(args['deployment_plan_digest']).lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if not re.fullmatch(r'build_[a-f0-9]{24}',build_job_id):raise ValueError('build_job_id incompatível.')
                    if not re.fullmatch(r'[a-f0-9]{64}',digest) or not 4<=len(reason)<=500 or not 60<=ttl<=86400:raise ValueError('digest, reason ou ttl_seconds incompatível.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    payload={'project_slug':slug,'build_job_id':build_job_id,'environment':environment,'trace_id':trace_id}
                    if args.get('routes') is not None:payload['routes']=args['routes']
                    code,plan=deployment_multiservice_plan_call(payload)
                    if code!=200 or not plan.get('ok'):raise ValueError('deployment_plan_failed')
                    if not hmac.compare_digest(str(plan.get('deployment_plan_digest') or ''),digest):raise ValueError('O plano do deploy mudou.')
                    if not plan.get('execution_allowed'):raise ValueError('Deploy bloqueado: '+', '.join(plan.get('blockers') or []))
                    created=approval_create_multiservice_deployment(slug,client_id,authz,plan,reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'environment':environment,'deployment_plan_digest':digest,'side_effects':False,'content_stored_in_approval':False,'secret_values_in_metadata':False}
                elif name=='deployment.multiservice.execute':
                    required={'slug','build_job_id','environment','deployment_plan_digest','approval_id'};allowed=required|{'routes'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('slug, build_job_id, environment, deployment_plan_digest e approval_id são obrigatórios.')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();build_job_id=str(args.get('build_job_id') or '').strip();environment=str(args['environment']).strip();digest=str(args['deployment_plan_digest']).lower();approval_id=str(args['approval_id'])
                    if not re.fullmatch(r'build_[a-f0-9]{24}',build_job_id):raise ValueError('build_job_id incompatível.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    payload={'project_slug':slug,'build_job_id':build_job_id,'environment':environment,'trace_id':trace_id}
                    if args.get('routes') is not None:payload['routes']=args['routes']
                    code,plan=deployment_multiservice_plan_call(payload)
                    if code!=200 or not plan.get('ok') or not plan.get('execution_allowed'):raise ValueError('deployment_plan_blocked')
                    if not hmac.compare_digest(str(plan.get('deployment_plan_digest') or ''),digest):raise ValueError('deployment_plan_digest_mismatch')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    operation=plan.get('operation') or {};reconciliation=plan.get('reconciliation') or {}
                    reservation_id,execution_id=transaction_ids('deployment.multiservice',approval_id,client_id,digest)
                    valid_status=bool(approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id))
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='deployment.multiservice' and approval.get('requested_by')==client_id and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('deployment_plan_digest') or ''),digest) and metadata.get('environment')==environment and metadata.get('build_job_id')==build_job_id and operation.get('build_job_id')==build_job_id and hmac.compare_digest(str(metadata.get('build_plan_digest') or ''),str(operation.get('build_plan_digest') or '')) and int(metadata.get('config_revision') or 0)==int(operation.get('config_revision') or 0) and hmac.compare_digest(str(metadata.get('config_digest') or ''),str(operation.get('config_digest') or '')) and hmac.compare_digest(str(metadata.get('toolchain_digest') or ''),str(operation.get('toolchain_digest') or '')) and hmac.compare_digest(str(metadata.get('archive_sha256') or ''),str(operation.get('archive_sha256') or '')) and hmac.compare_digest(str(metadata.get('variables_digest') or ''),str(plan.get('variables_digest') or '')) and metadata.get('routes')==(operation.get('routes') or []) and int(metadata.get('membership_revision') or 0)==int(reconciliation.get('membershipRevision') or 0) and hmac.compare_digest(str(metadata.get('acl_digest') or ''),str(reconciliation.get('aclDigest') or '')) and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    effect={**payload,'deployment_plan_digest':digest,'execution_id':execution_id}
                    code,result=deployment_multiservice_execute_call(effect)
                    current=approval_get(approval_id)
                    if code in {200,201} and result.get('ok'):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        result['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'};result['variable_values_returned']=False;content=result
                    else:
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        error=result.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'deployment_execute_failed'))
                elif name=='deployment.multiservice.status':
                    if set(args)!={'deployment_id'}:raise ValueError('O campo deployment_id é obrigatório.')
                    deployment_id=str(args.get('deployment_id') or '')
                    if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise ValueError('deployment_id incompatível.')
                    code,data=deployment_multiservice_status_call(deployment_id)
                    if code!=200 or not data.get('ok'):raise ValueError('Deploy não encontrado.')
                    data.pop('variables',None);data['variable_values_returned']=False;content=data
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
                    if created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'preview_plan_digest':digest,'artifact_image_id':art.get('artifact_image_id'),'immutable_source_digest':art.get('immutable_source_digest'),'public_url_ready':False,'two_approvers_required':False}
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
                elif name=='project.technologies.detect':
                    if not set(args).issubset({'slug','ref'}) or 'slug' not in args:raise ValueError('O campo slug é obrigatório. Exemplo: {"slug":"meu-projeto","ref":"main"}')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip()
                    if not slug:raise ValueError('O campo slug é obrigatório. Exemplo: {"slug":"meu-projeto","ref":"main"}')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('O campo ref é incompatível. Use uma referência como main ou feature/minha-branch.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    data=workspace_detect_multiservice(slug,ref,trace_id)
                    if not data.get('ok'):raise ValueError(str(data.get('error') or 'Falha na detecção multitecnologia.'))
                    content=data
                elif name=='project.manifest.validate':
                    if not set(args).issubset({'slug','manifest','overrides'}) or not {'slug','manifest'}.issubset(args):raise ValueError('Os campos slug e manifest são obrigatórios. Exemplo: {"slug":"meu-projeto","manifest":{"version":1,"runtime":"static"}}')
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('O campo slug é obrigatório.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,validated=project_config_call('POST','/v1/manifest/validate',{'manifest':args.get('manifest'),'overrides':args.get('overrides') or {}})
                    if code not in {200,422}:raise ValueError('Falha ao validar o manifesto do projeto.')
                    content=validated
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
                    if created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'promotion_digest':digest,'side_effects':{'release':False,'backup':False,'migrations':False,'komodo':False}}
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
                    if created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'rollback_digest':digest,'side_effects':{'backup':False,'komodo':False,'rollback':False}}
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
                elif name in SUPABASE_READ_TOOL_ACTIONS:
                    if 'slug' not in args:raise ValueError('slug obrigatório')
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    payload={k:v for k,v in args.items() if k!='slug'}
                    code,data=supabase_broker_call('/v1/read',slug,authz,payload=payload,action=SUPABASE_READ_TOOL_ACTIONS[name],timeout=75)
                    if code!=200 or not data.get('ok'):raise ValueError(str(data.get('error') or 'supabase_read_failed'))
                    content=data
                elif name in SUPABASE_PLAN_TOOL_OPERATIONS:
                    if 'slug' not in args:raise ValueError('slug obrigatório')
                    slug=str(args.get('slug') or '').strip()
                    if not slug:raise ValueError('slug obrigatório')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    payload={k:v for k,v in args.items() if k!='slug'}
                    content=supabase_plan(slug,authz,SUPABASE_PLAN_TOOL_OPERATIONS[name],payload)
                elif name=='approval.request-supabase-operation':
                    required={'slug','operation','payload','plan_digest','reason'}
                    if not required.issubset(args) or not set(args).issubset(required|{'ttl_seconds'}):raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();operation=str(args['operation']).strip();payload=args['payload'];digest=str(args['plan_digest']).strip().lower();reason=str(args['reason']).strip();ttl=int(args.get('ttl_seconds') or 900)
                    if not isinstance(payload,dict) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) or not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=supabase_plan(slug,authz,operation,payload)
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest):raise ValueError('plan_digest_mismatch')
                    created=supabase_approval_create(slug,client_id,authz,operation,digest,plan.get('summary') or {},reason,ttl,trace_id)
                    if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                    content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'operation':operation,'plan_digest':digest,'summary':plan.get('summary') or {},'secret_values_exposed':False,'side_effects':False}
                elif name=='supabase.operation.execute':
                    if set(args)!={'slug','operation','payload','plan_digest','approval_id'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args['slug']).strip();operation=str(args['operation']).strip();payload=args['payload'];digest=str(args['plan_digest']).strip().lower();approval_id=str(args['approval_id']).strip()
                    if not isinstance(payload,dict) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) or not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    plan=supabase_plan(slug,authz,operation,payload)
                    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),digest):raise ValueError('plan_digest_mismatch')
                    row=approval_get(approval_id)
                    try:meta=json.loads(row.get('metadata_json') or '{}') if row else {}
                    except Exception:meta={}
                    action=supabase_operation_action(operation);actor_user=supabase_actor_user(authz)
                    reservation_id,execution_id=transaction_ids(action,approval_id,client_id,digest)
                    valid_status=bool(row and (row.get('status')=='approved' or (row.get('status') in {'reserved','consumed'} and row.get('reservation_id')==reservation_id)))
                    valid=bool(row and valid_status and row.get('project_slug')==slug and row.get('action')==action and row.get('requested_by')==client_id and row.get('approved_by') and meta.get('supabase_operation')==operation and hmac.compare_digest(str(meta.get('supabase_plan_digest') or ''),digest) and str(meta.get('actor_user') or '')==actor_user)
                    if not valid:raise ValueError('approval_mismatch')
                    if row.get('status')=='approved':
                        rc,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if rc!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    code,data=supabase_broker_call('/v1/effect',slug,authz,payload=payload,operation=operation,plan_digest=digest,execution_id=execution_id,timeout=240)
                    current=approval_get(approval_id)
                    if code==200 and data.get('ok'):
                        if current and current.get('status')!='consumed':
                            fc,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if fc!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        data['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'}
                        content=data
                    else:
                        if current and current.get('status')=='reserved' and code in {400,403,404}:
                            approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        raise ValueError(str(data.get('error') or 'supabase_effect_failed'))
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
                        if created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'deployment_digest':digest,'side_effects':{'release':False,'backup':False,'migrations':False,'komodo':False}}
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
                elif name=='approval.cancel':
                    if set(args)!={'slug','approval_id','reason'}:raise ValueError('argumentos inválidos')
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=str(args.get('slug') or '').strip();approval_id=str(args.get('approval_id') or '').strip();reason=str(args.get('reason') or '').strip()
                    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',slug) or not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id) or not (4<=len(reason)<=500):raise ValueError('argumentos inválidos')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    row=approval_get(approval_id)
                    if not row or row.get('project_slug')!=slug or row.get('requested_by')!=client_id:raise ValueError('approval_not_found')
                    code,result=approval_transition(approval_id,'cancel',{'requested_by':client_id,'cancellation_reason':reason})
                    if code!=200 or result.get('status')!='cancelled':raise ValueError(str(result.get('error') or 'approval_cancel_failed'))
                    content={'ok':True,'approval_id':approval_id,'project_slug':slug,'status':'cancelled','cancelled':True,'idempotent':bool(result.get('idempotent')),'cancelled_at':result.get('cancelled_at'),'side_effects':{'forgejo':False,'runtime':False,'database':False}}
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
                        if created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'merge_digest':digest,'side_effects':{'forgejo':False,'main_modified':False}}
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
                elif name=='workspace.normalize.plan':
                    allowed={'slug','ref','title','description','ttl_seconds'}
                    if 'slug' not in args or not set(args).issubset(allowed):raise ValueError('O campo slug é obrigatório. Campos permitidos: slug, ref, title, description e ttl_seconds.')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();title=str(args.get('title') or 'Adicionar manifesto CloudIFF').strip();description=str(args.get('description') or 'Adiciona a configuração versionada detectada pela plataforma.');ttl=int(args.get('ttl_seconds') or 3600)
                    if not slug:raise ValueError('O campo slug é obrigatório.')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('O campo ref deve ser uma referência relativa como main.')
                    if not (4<=len(title)<=160) or len(description)>4000 or not (300<=ttl<=86400):raise ValueError('title, description ou ttl_seconds incompatível.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=workspace_broker_post('/v1/normalize-plan',{'project_slug':slug,'ref':ref,'trace_id':trace_id,'title':title,'description':description,'ttl_seconds':ttl},timeout=150)
                    if code not in {200,422} or not data.get('ok'):
                        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'normalization_plan_failed'))
                    content=data.get('result') or data
                elif name=='workspace.artifact.import':
                    required={'slug','file_id','filename','expected_size','expected_sha256'};allowed=required|{'ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug, file_id, filename, expected_size e expected_sha256.')
                    slug=str(args.get('slug') or '').strip();file_id=str(args.get('file_id') or '').strip();filename=str(args.get('filename') or '').strip();size=int(args.get('expected_size'));digest=str(args.get('expected_sha256') or '').strip().lower();ttl=int(args.get('ttl_seconds') or 3600)
                    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',slug) or not re.fullmatch(r'[A-Za-z0-9_-]{6,192}',file_id) or not filename or len(filename)>240 or not (0<=size<=67108864) or not re.fullmatch(r'[a-f0-9]{64}',digest) or not (300<=ttl<=86400):raise ValueError('Metadados da importação são inválidos.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    raw=session_file_resolve(file_id,size,digest,trace_id)
                    content=workspace_artifact_import_bytes(slug,filename,raw,digest,ttl,trace_id);content['file_id']=file_id
                elif name in {'workspace.artifact.upload.start','workspace.artifact.upload.chunk','workspace.artifact.upload.batch','workspace.artifact.upload.ticket','workspace.artifact.upload.complete'}:
                    slug=str(args.get('slug') or '').strip()
                    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',slug):raise ValueError('O campo slug é obrigatório e deve ser válido.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    if name=='workspace.artifact.upload.start':
                        allowed={'slug','filename','expected_size','expected_sha256','ttl_seconds'}
                        if not {'slug','filename','expected_size','expected_sha256'}.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug, filename, expected_size e expected_sha256.')
                        filename=str(args.get('filename') or '').strip();digest=str(args.get('expected_sha256') or '').strip().lower();size=int(args.get('expected_size'));ttl=int(args.get('ttl_seconds') or 3600)
                        if not filename or len(filename)>240 or not re.fullmatch(r'[a-f0-9]{64}',digest) or not (0<=size<=67108864) or not (300<=ttl<=86400):raise ValueError('Metadados do artefato inválidos.')
                        payload={'project_slug':slug,'trace_id':trace_id,'filename':filename,'expected_size':size,'expected_sha256':digest,'ttl_seconds':ttl};endpoint='/v1/artifact/start'
                    elif name=='workspace.artifact.upload.chunk':
                        allowed={'slug','artifact_id','chunk_index','content_base64','chunk_sha256'}
                        if not {'slug','artifact_id','chunk_index','content_base64','chunk_sha256'}.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug, artifact_id, chunk_index, content_base64 e chunk_sha256.')
                        artifact_id=str(args.get('artifact_id') or '').strip();index=int(args.get('chunk_index'));encoded=str(args.get('content_base64') or '');chunk_sha=str(args.get('chunk_sha256') or '').strip().lower()
                        if not re.fullmatch(r'art_[a-f0-9]{24}',artifact_id) or index<0 or len(encoded)>262144 or not re.fullmatch(r'[a-f0-9]{64}',chunk_sha):raise ValueError('Metadados do chunk inválidos.')
                        payload={'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id,'chunk_index':index,'content_base64':encoded,'chunk_sha256':chunk_sha};endpoint='/v1/artifact/chunk'
                    elif name=='workspace.artifact.upload.batch':
                        allowed={'slug','artifact_id','chunks'}
                        if not {'slug','artifact_id','chunks'}.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug, artifact_id e chunks.')
                        artifact_id=str(args.get('artifact_id') or '').strip();chunks=args.get('chunks')
                        if not re.fullmatch(r'art_[a-f0-9]{24}',artifact_id) or not isinstance(chunks,list) or not (1<=len(chunks)<=16):raise ValueError('Metadados do batch inválidos.')
                        for item in chunks:
                            if not isinstance(item,dict) or set(item)!={'chunk_index','content_base64','chunk_sha256'} or int(item.get('chunk_index',-1))<0 or len(str(item.get('content_base64') or ''))>11000 or not re.fullmatch(r'[a-f0-9]{64}',str(item.get('chunk_sha256') or '').lower()):raise ValueError('Chunk do batch inválido.')
                        payload={'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id,'chunks':chunks};endpoint='/v1/artifact/batch'
                    elif name=='workspace.artifact.upload.ticket':
                        allowed={'slug','artifact_id','ttl_seconds'}
                        if not {'slug','artifact_id'}.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug e artifact_id.')
                        artifact_id=str(args.get('artifact_id') or '').strip();ttl=int(args.get('ttl_seconds') or 900);client_id=self.headers.get('X-CloudIF-Client','').strip()
                        if not re.fullmatch(r'art_[a-f0-9]{24}',artifact_id) or not (60<=ttl<=1800) or not client_id:raise ValueError('Metadados do ticket inválidos.')
                        payload={'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id,'requested_by':client_id,'ttl_seconds':ttl};endpoint='/v1/artifact/ticket'
                    else:
                        allowed={'slug','artifact_id'}
                        if not {'slug','artifact_id'}.issubset(args) or not set(args).issubset(allowed):raise ValueError('Informe slug e artifact_id.')
                        artifact_id=str(args.get('artifact_id') or '').strip()
                        if not re.fullmatch(r'art_[a-f0-9]{24}',artifact_id):raise ValueError('artifact_id inválido.')
                        payload={'project_slug':slug,'trace_id':trace_id,'artifact_id':artifact_id};endpoint='/v1/artifact/complete'
                    code,data=workspace_broker_post(endpoint,payload,timeout=90)
                    if code not in {200,201} or not data.get('ok'):
                        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'artifact_upload_failed'))
                    content=data.get('result') or data
                    if name=='workspace.artifact.upload.ticket':
                        token=str(content.pop('upload_ticket','') or '')
                        if not re.fullmatch(r'upt_[a-f0-9]{24}_[a-f0-9]{48}',token):raise ValueError('upload_ticket_invalid')
                        artifact_id=str(content.get('artifact_id') or '')
                        if not re.fullmatch(r'art_[a-f0-9]{24}',artifact_id):raise ValueError('artifact_id_invalid')
                        content['upload_url']=PUBLIC_ORIGIN+'/cloudiff/portal/artifact-upload/'+urllib.parse.quote(artifact_id,safe='')
                        content['user_action_required']=True;content['upload_method']='browser_direct';content['browser_secret_required']=False;content['secrets_exposed']=False
                elif name=='workspace.change-set.validate':
                    required={'slug','title','description','changes'};allowed=required|{'ref','ttl_seconds'}
                    if not required.issubset(args) or not set(args).issubset(allowed):raise ValueError('Os campos slug, title, description e changes são obrigatórios.')
                    slug=str(args.get('slug') or '').strip();ref=str(args.get('ref') or 'main').strip();title=str(args.get('title') or '').strip();description=str(args.get('description') or '');changes=args.get('changes');ttl=int(args.get('ttl_seconds') or 3600)
                    if not slug or not isinstance(changes,list):raise ValueError('slug deve ser texto e changes deve ser uma lista.')
                    if not ref or '..' in ref or ref.startswith('/') or ref.endswith('/'):raise ValueError('O campo ref deve ser uma referência relativa como main.')
                    if not (4<=len(title)<=160) or len(description)>4000 or not (300<=ttl<=86400):raise ValueError('title, description ou ttl_seconds incompatível.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    code,data=workspace_broker_post('/v1/change-set/validate',{'project_slug':slug,'ref':ref,'trace_id':trace_id,'title':title,'description':description,'changes':changes,'ttl_seconds':ttl},timeout=180)
                    if code not in {200,422} or not data.get('ok'):
                        error=data.get('error') or {};raise ValueError(str(error.get('message') if isinstance(error,dict) else error or 'change_set_validation_failed'))
                    content=data.get('result') or data
                elif name in {'forgejo.proposal.change-set.plan','approval.request-change-set-proposal'}:
                    required={'slug','workspace_id','change_set_digest'}|({'reason'} if name=='approval.request-change-set-proposal' else set())
                    allowed={'slug','workspace_id','change_set_digest'}|({'reason','ttl_seconds'} if name=='approval.request-change-set-proposal' else set())
                    example={'slug':'meu-projeto','workspace_id':'ws_'+'1'*24,'change_set_digest':'a'*64}
                    if name=='approval.request-change-set-proposal':example['reason']='Publicar a proposta validada'
                    args,input_normalization=canonical_tool_arguments(args,required,allowed,example,'mcp#forgejo-change-set',aliases={'project_slug':'slug'})
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=require_tool_pattern(args,'slug',r'[a-z0-9][a-z0-9-]*',example,'mcp#forgejo-change-set','O campo slug deve usar letras minúsculas, números e hífens.')
                    workspace_id=require_tool_pattern(args,'workspace_id',r'ws_[a-f0-9]{24}',example,'mcp#forgejo-change-set','O workspace_id deve usar o formato ws_ seguido de 24 caracteres hexadecimais.')
                    digest_value=require_tool_pattern(args,'change_set_digest',r'[a-f0-9]{64}',example,'mcp#forgejo-change-set','O change_set_digest deve conter 64 caracteres hexadecimais.').lower()
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    sealed=change_set_resolve(slug,workspace_id,digest_value,trace_id)
                    if sealed.get('ref')!='main':raise ValueError('Propostas controladas só podem ser criadas a partir da referência main.')
                    operation={'action':'forgejo.propose-change-set','project_slug':slug,'base_branch':'main','workspace_id':workspace_id,'change_set_digest':digest_value,'archive_sha256':sealed.get('archive_sha256'),'summary':sealed.get('summary') or {}}
                    if name=='forgejo.proposal.change-set.plan':
                        content={'ok':True,'side_effect_free':True,'client_id':client_id,'operation':operation,'approval_requirements':{'action':'forgejo.propose-change-set','project_slug':slug,'requested_by':client_id,'metadata':{'workspace_id':workspace_id,'change_set_digest':digest_value,'archive_sha256':sealed.get('archive_sha256'),'summary':sealed.get('summary') or {},'content_stored':False,'secret_values_in_metadata':False}},'branch_created':False,'pull_request_created':False,'input_normalization':input_normalization}
                    else:
                        reason=str(args.get('reason') or '').strip();ttl=int(args.get('ttl_seconds') or 900)
                        if not (4<=len(reason)<=500) or not (60<=ttl<=86400):raise ValueError('reason deve ter 4 a 500 caracteres e ttl_seconds deve estar entre 60 e 86400.')
                        created=approval_create_change_set(slug,client_id,authz,workspace_id,digest_value,str(sealed.get('archive_sha256') or ''),sealed.get('summary') or {},reason,ttl,trace_id)
                        if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'project_slug':slug,'workspace_id':workspace_id,'change_set_digest':digest_value,'action':'forgejo.propose-change-set','side_effects':{'forgejo':False,'branch_created':False,'pull_request_created':False},'content_stored_in_approval':False}
                elif name=='forgejo.proposal.change-set.create':
                    required={'slug','workspace_id','change_set_digest','approval_id'}
                    example={'slug':'meu-projeto','workspace_id':'ws_'+'1'*24,'change_set_digest':'a'*64,'approval_id':'apr_'+'1'*20}
                    args,input_normalization=canonical_tool_arguments(args,required,required,example,'mcp#forgejo-change-set',aliases={'project_slug':'slug'})
                    client_id=self.headers.get('X-CloudIF-Client','').strip()
                    if not client_id:raise ValueError('identified_client_required')
                    slug=require_tool_pattern(args,'slug',r'[a-z0-9][a-z0-9-]*',example,'mcp#forgejo-change-set','O campo slug deve usar letras minúsculas, números e hífens.')
                    workspace_id=require_tool_pattern(args,'workspace_id',r'ws_[a-f0-9]{24}',example,'mcp#forgejo-change-set','O workspace_id deve usar o formato ws_ seguido de 24 caracteres hexadecimais.')
                    digest_value=require_tool_pattern(args,'change_set_digest',r'[a-f0-9]{64}',example,'mcp#forgejo-change-set','O change_set_digest deve conter 64 caracteres hexadecimais.').lower()
                    approval_id=require_tool_pattern(args,'approval_id',r'apr_[a-f0-9]{20}',example,'mcp#forgejo-change-set','O approval_id deve usar o formato apr_ seguido de 20 caracteres hexadecimais.')
                    control('/v1/projects/'+urllib.parse.quote(slug,safe=''))
                    sealed=change_set_resolve(slug,workspace_id,digest_value,trace_id)
                    if sealed.get('ref')!='main':raise ValueError('Propostas controladas só podem ser criadas a partir da referência main.')
                    approval=approval_get(approval_id)
                    if not approval:raise ValueError('approval_not_found')
                    try:metadata=json.loads(approval.get('metadata_json') or '{}')
                    except Exception:raise ValueError('approval_metadata_invalid')
                    reservation_id,execution_id=transaction_ids('forgejo.propose-change-set',approval_id,client_id,digest_value)
                    valid_status=bool(approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id))
                    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='forgejo.propose-change-set' and approval.get('requested_by')==client_id and metadata.get('workspace_id')==workspace_id and hmac.compare_digest(str(metadata.get('change_set_digest') or ''),digest_value) and hmac.compare_digest(str(metadata.get('archive_sha256') or ''),str(sealed.get('archive_sha256') or '')) and metadata.get('content_stored') is False)
                    if not valid:raise ValueError('approval_binding_mismatch')
                    if approval.get('status')=='approved':
                        reserve_code,reserved=approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':client_id,'ttl_seconds':900})
                        if reserve_code!=200 or reserved.get('status')!='reserved':raise ValueError('approval_reserve_failed')
                    try:
                        staged_artifacts=stage_change_set_artifacts(slug,sealed.get('changes') or [],trace_id)
                    except Exception:
                        current=approval_get(approval_id)
                        if current and current.get('status')=='reserved':approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        raise
                    payload={'project_slug':slug,'base_branch':'main','workspace_id':workspace_id,'change_set_digest':digest_value,'archive_sha256':sealed.get('archive_sha256'),'ref':sealed.get('ref'),'title':sealed.get('title'),'description':sealed.get('description'),'changes':sealed.get('changes'),'trace_id':'txn-'+reservation_id,'approval_id':approval_id,'requested_by':client_id}
                    effect_code,effect=forgejo_change_set_create(payload)
                    current=approval_get(approval_id)
                    if effect_code in {200,201} and effect.get('ok'):
                        if current and current.get('status')!='consumed':
                            final_code,finalized=approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
                            if final_code!=200 or finalized.get('status')!='consumed':raise ValueError('approval_finalize_failed')
                        effect['transaction']={'approval_id':approval_id,'reservation_id':reservation_id,'execution_id':execution_id,'approval_status':'consumed'}
                        effect['workspace_validated']=True;effect['source_unchanged']=True;effect['staged_artifact_count']=len(staged_artifacts);content=effect
                    else:
                        if current and current.get('status')=='reserved' and effect_code in {400,403,404,409,422}:
                            approval_transition(approval_id,'release',{'reservation_id':reservation_id})
                        raise ValueError(str(effect.get('error') or 'forgejo_change_set_failed'))
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
                        if not created.get('ok') or created.get('status') not in {'pending','approved'}:raise ValueError('approval_create_failed')
                        content={'ok':True,'approval_id':created['approval_id'],'status':created.get('status'),'expires_at':created['expires_at'],'policy_applied':bool(created.get('policy_applied')),'approval_policy_id':created.get('approval_policy_id'),'proposal_digest':digest,'project_slug':slug,'requested_by':client_id,'action':'forgejo.propose-edit','side_effects':{'forgejo':False,'branch_created':False,'pull_request_created':False}}
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
        except ToolInputError as e:
            _tool_name=tool if 'tool' in locals() else (name if 'name' in locals() else '')
            _args=args if 'args' in locals() else {}
            _data=enrich_tool_error(_tool_name,_args,e.payload,e.payload.get('message','Parâmetros inválidos.'))
            self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32602,'message':_data['message'],'data':_data}})
        except ToolStateError as e:
            _tool_name=tool if 'tool' in locals() else (name if 'name' in locals() else '')
            _data=dict(e.payload);_data['tool']=_tool_name or _data.get('tool') or ''
            self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32009,'message':str(_data.get('message') or 'Estado do projeto não permite esta operação.'),'data':_data}})
        except urllib.error.HTTPError as e:self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32004,'message':'Recurso não encontrado' if e.code==404 else 'Falha no plano de controle'}})
        except Exception as e:
            _tool_name=tool if 'tool' in locals() else (name if 'name' in locals() else '')
            _args=args if 'args' in locals() else {}
            _message=str(e)[:160] or 'Parâmetros inválidos.'
            _data=enrich_tool_error(_tool_name,_args,{},_message)
            self.sendj(200,{'jsonrpc':'2.0','id':req.get('id') if 'req' in locals() else None,'error':{'code':-32602,'message':_message,'data':_data}})
if __name__ == '__main__':
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
