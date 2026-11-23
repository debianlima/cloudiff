#!/usr/bin/env python3
import fcntl, hashlib, hmac, json, os, re, sqlite3, ssl, time, urllib.error, urllib.parse, urllib.request
import cloudif_portal_readmodel as _rm
from contextlib import contextmanager
from pathlib import Path
import cloudif_publication_permissions as publication_permissions
DB=Path('/var/lib/cloudif/portal/cloudif-portal.db')
HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT=900
HOMOLOGATION_DEPLOY_HTTP_TIMEOUT=1020
PREVIEW_ENSURE_LOCK_ROOT=Path('/run/cloudif/preview-ensure-locks')


@contextmanager
def _preview_ensure_lock(slug):
    PREVIEW_ENSURE_LOCK_ROOT.mkdir(parents=True,exist_ok=True)
    lock_path=PREVIEW_ENSURE_LOCK_ROOT/(hashlib.sha256(str(slug).encode()).hexdigest()[:24]+'.lock')
    fd=os.open(lock_path,os.O_CREAT|os.O_RDWR,0o600);contended=False
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            contended=True;fcntl.flock(fd,fcntl.LOCK_EX)
        yield contended
    finally:
        try:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)

def _env(path):
    d={}; p=Path(path)
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            s=line.strip()
            if s and not s.startswith('#') and '=' in s:
                k,v=s.split('=',1); d[k.strip()]=v.strip().strip('"\'')
    return d

def _post(url,payload,token,host='',timeout=420):
    h={'Accept':'application/json','Content-Type':'application/json','X-CloudIF-Token':token}
    if host: h['Host']=host
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),method='POST',headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode(errors='ignore'); data=json.loads(raw or '{}')
            return r.status,data
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='ignore')
        try:data=json.loads(raw or '{}')
        except:data={'raw':raw}
        return e.code,data

def _bearer_json(method,url,token,payload=None,timeout=120):
    raw=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    if raw is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=raw,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'internal_http_error'}}
        return error.code,data


def _multiservice_clients():
    build=_env('/etc/cloudif/build-broker.env');deploy=_env('/etc/cloudif/deployment-broker.env');config=_env('/etc/cloudif/project-config-controller.env')
    build_token=build.get('CLOUDIF_BUILD_TOKEN','');deploy_token=deploy.get('CLOUDIF_DEPLOYMENT_BROKER_TOKEN','');config_token=config.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
    if not build_token or not deploy_token or not config_token:raise RuntimeError('Credenciais internas do fluxo multissserviço ausentes.')
    return {
      'buildUrl':'http://'+str(build.get('CLOUDIF_BUILD_HOST') or '127.0.0.1')+':'+str(build.get('CLOUDIF_BUILD_PORT') or '18213'),'buildToken':build_token,
      'deploymentUrl':'http://'+str(deploy.get('CLOUDIF_DEPLOYMENT_BROKER_HOST') or '127.0.0.1')+':'+str(deploy.get('CLOUDIF_DEPLOYMENT_BROKER_PORT') or '18207'),'deploymentToken':deploy_token,
      'configUrl':'http://127.0.0.1:18219','configToken':config_token,
    }


def _project_configuration(slug):
    client=_multiservice_clients();url=client['configUrl']+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/configuration'
    status,data=_bearer_json('GET',url,client['configToken'],timeout=30)
    return data if status==200 and data.get('ok') is True else {}


def _is_multiservice_project(slug):
    data=_project_configuration(slug);project=((data.get('configuration') or {}).get('project') or {}) if isinstance(data,dict) else {}
    return str(project.get('type') or '')=='multi-service'


def _compose_source_probe(slug):
    client=_multiservice_clients();url=client['deploymentUrl']+'/v1/compose-source?'+urllib.parse.urlencode({'project_slug':slug})
    status,data=_bearer_json('GET',url,client['deploymentToken'],timeout=50)
    if status==200 and isinstance(data,dict) and data.get('ok') is True:return {'linked':True,'status':'ready','source':data}
    error=data.get('error') if isinstance(data,dict) else {};code=str(error.get('code') if isinstance(error,dict) else error or '')
    if status==404 or code in {'compose_source_not_found','project_configuration_not_found'}:return {'linked':False,'status':'absent','error':code}
    if status==409 and code.startswith('compose_'):return {'linked':True,'status':'attention','error':code}
    raise RuntimeError('A detecção do stack Compose está indisponível.')


def _is_linked_compose_project(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    try:
        try:_linked_compose_binding(con,slug)
        except RuntimeError:return False
    finally:con.close()
    return bool(_compose_source_probe(slug).get('linked'))


def _linked_compose_binding(con,slug):
    row=con.execute("select komodo_repo_id,komodo_stack_id,komodo_repo_name,komodo_stack_name,repo_name,stack_name from project_integrations where project=?",(slug,)).fetchone()
    if not row:raise RuntimeError('O projeto não possui vínculo Forgejo/Komodo para o Preview.')
    expected='cloudif-'+slug
    repo_name=str(row['komodo_repo_name'] or row['repo_name'] or '')
    stack_name=str(row['komodo_stack_name'] or row['stack_name'] or '')
    if repo_name!=expected or stack_name!=expected:raise RuntimeError('O vínculo Forgejo/Komodo do projeto está inconsistente.')
    import cloudif_git_komodo_module as gk
    response=gk.v133_komodo_project_status(slug,timeout=45)
    data=response.get('data') if isinstance(response,dict) else {};data=data if isinstance(data,dict) else {}
    repo=data.get('repo') or {};stack=data.get('stack') or {}
    live_repo_id=str(data.get('repo_id') or repo.get('id') or '')
    live_stack_id=str(data.get('stack_id') or stack.get('id') or '')
    if not response.get('ok') or str(repo.get('name') or '')!=expected or str(stack.get('name') or '')!=expected:
        raise RuntimeError('O Komodo não confirmou o vínculo canônico do projeto.')
    if not re.fullmatch(r'[a-f0-9]{24}',live_repo_id) or not re.fullmatch(r'[a-f0-9]{24}',live_stack_id):
        raise RuntimeError('O Komodo não retornou identidades válidas para o projeto.')
    return {'repoId':live_repo_id,'stackId':live_stack_id,'repoName':expected,'stackName':expected}



def _fixed_preview_generation(slug):
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
        row=con.execute("select coalesce(max(preview_generation),0) as generation from publication_candidates where project_slug=? and preview_generation>0",(slug,)).fetchone();con.close()
        generation=int(row['generation'] or 0) if row else 0
        return generation if generation>0 else 1
    except Exception:return 1


def _linked_compose_status(slug,num,binding):
    import cloudif_git_komodo_module as gk
    response=gk.v133_komodo_project_status(slug,repo_id=binding['repoId'],stack_id=binding['stackId'],timeout=45)
    data=response.get('data') if isinstance(response,dict) else {};data=data if isinstance(data,dict) else {}
    repo=data.get('repo') or {};stack=data.get('stack') or {};runtime=data.get('runtime') or {}
    if not response.get('ok') or data.get('ok') is not True:raise RuntimeError('O status do stack Forgejo/Komodo está indisponível.')
    if str(data.get('repo_id') or repo.get('id') or '')!=binding['repoId'] or str(data.get('stack_id') or stack.get('id') or '')!=binding['stackId'] or str(stack.get('name') or '')!=binding['stackName']:
        raise RuntimeError('O Komodo respondeu com um stack diferente do vínculo do projeto.')
    deploy_status=str(data.get('deploy_status') or '');running=bool(runtime.get('running'));healthy=bool(running and deploy_status in {'completed','ready'})
    generation=_fixed_preview_generation(slug);ident=_stage_identity(num,'preview',generation);head=str(repo.get('latest_hash') or '')
    return {'ok':True,'configured':True,'project':slug,'public_number':int(num),'generation':generation,'stageCode':'W'+str(generation),'url':ident['url'],'hostname':ident['hostname'],'healthy':healthy,'status':deploy_status,'runtimeKind':'linked-compose','sourceMode':'forgejo-linked-stack','repoId':binding['repoId'],'stackId':binding['stackId'],'stackName':binding['stackName'],'container':str(runtime.get('container_name') or ''),'servicesCount':int(runtime.get('services_count') or 0),'bridge':f'cloudif-p{num}-w{generation}-preview-web','git':{'status':'synced' if healthy else 'degraded','head':head},'secretValuesIncluded':False,'secretReferencesIncluded':False}


def _ensure_linked_compose_preview(slug,num,binding):
    import cloudif_git_komodo_module as gk
    deployed=gk.v133_komodo_deploy_linked_current(slug,repo_id=binding['repoId'],stack_id=binding['stackId'],timeout=180)
    data=deployed.get('data') if isinstance(deployed,dict) else {};data=data if isinstance(data,dict) else {}
    if not deployed.get('ok') or data.get('ok') is not True or str(data.get('deploy_status') or '') not in {'completed','ready'}:
        raise RuntimeError('O Komodo não conseguiu atualizar o Preview a partir do Forgejo vinculado.')
    generation=_fixed_preview_generation(slug);_,_,npm_token=_clients();pstatus,pdata=_post('http://10.62.91.3/stage',{'public_number':int(num),'stage':'preview','number':generation},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or pdata.get('ok') is not True:raise RuntimeError(_publication_error('https',pdata))
    result=_linked_compose_status(slug,num,binding)
    if not result.get('healthy'):raise RuntimeError('O stack Forgejo/Komodo não ficou saudável após a atualização do Preview.')
    bridge=_compose_source_preview_bridge(slug,num,generation)
    if not _external_ok(result['hostname']):raise RuntimeError('A URL W'+str(generation)+' não respondeu após atualizar o stack Forgejo/Komodo.')
    result['bridge']=str(bridge.get('bridge') or result.get('bridge') or '');result['publisher']={'ok':True};return result


def _compose_source_preview_bridge(slug,num,generation=1):
    client=_multiservice_clients();payload={'project_slug':slug,'public_number':int(num),'generation':int(generation)}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/compose-source-preview-bridge',client['deploymentToken'],payload,timeout=120)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('A ponte pública Wn do stack Compose não pôde ser preparada.')
    expected=f'cloudif-p{int(num)}-w{int(generation)}-preview-web'
    if str(result.get('bridge') or '')!=expected:raise RuntimeError('A ponte pública Wn retornou identidade divergente.')
    return result


def _compose_snapshot_deploy(slug,environment,trace,execution_material,snapshot_id='',source_kind='linked-compose'):
    source_kind=str(source_kind or 'linked-compose').strip().lower()
    if source_kind not in {'linked-compose','preview-runtime'}:raise RuntimeError('Origem do snapshot Compose inválida.')
    client=_multiservice_clients();plan_payload={'project_slug':slug,'environment':environment,'trace_id':trace,'source_kind':source_kind}
    if snapshot_id:plan_payload['snapshot_id']=snapshot_id
    status,plan=_bearer_json('POST',client['deploymentUrl']+'/v1/compose-publication-plan',client['deploymentToken'],plan_payload,timeout=75)
    if status!=200 or plan.get('ok') is not True:raise RuntimeError('O plano de publicação Compose não pôde ser criado.')
    blockers=plan.get('blockers') or []
    if plan.get('execution_allowed') is not True or blockers:raise RuntimeError('Publicação Compose bloqueada: '+','.join(str(x) for x in blockers[:12]))
    digest=str(plan.get('deployment_plan_digest') or '')
    if not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('Digest do plano Compose inválido.')
    execution_id='exec_'+hashlib.sha256(str(execution_material).encode()).hexdigest()[:24]
    payload={**plan_payload,'deployment_plan_digest':digest,'execution_id':execution_id}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/compose-publication-deploy',client['deploymentToken'],payload,timeout=1260)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('O Deployment Broker não conseguiu materializar o snapshot Compose em '+environment+'.')
    if not re.fullmatch(r'dep_[a-f0-9]{24}',str(result.get('deployment_id') or '')):raise RuntimeError('Deployment Compose sem identidade válida.')
    snap=str(result.get('snapshot_id') or '');snap_digest=str(result.get('snapshot_digest') or '')
    if not re.fullmatch(r'snap_[a-f0-9]{24}',snap) or not re.fullmatch(r'[a-f0-9]{64}',snap_digest):raise RuntimeError('Snapshot Compose sem identidade imutável válida.')
    artifact=str(result.get('artifact_image_id') or '')
    if artifact!='sha256:'+snap_digest:raise RuntimeError('Identidade do snapshot Compose diverge do artefato retornado.')
    return plan,result


def _create_linked_compose_homologation_candidate(slug,num,candidate,actor,progress=None):
    notify=lambda step,msg:progress(step,msg) if progress else None
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);binding=_linked_compose_binding(con,slug);con.close()
    source=_linked_compose_status(slug,num,binding);preview_generation=int(source.get('generation') or _fixed_preview_generation(slug))
    if not source.get('healthy'):raise RuntimeError('O Preview W'+str(preview_generation)+' vinculado ao Forgejo não está saudável.')
    probe=_compose_source_probe(slug);source_state=probe.get('source') or {}
    source_commit=str(source_state.get('source_commit') or '')
    if not re.fullmatch(r'[a-f0-9]{40,64}',source_commit):raise RuntimeError('A origem Compose não possui commit Forgejo completo válido.')
    preview_head=str((source.get('git') or {}).get('head') or '')
    if preview_head and not source_commit.startswith(preview_head):raise RuntimeError('O HEAD exibido no Preview diverge do commit Compose materializado; atualize o Preview e tente novamente.')
    pc=_publication_config();summary=pc.environment_summary(slug,'homologation')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Homologação possui variáveis obrigatórias pendentes.')
    notify('snapshot','Congelando stack Compose, volumes e configuração do Preview W1.')
    trace='portal-hc-'+hashlib.sha256((slug+source_commit+str(candidate)).encode()).hexdigest()[:20]
    plan,deployed=_compose_snapshot_deploy(slug,'homologation',trace,'HC|'+slug+'|'+str(candidate)+'|'+source_commit)
    snapshot_id=str(deployed['snapshot_id']);snapshot_digest=str(deployed['snapshot_digest']);artifact_id='sha256:'+snapshot_digest;deployment_id=str(deployed['deployment_id'])
    operation=plan.get('operation') or {};planned_commit=str(operation.get('source_commit') or '')
    if planned_commit and not hmac.compare_digest(planned_commit,source_commit):raise RuntimeError('O HEAD Forgejo mudou durante a criação do candidato; gere novamente.')
    bridge=_multiservice_bridge(slug,deployment_id,num,'homologation',candidate,trace+'-bridge')
    notify('https','Preparando URL pública de Homologação.')
    _,_,npm_token=_clients();hstatus,hdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'homologation','number':candidate},npm_token,host='cloudif-publisher.internal',timeout=300)
    if hstatus//100!=2 or not hdata.get('ok'):raise RuntimeError(_publication_error('https',hdata))
    ident=_stage_identity(num,'homologation',candidate)
    if not _external_ok(ident['hostname']):raise RuntimeError('Validação HTTPS externa falhou para '+ident['hostname'])
    diff={'runtimeKind':'compose-snapshot','sourceMode':'forgejo-linked-stack','sourceCommit':source_commit,'sourceDigest':str(operation.get('source_digest') or ''),'snapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'secretValuesIncluded':False}
    runtime_meta={'runtimeKind':'compose-snapshot','composeSnapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'homologationDeploymentId':deployment_id,'deploymentPlanDigest':str(plan.get('deployment_plan_digest') or ''),'environment':'homologation','bridge':str(bridge.get('bridge') or ''),'sourceCommit':source_commit,'sourceDigest':str(operation.get('source_digest') or ''),'sourcePreviewStageCode':'W'+str(preview_generation),'sameSnapshotAsProductionRequired':True,'sameInstancePromotionRequired':True,'sourceKind':'linked-compose','secretValuesIncluded':False}
    now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    sql="insert into publication_candidates(project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    values=(slug,num,candidate,candidate,preview_generation,ident['code'],ident['hostname'],'awaiting_homologation',source_commit,source_commit,'compose-snapshot:'+snapshot_id,artifact_id,json.dumps(diff,ensure_ascii=False),json.dumps(runtime_meta,ensure_ascii=False),int(summary.get('environmentRevision') or 0),str(summary.get('environmentDigest') or ''),actor,now)
    con.execute(sql,values);con.commit();con.close()
    return {'ok':True,'project':slug,'candidateNumber':candidate,'stageCode':ident['code'],'url':ident['url'],'hostname':ident['hostname'],'commit':source_commit,'parentCommit':source_commit,'artifactImageId':artifact_id,'previewGeneration':preview_generation,'diff':diff,'runtimeDiff':runtime_meta,'environmentRevision':int(summary.get('environmentRevision') or 0),'snapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'secretValuesIncluded':False}



def _preview_runtime_snapshot(slug,num,generation,source_commit='',app_container='',source_checkout=''):
    base,token=_executor_runtime_client();payload={'project_slug':slug,'public_number':int(num),'generation':int(generation)}
    if source_commit:payload['expected_source_commit']=str(source_commit)
    if app_container:payload['app_container']=str(app_container)
    if source_checkout:payload['source_checkout']=str(source_checkout)
    status,result=_bearer_json('POST',base+'/v1/preview-runtime-snapshots',token,payload,timeout=1260)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:
        error=result.get('error') if isinstance(result,dict) else {};code=str(error.get('code') if isinstance(error,dict) else error or '')
        messages={
          'preview_runtime_app_not_found':'O Preview não possui app congelável associado à bridge Wn.',
          'preview_runtime_app_not_running':'O app do Preview não está ativo para criar a Homologação.',
          'preview_runtime_identity_invalid':'A identidade do app do Preview diverge do projeto/estágio selecionado.',
          'preview_runtime_source_commit_changed':'O código do Preview mudou durante a criação da Homologação.',
          'preview_runtime_source_commit_mismatch':'O container do Preview não corresponde ao commit Forgejo validado.',
          'preview_runtime_bind_outside_allowed_roots':'O Preview usa bind fora das raízes publicáveis; ajuste o runtime antes de homologar.',
          'preview_runtime_mount_unsupported':'O Preview usa um mount ainda não publicável.',
          'preview_runtime_security_blocked':'O Preview usa configuração privilegiada que não pode ser promovida.',
          'compose_snapshot_too_large':'O snapshot integral do Preview excede o limite configurado.',
        }
        raise RuntimeError(messages.get(code,'Não foi possível congelar o runtime integral do Preview.'))
    if str(result.get('source_kind') or '')!='preview-runtime':raise RuntimeError('O Executor retornou origem de snapshot divergente.')
    if not re.fullmatch(r'snap_[a-f0-9]{24}',str(result.get('snapshot_id') or '')) or not re.fullmatch(r'[a-f0-9]{64}',str(result.get('snapshot_digest') or '')):raise RuntimeError('Snapshot integral do Preview sem identidade válida.')
    return result


def _create_preview_runtime_homologation_candidate(slug,num,candidate,actor,user,source,progress=None):
    notify=lambda step,msg:progress(step,msg) if progress else None
    generation=int(source.get('generation') or 0);stage_code=str(source.get('stageCode') or '').strip().upper();match=re.fullmatch(r'W([1-9][0-9]*)',stage_code)
    if not source.get('configured') or not source.get('healthy') or not match or generation!=int(match.group(1)):
        raise RuntimeError('Prepare um Preview Wn saudável antes de criar a Homologação.')
    expected_bridge=f'cloudif-p{int(num)}-w{generation}-preview-web';bridge=str(source.get('bridge') or source.get('container') or '')
    if bridge!=expected_bridge:raise RuntimeError('O Preview selecionado não possui bridge Wn compatível com snapshot integral.')
    source_commit=str(source.get('sourceCommit') or ((source.get('git') or {}).get('head') if isinstance(source.get('git'),dict) else '') or '').strip().lower()
    if source_commit and not re.fullmatch(r'[a-f0-9]{40,64}',source_commit):raise RuntimeError('O Preview não possui commit Forgejo válido para congelamento.')
    app_container='';source_checkout=''
    if str(source.get('runtimeKind') or '')=='source-linked-preview':
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
        try:row=con.execute('select app_container,source_checkout,source_commit from project_preview_source_links where project_slug=?',(slug,)).fetchone()
        finally:con.close()
        if not row:raise RuntimeError('O vínculo source-linked do Preview não foi localizado.')
        app_container=str(row['app_container'] or '');source_checkout=str(row['source_checkout'] or '');registered_commit=str(row['source_commit'] or '').strip().lower()
        if registered_commit and source_commit and not hmac.compare_digest(registered_commit,source_commit):raise RuntimeError('O vínculo source-linked diverge do commit exibido no Preview.')
        source_commit=registered_commit or source_commit
    notify('snapshot','Congelando app, volumes, binds e rootfs do Preview '+stage_code+'.')
    snapshot=_preview_runtime_snapshot(slug,num,generation,source_commit,app_container,source_checkout);snapshot_id=str(snapshot['snapshot_id']);snapshot_digest=str(snapshot['snapshot_digest']);source_commit=str(snapshot.get('source_commit') or source_commit)
    if not re.fullmatch(r'[a-f0-9]{40,64}',source_commit):raise RuntimeError('O snapshot integral não possui commit Forgejo válido.')
    pc=_publication_config();summary=pc.environment_summary(slug,'homologation')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Homologação possui variáveis obrigatórias pendentes.')
    trace='portal-hpr-'+hashlib.sha256((slug+snapshot_id+str(candidate)).encode()).hexdigest()[:20]
    notify('deploying','Criando Homologação a partir do snapshot integral do Preview.')
    plan,deployed=_compose_snapshot_deploy(slug,'homologation',trace,'HPR|'+slug+'|'+str(candidate)+'|'+snapshot_id,snapshot_id,'preview-runtime')
    if str(deployed.get('snapshot_id') or '')!=snapshot_id or str(deployed.get('snapshot_digest') or '')!=snapshot_digest:raise RuntimeError('O deployment da Homologação diverge do snapshot congelado.')
    deployment_id=str(deployed.get('deployment_id') or '');artifact_id='sha256:'+snapshot_digest
    bridge_result=_multiservice_bridge(slug,deployment_id,num,'homologation',candidate,trace+'-bridge')
    notify('https','Preparando URL pública de Homologação.')
    _,_,npm_token=_clients();hstatus,hdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'homologation','number':candidate},npm_token,host='cloudif-publisher.internal',timeout=300)
    if hstatus//100!=2 or not hdata.get('ok'):raise RuntimeError(_publication_error('https',hdata))
    ident=_stage_identity(num,'homologation',candidate)
    if not _external_ok(ident['hostname']):raise RuntimeError('Validação HTTPS externa falhou para '+ident['hostname'])
    operation=plan.get('operation') or {};diff={'runtimeKind':'compose-snapshot','sourceMode':'preview-runtime','sourceCommit':source_commit,'sourceDigest':str(operation.get('source_digest') or snapshot.get('source_digest') or ''),'snapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'secretValuesIncluded':False}
    runtime_meta={'runtimeKind':'compose-snapshot','sourceKind':'preview-runtime','composeSnapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'homologationDeploymentId':deployment_id,'deploymentPlanDigest':str(plan.get('deployment_plan_digest') or ''),'environment':'homologation','bridge':str(bridge_result.get('bridge') or ''),'sourceCommit':source_commit,'sourceDigest':str(operation.get('source_digest') or snapshot.get('source_digest') or ''),'sourcePreviewStageCode':stage_code,'sameSnapshotAsProductionRequired':True,'sameInstancePromotionRequired':True,'secretValuesIncluded':False}
    now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    sql="insert into publication_candidates(project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    values=(slug,num,candidate,candidate,generation,ident['code'],ident['hostname'],'awaiting_homologation',source_commit,source_commit,'compose-snapshot:'+snapshot_id,artifact_id,json.dumps(diff,ensure_ascii=False),json.dumps(runtime_meta,ensure_ascii=False),int(summary.get('environmentRevision') or 0),str(summary.get('environmentDigest') or ''),actor,now)
    con.execute(sql,values);con.commit();con.close()
    return {'ok':True,'project':slug,'candidateNumber':candidate,'stageCode':ident['code'],'url':ident['url'],'hostname':ident['hostname'],'commit':source_commit,'parentCommit':source_commit,'artifactImageId':artifact_id,'previewGeneration':generation,'diff':diff,'runtimeDiff':runtime_meta,'environmentRevision':int(summary.get('environmentRevision') or 0),'snapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'secretValuesIncluded':False}


def _supersede_prior_homologations(con,slug,candidate_number):
    con.execute("update publication_candidates set status='superseded' where project_slug=? and candidate_number<? and status in ('awaiting_homologation','homologated')",(slug,int(candidate_number)))

def _linked_compose_previous_active_production(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    row=con.execute("select * from project_publications where project_slug=? and is_active=1 and status='published' order by id desc limit 1",(slug,)).fetchone()
    release=con.execute("select * from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone();con.close()
    detail={}
    if row:
        try:detail=json.loads(row['detail_json'] or '{}')
        except Exception:detail={}
    dep=str(detail.get('productionDeploymentId') or '')
    publication=int(release['publication_number']) if release else 0
    return {'deploymentId':dep if re.fullmatch(r'dep_[a-f0-9]{24}',dep) else '','publicationNumber':publication}

def _compose_deployment_status(deployment_id):
    base,token=_executor_runtime_client();status,data=_bearer_json('GET',base+'/v1/deployments/'+urllib.parse.quote(str(deployment_id),safe=''),token,timeout=30)
    if status!=200 or not isinstance(data,dict) or data.get('ok') is not True:raise RuntimeError('O Executor não confirmou o deployment homologado.')
    return data


def _compose_deployment_runtime_targets(slug,deployment_id):
    deployment_id=str(deployment_id or '').strip()
    if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('Deployment Compose inválido para diagnóstico.')
    runtime=_compose_deployment_status(deployment_id)
    if str(runtime.get('project_slug') or '')!=str(slug):raise RuntimeError('O deployment Compose pertence a outro projeto.')
    services=runtime.get('services') if isinstance(runtime.get('services'),list) else []
    routes=runtime.get('routes') if isinstance(runtime.get('routes'),list) else []
    routed=[]
    for route in routes:
        service=str((route or {}).get('service') or '').strip()
        if service and service not in routed:routed.append(service)
    db_like={'db','database','postgres','postgresql','mysql','mariadb','mongo','mongodb','redis','valkey'}
    rows=[]
    for item in services:
        if not isinstance(item,dict):continue
        service=str(item.get('service') or '').strip();container=str(item.get('container_name') or '').strip()
        if not service or not re.fullmatch(r'[A-Za-z0-9_.-]+',container):continue
        rows.append({'service':service,'container':container,'routed':service in routed,'databaseLike':service.lower() in db_like})
    rows.sort(key=lambda x:(0 if x['routed'] else 1,1 if x['databaseLike'] else 0,x['service'],x['container']))
    if not rows:raise RuntimeError('O Executor não retornou containers válidos para este deployment.')
    return {'deploymentId':deployment_id,'status':str(runtime.get('status') or ''),'environment':str(runtime.get('environment') or ''),'targets':rows,'containers':[x['container'] for x in rows],'services':[x['service'] for x in rows]}


def _compose_publication_preflight(slug,candidate,publication):
    publication=int(publication);candidate_number=int(candidate['candidate_number']);deploy_number=int(candidate['deploy_number']);num=int(candidate['public_number']);meta=_candidate_runtime_metadata(candidate);deployment_id=str(meta.get('homologationDeploymentId') or '')
    if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('A Homologação não possui deployment válido para promoção.')
    con=_publication_db(60,True);_ensure_schema(con);con.commit()
    try:
        reservation=con.execute('select candidate_number,status from publication_number_reservations where project_slug=? and publication_number=?',(slug,publication)).fetchone()
        if reservation and int(reservation['candidate_number'])!=candidate_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' está reservada por outra candidata.')
        if not reservation:_reserve_publication_number(con,slug,candidate_number,publication)
        release=con.execute('select candidate_number,deploy_number,status,is_active from production_releases where project_slug=? and publication_number=?',(slug,publication)).fetchone()
        if release and int(release['candidate_number'])!=candidate_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' já pertence a outro candidato.')
        project_row=con.execute("select deploy_number,status from project_publications where project_slug=? and (version=? or version_hostname=?) order by id desc limit 1",(slug,'P'+str(publication),_stage_identity(num,'publication',publication)['hostname'])).fetchone()
        if project_row and int(project_row['deploy_number'])!=deploy_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' já existe no histórico de outro deployment.')
        other=con.execute("select candidate_number,status from publication_jobs where project_slug=? and operation='production_release' and publication_number=? and candidate_number<>? order by id desc limit 1",(slug,publication,candidate_number)).fetchone()
        if other:raise RuntimeError('Conflito de nome: P'+str(publication)+' já foi usada por outro job de publicação.')
        request=con.execute("select candidate_number,status from production_activation_requests where project_slug=? and publication_number=? and candidate_number<>? order by created_at desc limit 1",(slug,publication,candidate_number)).fetchone()
        if request:raise RuntimeError('Conflito de nome: P'+str(publication)+' já foi reservada por outra solicitação.')
    finally:con.close()
    runtime=_compose_deployment_status(deployment_id);environment=str(runtime.get('environment') or '');runtime_status=str(runtime.get('status') or '')
    if runtime_status!='running':raise RuntimeError('O deployment homologado não está em estado executável para promoção.')
    ident=_stage_identity(num,'publication',publication)
    # One strict probe is enough for collision detection. Full health retries happen after stage activation.
    external_exists=False
    try:
        req=urllib.request.Request('https://'+ident['hostname']+'/',headers={'User-Agent':'CloudIF-Publication-Name-Preflight/1.0'})
        with urllib.request.urlopen(req,timeout=6,context=ssl.create_default_context()) as response:external_exists=(response.status==200 and bool(response.read(1024)))
    except Exception:external_exists=False
    recovering=(environment=='production')
    if external_exists and not recovering and not release:raise RuntimeError('Conflito de nome: '+ident['hostname']+' já existe fora do registro desta candidata.')
    if environment not in {'homologation','production'}:raise RuntimeError('O deployment homologado está em ambiente incompatível com a promoção.')
    return {'ok':True,'publicationNumber':publication,'stageCode':ident['code'],'hostname':ident['hostname'],'deploymentId':deployment_id,'recoveringPartialPromotion':recovering,'externalExists':external_exists,'alreadyFinalized':bool(release and int(release['candidate_number'])==candidate_number)}

def _finalize_compose_publication_db(slug,candidate,project,publication,actor,ident,artifact_id,snapshot_id,snapshot_digest,deployment_id,bridge,activation,h_cleanup,environment_revision,environment_digest):
    now=_now();num=int(candidate['public_number']);stable=f'{num}.cloudiff.duckdns.org';candidate_number=int(candidate['candidate_number']);deploy_number=int(candidate['deploy_number']);meta=_candidate_runtime_metadata(candidate)
    detail={'runtimeKind':'compose-snapshot','stageCode':ident['code'],'publicationHostname':ident['hostname'],'candidateNumber':candidate_number,'publicationNumber':int(publication),'artifactImageId':artifact_id,'composeSnapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'sourceCommit':str(meta.get('sourceCommit') or candidate['commit_sha'] or ''),'homologationDeploymentId':deployment_id,'productionDeploymentId':deployment_id,'bridge':str(bridge.get('bridge') or ''),'activeAlias':str(activation.get('active_alias') or ''),'sameArtifactAsHomologation':True,'sameSnapshotAsHomologation':True,'sameInstanceAsHomologation':True,'containersRecreated':False,'promotionMode':'in-place-role-and-routing','homologationStageRemoved':bool(h_cleanup.get('removed')),'homologationCertificatePreserved':bool(h_cleanup.get('certificatePreserved')),'secretValuesIncluded':False}
    last=None
    for attempt in range(4):
        con=_publication_db(60,True)
        try:
            _ensure_schema(con);con.commit();con.execute('begin immediate')
            existing_release=con.execute('select * from production_releases where project_slug=? and publication_number=?',(slug,int(publication))).fetchone()
            if existing_release and int(existing_release['candidate_number'])!=candidate_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' foi ocupada durante a promoção.')
            con.execute('update production_releases set is_active=0 where project_slug=?',(slug,))
            if existing_release:
                con.execute("update production_releases set candidate_number=?,deploy_number=?,stage_code=?,hostname=?,stable_hostname=?,artifact_image_id=?,status='published',is_active=1,environment_revision=?,environment_digest=?,created_by=?,published_at=? where id=?",(candidate_number,deploy_number,ident['code'],ident['hostname'],stable,artifact_id,int(environment_revision),str(environment_digest),actor,now,existing_release['id']))
            else:
                con.execute("insert into production_releases(project_slug,public_number,publication_number,candidate_number,deploy_number,stage_code,hostname,stable_hostname,artifact_image_id,status,is_active,environment_revision,environment_digest,created_by,created_at,published_at) values(?,?,?,?,?,?,?,?,?,'published',1,?,?,?,?,?)",(slug,num,int(publication),candidate_number,deploy_number,ident['code'],ident['hostname'],stable,artifact_id,int(environment_revision),str(environment_digest),actor,now,now))
            con.execute('update project_publications set is_active=0 where project_slug=?',(slug,));existing=con.execute('select id from project_publications where project_slug=? and deploy_number=?',(slug,deploy_number)).fetchone()
            if existing:con.execute("update project_publications set version=?,commit_sha=?,stable_hostname=?,version_hostname=?,status='published',is_active=1,published_at=?,message=?,detail_json=? where id=?",(ident['code'],str(candidate['commit_sha']),stable,ident['hostname'],now,'Promovida a mesma instância homologada '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False),existing['id']))
            else:con.execute("insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json) values(?,?,?,?,?,?,?,'published',1,?,?,?,?,?)",(slug,num,deploy_number,ident['code'],str(candidate['commit_sha']),stable,ident['hostname'],actor,now,now,'Promovida a mesma instância homologada '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False)))
            _supersede_prior_homologations(con,slug,candidate_number);con.execute("update publication_candidates set status='published',published_publication_number=? where id=?",(int(publication),candidate['id']))
            con.execute("insert into publication_number_reservations(project_slug,candidate_number,publication_number,status,created_at,updated_at) values(?,?,?,'published',?,?) on conflict(project_slug,candidate_number) do update set publication_number=excluded.publication_number,status='published',updated_at=excluded.updated_at",(slug,candidate_number,int(publication),now,now))
            con.commit();last=None;break
        except sqlite3.OperationalError as exc:
            if con.in_transaction:con.rollback()
            last=exc
            if 'locked' not in str(exc).lower() or attempt==3:raise
            time.sleep(0.4*(attempt+1))
        except Exception:
            if con.in_transaction:con.rollback()
            raise
        finally:con.close()
    if last:raise last
    _rm.project_changed(slug,'production-promoted')
    return detail

def _publish_linked_compose_homologated_candidate(slug,candidate,project,publication,alias,actor,progress=None):
    notify=lambda step,msg:progress(step,msg) if progress else None
    meta=_candidate_runtime_metadata(candidate);snapshot_id=str(meta.get('composeSnapshotId') or '');snapshot_digest=str(meta.get('snapshotDigest') or '');deployment_id=str(meta.get('homologationDeploymentId') or '')
    if meta.get('runtimeKind')!='compose-snapshot' or not re.fullmatch(r'snap_[a-f0-9]{24}',snapshot_id) or not re.fullmatch(r'[a-f0-9]{64}',snapshot_digest) or not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('Metadados da Homologação Compose estão incompletos.')
    if meta.get('sameInstancePromotionRequired') is not True:raise RuntimeError('O candidato não declara promoção da mesma instância homologada.')
    artifact_id='sha256:'+snapshot_digest
    if not hmac.compare_digest(artifact_id,str(candidate['artifact_image_id'] or '')):raise RuntimeError('Identidade do snapshot Compose não confere com o candidato homologado.')
    preflight=_compose_publication_preflight(slug,candidate,publication)
    notify('preflight','Nome P'+str(publication)+' e identidade do deployment validados antes da promoção.')
    previous_production=_linked_compose_previous_active_production(slug);trace='portal-pc-'+hashlib.sha256((slug+deployment_id+snapshot_id+str(publication)).encode()).hexdigest()[:20]
    if preflight.get('recoveringPartialPromotion'):
        notify('recovery','Retomando promoção parcial já materializada para P'+str(publication)+'.')
        inherited_environment=_publication_config().environment_summary(slug,'production')
        if not inherited_environment.get('valid'):raise RuntimeError('O ambiente de Produção não está válido para reconciliar a promoção parcial.')
    else:
        notify('configuration','Herdando para Produção as variáveis correntes da Homologação.')
        inherited_environment=_publication_config().clone_environment_configuration(slug,'homologation','production',actor)
        notify('production','Promovendo a própria instância homologada para Produção, sem rebuild/reclone.')
        plan,promoted=_compose_snapshot_promote(slug,deployment_id,snapshot_id,snapshot_digest,trace,'PC|'+slug+'|'+str(publication)+'|'+deployment_id)
        if str(promoted.get('deployment_id') or '')!=deployment_id or promoted.get('containerIdsPreserved') is not True or promoted.get('containersRecreated') is not False:raise RuntimeError('A Produção não preservou a instância homologada.')
    num=int(candidate['public_number']);bridge=_multiservice_bridge(slug,deployment_id,num,'publication',publication,trace+'-bridge')
    _,_,npm_token=_clients();notify('https','Preparando URL P e domínio estável para a mesma instância homologada.')
    pstage,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':publication},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstage//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
    ident=_stage_identity(num,'publication',publication)
    if not _external_ok(ident['hostname']):raise RuntimeError('Validação HTTPS externa falhou para '+ident['hostname'])
    activation=_multiservice_activate_bridge(slug,num,publication,trace+'-activate')
    pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':int(candidate['deploy_number']),'alias':alias},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not publisher.get('ok'):raise RuntimeError(_publication_error('https',publisher))
    stable=f'{num}.cloudiff.duckdns.org'
    if not _external_ok(stable):raise RuntimeError('Validação da URL estável falhou após ativação.')
    h_number=int(candidate['candidate_number']);notify('cleanup','Retirando a rota de Homologação após validar a nova Produção.')
    h_cleanup=_publisher_delete_stage(num,'homologation',h_number,npm_token);_multiservice_deactivate_bridge(slug,deployment_id,'homologation',trace+'-deactivate-h')
    previous_dep=str((previous_production or {}).get('deploymentId') or '');previous_pub=int((previous_production or {}).get('publicationNumber') or 0)
    if previous_dep and previous_dep!=deployment_id:
        _multiservice_deactivate(slug,previous_dep,'substituída pela Produção P'+str(publication),trace+'-deactivate-previous-p')
        _wait_deployment_inactive(previous_dep)
        try:_multiservice_deactivate_bridge(slug,previous_dep,'publication',trace+'-remove-previous-p-bridge')
        except Exception:pass
        if previous_pub:_publisher_delete_stage(num,'publication',previous_pub,npm_token)
    elif not previous_dep and previous_pub and previous_pub!=publication:
        _legacy_publication_deactivate(slug,num,previous_pub);_publisher_delete_stage(num,'publication',previous_pub,npm_token)
    environment_revision=int(inherited_environment.get('environmentRevision') or candidate['environment_revision'] or 0);environment_digest=str(inherited_environment.get('environmentDigest') or candidate['environment_digest'] or snapshot_digest)
    _finalize_compose_publication_db(slug,candidate,project,publication,actor,ident,artifact_id,snapshot_id,snapshot_digest,deployment_id,bridge,activation,h_cleanup,environment_revision,environment_digest)
    tenant=str(project['tenant'] if 'tenant' in project.keys() else '');queued=_enqueue_membership_reconcile(slug,actor,tenant)
    return {'ok':True,'project':slug,'candidateNumber':int(candidate['candidate_number']),'publicationNumber':int(publication),'stageCode':ident['code'],'url':ident['url'],'stableUrl':'https://'+stable+'/','aliasUrl':('https://'+alias+'.cloudiff.duckdns.org/' if alias else ''),'artifactImageId':artifact_id,'snapshotId':snapshot_id,'snapshotDigest':snapshot_digest,'deploymentId':deployment_id,'sameArtifactAsHomologation':True,'sameSnapshotAsHomologation':True,'sameInstanceAsHomologation':True,'containersRecreated':False,'homologationStageRemoved':bool(h_cleanup.get('removed')),'environmentRevision':environment_revision,'recoveredPartialPromotion':bool(preflight.get('recoveringPartialPromotion')),'membership':{'ok':True,'mode':'compose-snapshot-promotion'},'reconcile':queued,'secretValuesIncluded':False}

def _latest_multiservice_build(slug,environment='homologation'):
    client=_multiservice_clients();url=client['buildUrl']+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/multiservice/latest?'+urllib.parse.urlencode({'environment':environment})
    status,data=_bearer_json('GET',url,client['buildToken'],timeout=30)
    if status!=200 or data.get('ok') is not True or data.get('status')!='succeeded':raise RuntimeError('Nenhum build multissserviço concluído está disponível para '+environment+'.')
    if not re.fullmatch(r'build_[a-f0-9]{24}',str(data.get('job_id') or '')) or not re.fullmatch(r'[a-f0-9]{64}',str(data.get('archive_sha256') or '')):raise RuntimeError('Metadados do build multissserviço são inválidos.')
    return data


def _multiservice_artifact_identity(plan):
    apps=[]
    for item in ((plan.get('operation') or {}).get('applications') or []):
        service=str(item.get('service') or '');image=str(item.get('imageId') or '');digest=str(item.get('applicationDigest') or '')
        if not service or not image or not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('Identidade de aplicação multissserviço inválida.')
        apps.append({'service':service,'imageId':image,'applicationDigest':digest})
    if not apps:raise RuntimeError('Build multissserviço não possui aplicações publicáveis.')
    apps=sorted(apps,key=lambda x:x['service']);composite='sha256:'+hashlib.sha256(json.dumps(apps,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return composite,apps


def _multiservice_deploy(slug,build_job_id,environment,trace,execution_material):
    client=_multiservice_clients();plan_payload={'project_slug':slug,'build_job_id':build_job_id,'environment':environment,'trace_id':trace}
    status,plan=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-plan',client['deploymentToken'],plan_payload,timeout=60)
    if status!=200 or plan.get('ok') is not True:raise RuntimeError('O plano multissserviço não pôde ser criado.')
    blockers=plan.get('blockers') or []
    if plan.get('execution_allowed') is not True or blockers:raise RuntimeError('Deploy multissserviço bloqueado: '+','.join(str(x) for x in blockers[:12]))
    digest=str(plan.get('deployment_plan_digest') or '')
    if not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('Digest do plano multissserviço inválido.')
    execution_id='exec_'+hashlib.sha256(str(execution_material).encode()).hexdigest()[:24]
    payload={**plan_payload,'deployment_plan_digest':digest,'execution_id':execution_id}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-deploy',client['deploymentToken'],payload,timeout=720)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('O Deployment Broker não conseguiu materializar '+environment+'.')
    if not re.fullmatch(r'dep_[a-f0-9]{24}',str(result.get('deployment_id') or '')):raise RuntimeError('Deployment multissserviço sem identidade válida.')
    return plan,result


def _multiservice_bridge(slug,deployment_id,public_number,stage,number,trace):
    client=_multiservice_clients();payload={'project_slug':slug,'deployment_id':deployment_id,'public_number':int(public_number),'stage':stage,'number':int(number),'trace_id':trace}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-publication-bridge',client['deploymentToken'],payload,timeout=120)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('Não foi possível ligar o deployment ao gateway público.')
    return result


def _multiservice_activate_bridge(slug,public_number,publication_number,trace):
    client=_multiservice_clients();payload={'project_slug':slug,'public_number':int(public_number),'publication_number':int(publication_number),'trace_id':trace}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-publication-activate',client['deploymentToken'],payload,timeout=90)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('Não foi possível ativar o bridge estável da publicação.')
    return result




def _candidate_runtime_metadata(candidate):
    try:data=json.loads(candidate['runtime_diff_json'] or '{}')
    except Exception:data={}
    return data if isinstance(data,dict) else {}


def _multiservice_preview_client():
    env=_env('/etc/cloudif/multiservice-preview.env');token=env.get('CLOUDIF_MULTISERVICE_PREVIEW_TOKEN','')
    if not token:raise RuntimeError('Cliente interno de Preview multissserviço indisponível.')
    return {'url':str(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_URL') or 'http://127.0.0.1:18228').rstrip('/'),'token':token}


def _current_multiservice_preview(slug):
    client=_multiservice_preview_client();status,data=_bearer_json('GET',client['url']+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/latest',client['token'],timeout=30)
    if status!=200 or data.get('ok') is not True:raise RuntimeError('O estado do Preview multissserviço está indisponível.')
    return data


def _effective_environment_internal(slug,environment):
    client=_multiservice_clients();url=client['configUrl']+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/effective-internal?'+urllib.parse.urlencode({'environment':environment})
    status,data=_bearer_json('GET',url,client['configToken'],timeout=30)
    if status!=200 or data.get('ok') is not True or data.get('valid') is not True:raise RuntimeError('Ambiente '+environment+' não está válido para o Preview.')
    if data.get('secretValuesIncluded') is not False:raise RuntimeError('Contrato de secrets do ambiente é inválido.')
    return data


def _multiservice_preview_profile(slug):
    cfg=_project_configuration(slug);current=int(cfg.get('currentRevision') or 0);build=_latest_multiservice_build(slug,'preview')
    if int(build.get('config_revision') or 0)!=current:raise RuntimeError('O Preview precisa de um build da configuração atual.')
    preview=_effective_environment_internal(slug,'preview');homologation=_effective_environment_internal(slug,'homologation')
    runtime={}
    for source in (homologation.get('publicRuntimeEnvironment') or {},preview.get('publicRuntimeEnvironment') or {}):
        for service,values in source.items():runtime.setdefault(str(service),{}).update({str(k):str(v) for k,v in (values or {}).items()})
    configuration=cfg.get('configuration') or {};dependencies=[];dependency_passwords=set()
    for raw in configuration.get('dependencies') or []:
        if not isinstance(raw,dict) or raw.get('kind')!='mongodb':continue
        mapping=raw.get('variableMap') or {};password_name=str(mapping.get('password') or '')
        if password_name:dependency_passwords.add((str(raw.get('service') or ''),password_name))
        dependencies.append({'kind':'mongodb','name':str(raw.get('name') or ''),'service':str(raw.get('service') or ''),'database':str(raw.get('database') or ''),'variableMap':{str(k):str(v) for k,v in mapping.items()}})
    generated={}
    for service,refs in (homologation.get('secretRuntimeReferences') or {}).items():
        names=[str(name) for name in (refs or {}) if (str(service),str(name)) not in dependency_passwords]
        if names:generated[str(service)]=sorted(set(names))
    return {'build':build,'runtime_variables':runtime,'generated_secrets':generated,'dependencies':dependencies,'configurationRevision':current,'secretValuesIncluded':False}


def _ensure_multiservice_preview(slug,num,user):
    profile=_multiservice_preview_profile(slug);client=_multiservice_preview_client();actor=str(user.get('username') or 'portal');groups=[str(x) for x in (user.get('groups') or [])]
    common={'build_job_id':profile['build']['job_id'],'ttl_seconds':7200,'actor_user':actor,'actor_groups':groups,'runtime_variables':profile['runtime_variables'],'generated_secrets':profile['generated_secrets'],'dependencies':profile['dependencies']}
    status,plan=_bearer_json('POST',client['url']+'/v1/plan',client['token'],common,timeout=90)
    if status!=200 or plan.get('ok') is not True:raise RuntimeError('Não foi possível planejar o Preview multissserviço.')
    create={**common,'preview_plan_digest':str(plan.get('preview_plan_digest') or '')};status,result=_bearer_json('POST',client['url']+'/v1/previews',client['token'],create,timeout=300)
    if status not in {200,201} or result.get('ok') is not True:raise RuntimeError('Não foi possível criar o Preview multissserviço.')
    preview_id=str(result.get('preview_id') or '');bridge_payload={'preview_id':preview_id,'public_number':int(num),'workspace_number':1,'actor_user':actor,'actor_groups':groups};status,bridge=_bearer_json('POST',client['url']+'/v1/workspace-bridges',client['token'],bridge_payload,timeout=120)
    if status not in {200,201} or bridge.get('ok') is not True:raise RuntimeError('Não foi possível atualizar o endereço W1 do Preview.')
    ident=_stage_identity(num,'preview',1);_,_,npm_token=_clients();pstatus,pdata=_post('http://10.62.91.3/stage',{'public_number':int(num),'stage':'preview','number':1},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or pdata.get('ok') is not True:raise RuntimeError(_publication_error('https',pdata))
    return {'ok':True,'configured':True,'project':slug,'public_number':int(num),'generation':1,'stageCode':'W1','hostname':ident['hostname'],'url':ident['url'],'previewId':preview_id,'buildJobId':profile['build']['job_id'],'bridge':bridge.get('bridge'),'previousPreviewId':bridge.get('previous_preview_id') or '','runtimeKind':'multiservice','mongoEphemeral':bool(profile['dependencies']),'generatedSecretsEphemeral':True,'secretValuesIncluded':False}


def _publication_error(stage,data):
    data=data if isinstance(data,dict) else {}
    code=str(data.get('error') or '').strip()
    message=str(data.get('message') or '').strip()
    known={
      'publication_image_build_failed':'A imagem da publicação não pôde ser criada a partir da base atual.',
      'publication_image_digest_missing':'A imagem da publicação foi criada sem identificação imutável.',
      'publication_base_reference_invalid':'A revisão da imagem-base não está disponível para esta publicação.',
      'publication_base_identity_mismatch':'A imagem-base local não corresponde à revisão congelada. Abra a base e publique novamente.',
      'publication_stack_update_failed':'A configuração da nova versão não pôde ser atualizada no Komodo.',
      'publication_stack_deploy_failed':'O Komodo não conseguiu iniciar a nova versão.',
      'publication_container_not_healthy':'A nova versão foi criada, mas o container não ficou saudável no tempo esperado.',
      'publication_terminal_unavailable':'A nova versão subiu, mas a validação do terminal não ficou disponível.',
      'target_not_healthy':'A versão selecionada não está saudável para ser ativada.',
      'immutable_runtime_snapshot_conflict':'Esta versão já está pronta e não pode trocar a revisão da base ou do ambiente. Publique uma nova versão.',
      'immutable_deploy_conflict':'Esta versão já está pronta com outro commit. Publique uma nova versão.',
    }
    if code in known:return known[code]
    if message and len(message)<=320 and not any(ch in message for ch in '{}[]'):
        return message
    fallback={
      'deploy':'Não foi possível iniciar a nova versão a partir da base atual.',
      'https':'Não foi possível configurar o endereço HTTPS da nova versão.',
      'promote':'A nova versão foi preparada, mas não pôde ser ativada.',
      'rebuild':'Não foi possível reconstruir a versão selecionada.',
    }
    return fallback.get(stage,'A publicação não pôde ser concluída.')


def _project_allowed(con,slug,user):
    row=con.execute('select * from projects where slug=?',(slug,)).fetchone()
    if not row:return None
    if publication_permissions.is_admin(user) or publication_permissions.is_professor(user):return row
    username=(user.get('username') or '').strip().lower()
    groups={str(x).strip().lower() for x in user.get('groups',[]) if str(x).strip()}
    cols=set(row.keys())
    owners=[]
    for k in ('owner','created_by'):
        if k in cols and row[k]: owners.append(str(row[k]).strip().lower())
    if username and username in owners:return row
    for acl in con.execute('select subject_type,subject from project_acl where slug=?',(slug,)):
        st=str(acl[0] or '').lower(); sub=str(acl[1] or '').strip().lower()
        if st=='user' and sub==username:return row
        if st=='group' and sub in groups:return row
    return None

def _ensure_schema(con):
    con.executescript('''
CREATE TABLE IF NOT EXISTS project_public_ids(project_slug TEXT PRIMARY KEY,public_number INTEGER NOT NULL UNIQUE,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_publications(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,
 version TEXT NOT NULL DEFAULT '',commit_sha TEXT NOT NULL DEFAULT '',stable_hostname TEXT NOT NULL,version_hostname TEXT NOT NULL,
 status TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,published_at TEXT,
 message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',UNIQUE(project_slug,deploy_number),UNIQUE(version_hostname));
CREATE INDEX IF NOT EXISTS idx_project_publications_active ON project_publications(project_slug,is_active,status);
CREATE TABLE IF NOT EXISTS publication_jobs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,actor TEXT NOT NULL,status TEXT NOT NULL,
 step TEXT NOT NULL DEFAULT 'queued',message TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT);
CREATE INDEX IF NOT EXISTS idx_publication_jobs_project ON publication_jobs(project_slug,id DESC);
CREATE TABLE IF NOT EXISTS project_publication_aliases(
 alias TEXT PRIMARY KEY,project_slug TEXT NOT NULL UNIQUE,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS publication_job_acknowledgements(
 job_id INTEGER PRIMARY KEY,actor TEXT NOT NULL,acknowledged_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_homologators(
 project_slug TEXT NOT NULL,username TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(project_slug,username));
CREATE TABLE IF NOT EXISTS publication_candidates(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,candidate_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,
 preview_generation INTEGER NOT NULL,stage_code TEXT NOT NULL,hostname TEXT NOT NULL,status TEXT NOT NULL,parent_commit TEXT NOT NULL,commit_sha TEXT NOT NULL,
 artifact_image TEXT NOT NULL DEFAULT '',artifact_image_id TEXT NOT NULL DEFAULT '',diff_json TEXT NOT NULL DEFAULT '{}',runtime_diff_json TEXT NOT NULL DEFAULT '{}',
 environment_revision INTEGER NOT NULL DEFAULT 0,environment_digest TEXT NOT NULL DEFAULT '',created_by TEXT NOT NULL,created_at TEXT NOT NULL,
 homologated_by TEXT NOT NULL DEFAULT '',homologated_at TEXT,rejected_by TEXT NOT NULL DEFAULT '',rejected_at TEXT,rejection_note TEXT NOT NULL DEFAULT '',published_publication_number INTEGER NOT NULL DEFAULT 0,
 UNIQUE(project_slug,candidate_number));
CREATE INDEX IF NOT EXISTS idx_publication_candidates_project ON publication_candidates(project_slug,candidate_number DESC);
CREATE TABLE IF NOT EXISTS production_releases(
 id INTEGER PRIMARY KEY AUTOINCREMENT,project_slug TEXT NOT NULL,public_number INTEGER NOT NULL,publication_number INTEGER NOT NULL,candidate_number INTEGER NOT NULL,deploy_number INTEGER NOT NULL,
 stage_code TEXT NOT NULL,hostname TEXT NOT NULL,stable_hostname TEXT NOT NULL,artifact_image_id TEXT NOT NULL,status TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 0,
 environment_revision INTEGER NOT NULL DEFAULT 0,environment_digest TEXT NOT NULL DEFAULT '',created_by TEXT NOT NULL,created_at TEXT NOT NULL,published_at TEXT,
 UNIQUE(project_slug,publication_number));
CREATE INDEX IF NOT EXISTS idx_production_releases_active ON production_releases(project_slug,is_active,status);
CREATE TABLE IF NOT EXISTS production_activation_requests(
 project_slug TEXT NOT NULL,candidate_number INTEGER NOT NULL,publication_number INTEGER NOT NULL,
 activation_digest TEXT NOT NULL,approval_id TEXT NOT NULL DEFAULT '',requested_by TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 PRIMARY KEY(project_slug,candidate_number,publication_number),UNIQUE(approval_id));
CREATE TABLE IF NOT EXISTS publication_number_reservations(
 project_slug TEXT NOT NULL,candidate_number INTEGER NOT NULL,publication_number INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'reserved',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(project_slug,candidate_number),UNIQUE(project_slug,publication_number));
''')
    cols={row[1] for row in con.execute('pragma table_info(publication_jobs)')}
    for name,kind in (
      ('base_revision','INTEGER NOT NULL DEFAULT 0'),('base_image',"TEXT NOT NULL DEFAULT ''"),('base_image_id',"TEXT NOT NULL DEFAULT ''"),
      ('environment',"TEXT NOT NULL DEFAULT 'production'"),('environment_revision','INTEGER NOT NULL DEFAULT 0'),('environment_digest',"TEXT NOT NULL DEFAULT ''"),
      ('operation',"TEXT NOT NULL DEFAULT 'legacy_publish'"),('candidate_number','INTEGER NOT NULL DEFAULT 0'),('publication_number','INTEGER NOT NULL DEFAULT 0'),
      ('approval_id',"TEXT NOT NULL DEFAULT ''"),('activation_digest',"TEXT NOT NULL DEFAULT ''"),
      ('authorization_mode',"TEXT NOT NULL DEFAULT 'critical_approval'"),('authorization_role',"TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in cols:con.execute(f'alter table publication_jobs add column {name} {kind}')
    publication_permissions.ensure_schema(con)

def _publication_db(timeout=60,row_factory=False):
    con=sqlite3.connect(DB,timeout=float(timeout));con.execute('pragma busy_timeout='+str(int(float(timeout)*1000)))
    if row_factory:con.row_factory=sqlite3.Row
    return con


def _number(con,slug):
    r=con.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
    if r:return int(r[0])
    if not con.execute('select 1 from projects where slug=?',(slug,)).fetchone():raise RuntimeError('Projeto não encontrado.')
    own_transaction=not con.in_transaction
    try:
        if own_transaction:con.execute('BEGIN IMMEDIATE')
        r=con.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
        if r:
            if own_transaction:con.commit()
            return int(r[0])
        now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        number=int(con.execute('select coalesce(max(public_number),1000)+1 from project_public_ids').fetchone()[0])
        con.execute('insert into project_public_ids(project_slug,public_number,created_at,updated_at) values(?,?,?,?)',(slug,number,now,now))
        if own_transaction:con.commit()
        return number
    except Exception:
        if own_transaction and con.in_transaction:con.rollback()
        raise

def _clients():
    k=_env('/etc/cloudif/komodo-publication-client.env'); n=_env('/etc/cloudif/npm-publisher-client.env')
    ku=(k.get('KOMODO_PUBLICATION_URL') or 'http://10.62.91.2:18098').rstrip('/'); kt=k.get('KOMODO_PUBLICATION_TOKEN','')
    nt=n.get('NPM_PUBLISHER_TOKEN','')
    if not kt or not nt: raise RuntimeError('Credenciais internas de publicação ausentes.')
    return ku,kt,nt

def _publication_config():
    import cloudif_project_publication_config as module
    return module

def project_base_status(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    num=_number(con,slug);con.close()
    return _publication_config().base_status(slug,num)

def project_environment_status(slug):
    return _publication_config().environment_summary(slug)

def base_workspace_preflight(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    from cloudif_project_environment_web import authorization
    auth=authorization(slug,user.get('username') or '',user.get('groups') or [])
    if not auth.get('canWrite'):con.close();raise PermissionError('A edição da base exige permissão de escrita no projeto.')
    num=_number(con,slug);con.close()
    return {'ok':True,'project':slug,'public_number':num,'canWrite':True,'secretValuesIncluded':False}


def ensure_base_workspace(slug,user):
    access=base_workspace_preflight(slug,user);num=int(access['public_number'])
    base=_publication_config().ensure_base(slug,num,user.get('username') or 'portal')
    container=str(base['workspace_container']);terminal=str(base.get('terminal') or '');server_id=str(base.get('server_id') or '')
    if not terminal or not server_id:raise RuntimeError('base_workspace_terminal_contract_invalid')
    target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
    return {'ok':True,'project':slug,'public_number':num,'container':container,'baseRevision':int(base.get('base_revision') or 0),'baseImageId':str(base.get('base_image_id') or ''),'terminalUrl':target,'terminalReady':True,'secretValuesIncluded':False}

def _external_ok(host):
    # A newly issued stage certificate can take a few seconds to become the
    # certificate served by the public edge.  Keep strict CA+hostname checking,
    # but allow bounded propagation time instead of failing the whole release on
    # the first transient mismatch.
    try: attempts=max(1,min(60,int(os.environ.get('CLOUDIF_PUBLICATION_HTTPS_READY_ATTEMPTS','18'))))
    except Exception: attempts=18
    try: delay=max(0.0,min(10.0,float(os.environ.get('CLOUDIF_PUBLICATION_HTTPS_READY_INTERVAL','5'))))
    except Exception: delay=5.0
    for attempt in range(attempts):
        req=urllib.request.Request('https://'+host+'/',headers={'User-Agent':'CloudIF-Publication-Validator/1.0'})
        try:
            with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context()) as r:
                body=r.read(200000)
                if r.status==200 and len(body)>0:return True
        except (urllib.error.URLError,ssl.SSLError,OSError,TimeoutError):
            pass
        if attempt+1<attempts and delay:time.sleep(delay)
    return False


TARGET_SLUG='atalhos-cloudif-iff1860746'
PRODUCTION_URL='https://cloudiff.duckdns.org/production/atalhos-cloudif-iff1860746/'
def _production_env():return _env('/etc/cloudif/production-public-client.env')
def _production_call(path,payload=None,timeout=180):
 e=_production_env();token=e.get('CLOUDIF_PRODUCTION_PUBLIC_TOKEN','')
 if not token:raise RuntimeError('Token interno de produção ausente.')
 headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};url='http://cloudif-production-public.internal'+path
 req=urllib.request.Request(url,data=(json.dumps(payload).encode() if payload is not None else None),method=('POST' if payload is not None else 'GET'),headers=headers)
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read() or b'{}')
def _latest_production_build(slug):
 c=sqlite3.connect('/var/lib/cloudif/build-broker/builds.sqlite3');c.row_factory=sqlite3.Row
 rows=c.execute("select id,result_json from builds where project_slug=? and status='succeeded' order by created_at desc",(slug,)).fetchall();c.close()
 for r in rows:
  try:x=json.loads(r['result_json'] or '{}')
  except Exception:continue
  if x.get('production_ready') is True and x.get('attestation_verified') is True and x.get('scanner_ready') is True and x.get('scanner_blocked') is False and x.get('sbom_ready') is True and x.get('artifact_image_id'):
   return r['id'],x
 raise RuntimeError('Nenhum build imutável e aprovado está disponível para produção.')
def _publish_production(slug,user):
 con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;project=_project_allowed(con,slug,user);con.close()
 if not project:raise PermissionError('Projeto não encontrado ou sem permissão.')
 if not user.get('admin'):raise PermissionError('Publicação real exige administrador tenant ou professor.')
 build_id,x=_latest_production_build(slug);eid='prd_'+hashlib.sha256((slug+build_id+x['artifact_image_id']+str(time.time_ns())).encode()).hexdigest()[:24]
 result=_production_call('/v1/deploy',{'project_slug':slug,'artifact_image_id':x['artifact_image_id'],'execution_id':eid},240)
 if not result.get('ok'):raise RuntimeError('Executor de produção recusou a publicação.')
 return {'ok':True,'slug':slug,'public_number':0,'deploy_number':int(result.get('release_id') or 0),'stable_url':PRODUCTION_URL,'version_url':PRODUCTION_URL,'commit':build_id,'artifact_image_id':x['artifact_image_id'],'blue_green':True,'external_health':result.get('external_health'),'idempotent':result.get('idempotent') is True}
def rollback_production(slug,user):
 con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;project=_project_allowed(con,slug,user);con.close()
 if not project or not user.get('admin'):raise PermissionError('Rollback real exige administrador tenant ou professor.')
 eid='prb_'+hashlib.sha256((slug+str(time.time_ns())).encode()).hexdigest()[:24];return _production_call('/v1/rollback',{'project_slug':slug,'execution_id':eid},240)
def production_status(slug):
 if slug!=TARGET_SLUG:return None
 try:return _production_call('/v1/status')
 except Exception:return {'ok':False,'public_url':PRODUCTION_URL,'public_traffic':False}

def _stage_identity(public_number,stage,number):
    labels={'preview':('W','w','preview'),'homologation':('H','h','homologation'),'publication':('P','p','publication')}
    if stage not in labels:raise ValueError('invalid_stage')
    upper,lower,label=labels[stage];number=int(number);name=f'{int(public_number)}-{lower}{number}-{label}'
    return {'code':upper+str(number),'name':name,'hostname':name+'.cloudiff.duckdns.org','url':'https://'+name+'.cloudiff.duckdns.org/'}


def _project_owner(con,slug):
    row=con.execute('select * from projects where slug=?',(slug,)).fetchone()
    if not row:return ''
    keys=set(row.keys());return str((row['owner'] if 'owner' in keys else '') or (row['created_by'] if 'created_by' in keys else '') or '').strip().lower()


def _owner_or_admin(con,slug,user):
    if user.get('admin'):return True
    return bool((user.get('username') or '').strip().lower()==_project_owner(con,slug))


def _can_homologate(con,slug,user):
    return publication_permissions.can_homologate(con,slug,user)


def _can_publish(con,slug,user):
    return publication_permissions.can_publish(con,slug,user)


def _release_permission_role(con,slug,user):
    if publication_permissions.is_admin(user):return 'admin'
    if publication_permissions.is_professor(user):return 'professor'
    if (user.get('username') or '').strip().lower()==_project_owner(con,slug):return 'owner'
    return 'delegated'


def homologators(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not (_project_allowed(con,slug,user) or _can_homologate(con,slug,user)):con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    owner=_project_owner(con,slug);rows=[str(x['username']) for x in con.execute('select username from project_homologators where project_slug=? order by username',(slug,)).fetchall()];allowed=_can_homologate(con,slug,user);con.close()
    return {'ok':True,'project':slug,'owner':owner,'homologators':rows,'canHomologate':allowed}


def set_homologators(slug,user,usernames):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _project_allowed(con,slug,user):con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    try:result=publication_permissions.replace_homologators(con,slug,user,usernames if isinstance(usernames,list) else [])
    finally:con.close()
    return {'ok':True,'project':slug,'homologators':[row['username'] for row in result.get('users',[]) if row.get('homologate') and not row.get('locked')]}


def publication_permissions_status(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _project_allowed(con,slug,user):con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    result=publication_permissions.snapshot(con,slug,user);con.close()
    return {'ok':True,'project':slug,**result}


def set_publication_permissions(slug,user,entries):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _project_allowed(con,slug,user):con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    try:result=publication_permissions.set_permissions(con,slug,user,entries if isinstance(entries,list) else [])
    finally:con.close()
    return {'ok':True,'project':slug,**result}


def _runtime_preview(slug,num,operation,payload=None,timeout=180):
    ku,kt,_=_clients();body={'project':slug,'public_number':int(num),**(payload or {})};status,data=_post(ku+'/komodo/project/preview/'+operation,body,kt,timeout=timeout)
    if status//100!=2 or data.get('ok') is not True:raise RuntimeError(_publication_error('preview',data) if data else 'Preview indisponível.')
    return data


def _source_link_preview_status(slug,num,row):
    if not isinstance(row,dict) or not row:return None
    stage_code=str(row.get('stage_code') or '').strip().upper();match=re.fullmatch(r'W([1-9][0-9]*)',stage_code)
    if not match:return None
    generation=int(match.group(1));ident=_stage_identity(num,'preview',generation);declared=str(row.get('url') or '')
    if declared and declared.rstrip('/')+'/'!=ident['url']:return None
    status=str(row.get('status') or '').strip().lower();external_ok=False
    if status in {'online','ready','healthy'}:
        try:external_ok=_external_ok(ident['hostname'])
        except Exception:external_ok=False
    containers=[x for x in (str(row.get('app_container') or ''),str(row.get('gateway_container') or '')) if x]
    return {'ok':True,'configured':True,'project':slug,'public_number':int(num),'generation':generation,'stageCode':ident['code'],'url':ident['url'],'hostname':ident['hostname'],'healthy':bool(external_ok),'status':status or 'unknown','container':str(row.get('gateway_container') or ''),'containers':containers,'bridge':str(row.get('gateway_container') or ''),'runtimeKind':'source-linked-preview','sourceMode':'project-preview-source-link','sourceCommit':str(row.get('source_commit') or ''),'sourceRepo':str(row.get('source_repo') or ''),'sourceBranch':str(row.get('source_branch') or ''),'git':{'ok':bool(row.get('source_commit')),'remoteAvailable':True,'status':'linked','message':str(row.get('message') or 'Preview vinculado por infraestrutura.'),'head':str(row.get('source_commit') or '')},'dataIsolated':bool(row.get('data_isolated')),'sourceBindReadonly':bool(row.get('source_bind_readonly')),'httpsVerified':bool(external_ok),'secretValuesIncluded':False,'secretReferencesIncluded':False}


def preview_status(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    allowed=_project_allowed(con,slug,user) or _can_homologate(con,slug,user)
    if not allowed:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug);linked=_linked_compose_binding(con,slug) if _is_linked_compose_project(slug) else None;source_link=None
    try:
        row=con.execute('select * from project_preview_source_links where project_slug=?',(slug,)).fetchone();source_link=dict(row) if row else None
    except sqlite3.Error:source_link=None
    con.close()
    if linked:return _linked_compose_status(slug,num,linked)
    if _is_multiservice_project(slug):
        data=_current_multiservice_preview(slug);ident=_stage_identity(num,'preview',1)
        if data.get('configured'):
            return {'ok':True,'configured':True,'project':slug,'public_number':num,'generation':1,'stageCode':'W1','url':ident['url'],'hostname':ident['hostname'],'healthy':bool(data.get('healthy')),'status':str(data.get('status') or ''),'previewId':str(data.get('preview_id') or ''),'buildJobId':str(data.get('build_job_id') or ''),'archiveSha256':str(data.get('archive_sha256') or ''),'configRevision':int(data.get('config_revision') or 0),'bridge':f'cloudif-p{num}-w1-preview-web','services':data.get('services') or [],'mongoEphemeral':bool(data.get('mongoEphemeral')),'expiresAt':int(data.get('expires_at') or 0),'runtimeKind':'multiservice','secretValuesIncluded':False}
        ku,kt,_=_clients();fallback_status,fallback=_post(ku+'/komodo/project/preview/status',{'project':slug,'public_number':num},kt,timeout=30)
        if fallback_status//100==2 and fallback.get('configured'):
            generation=int(fallback.get('generation') or 1);fallback_ident=_stage_identity(num,'preview',generation);fallback.update({'url':fallback_ident['url'],'hostname':fallback_ident['hostname'],'stageCode':fallback_ident['code'],'runtimeKind':'generic-preview','fallbackFrom':'multiservice'})
            return fallback
        linked_source=_source_link_preview_status(slug,num,source_link)
        if linked_source:return linked_source
        return {'ok':True,'configured':False,'project':slug,'public_number':num,'generation':1,'stageCode':'W1','url':ident['url'],'hostname':ident['hostname'],'runtimeKind':'multiservice','secretValuesIncluded':False}
    ku,kt,_=_clients();status,data=_post(ku+'/komodo/project/preview/status',{'project':slug,'public_number':num},kt,timeout=30)
    if status//100!=2:return {'ok':False,'configured':False,'error':'preview_status_unavailable'}
    if data.get('configured'):
        ident=_stage_identity(num,'preview',int(data.get('generation') or 1));data.update({'url':ident['url'],'hostname':ident['hostname'],'stageCode':ident['code']});return data
    linked_source=_source_link_preview_status(slug,num,source_link)
    return linked_source or data


def ensure_preview(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug);con.close()
    with _preview_ensure_lock(slug) as contended:
        if contended:
            try:current=preview_status(slug,user)
            except Exception:current={}
            if current.get('configured') and current.get('healthy'):
                current['deduplicated']=True;return current
        linked=None
        if _is_linked_compose_project(slug):
            con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
            try:linked=_linked_compose_binding(con,slug)
            finally:con.close()
        if linked:return _ensure_linked_compose_preview(slug,num,linked)
        if _is_multiservice_project(slug):
            current=preview_status(slug,user)
            if str(current.get('runtimeKind') or '')=='multiservice' or not current.get('configured'):return _ensure_multiservice_preview(slug,num,user)
        pc=_publication_config();summary=pc.environment_summary(slug,'preview')
        if not summary.get('valid'):raise RuntimeError('O ambiente Preview possui variáveis obrigatórias pendentes.')
        runtime=pc.execution_environment(slug,int(summary['environmentRevision']),str(summary.get('environmentDigest') or ''),'preview');values=runtime.get('values') or {}
        try:
            data=_runtime_preview(slug,num,'ensure',{'actor':user.get('username') or 'portal','environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest']),'environment_variables':values},240)
        finally:
            if isinstance(values,dict):values.clear();runtime['values']={}
        ident=_stage_identity(num,'preview',int(data.get('generation') or 1));_,_,nt=_clients();status,pub=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'preview','number':int(data.get('generation') or 1)},nt,host='cloudif-publisher.internal',timeout=300)
        if status//100!=2 or not pub.get('ok'):raise RuntimeError(_publication_error('https',pub))
        data.update({'url':ident['url'],'hostname':ident['hostname'],'stageCode':ident['code'],'publisher':{'ok':True}});return data



def preview_terminal(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    from cloudif_project_environment_web import authorization
    auth=authorization(slug,user.get('username') or '',user.get('groups') or [])
    if not auth.get('canWrite'):con.close();raise PermissionError('O terminal do Preview exige permissão de escrita no projeto.')
    num=_number(con,slug);con.close()
    ku,kt,_=_clients();status,data=_post(ku+'/komodo/project/preview/terminal',{'project':slug,'public_number':num,'actor':user.get('username') or 'portal'},kt,timeout=60)
    if status//100!=2 or data.get('ok') is not True:raise RuntimeError(str(data.get('message') or 'O terminal do Preview está temporariamente indisponível.'))
    container=str(data.get('container') or '');server_id=str(data.get('server_id') or '');terminal=str(data.get('terminal') or '');generation=int(data.get('generation') or 0)
    expected=f'cloudif-p{num}-w{generation}-preview-web'
    if generation<1 or container!=expected or not server_id or not terminal:raise RuntimeError('preview_terminal_contract_invalid')
    target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
    return {'ok':True,'project':slug,'public_number':num,'generation':generation,'stageCode':'W'+str(generation),'container':container,'terminalUrl':target,'terminalReady':True,'terminalSource':'preview_workspace','secretValuesIncluded':False,'secretReferencesIncluded':False}



def stage_terminal(slug,user,environment='preview'):
    environment=str(environment or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('Ambiente de terminal inválido.')
    if environment=='preview':return preview_terminal(slug,user)
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    from cloudif_project_environment_web import authorization
    auth=authorization(slug,user.get('username') or '',user.get('groups') or [])
    if not auth.get('canWrite'):con.close();raise PermissionError('O terminal exige permissão de escrita no projeto.')
    if environment=='production' and not _owner_or_admin(con,slug,user):con.close();raise PermissionError('O terminal de Produção exige o responsável pelo projeto ou administrador.')
    num=_number(con,slug);payload={'project':slug,'public_number':num,'environment':environment,'actor':user.get('username') or 'portal'};expected=''
    if environment=='homologation':
        row=con.execute("select candidate_number,deploy_number,stage_code,status from publication_candidates where project_slug=? and status in ('awaiting_homologation','homologated') order by candidate_number desc limit 1",(slug,)).fetchone()
        if not row:con.close();raise RuntimeError('Nenhum candidato de Homologação está disponível para abrir o terminal.')
        dep=int(row['deploy_number'] or 0);candidate=int(row['candidate_number'] or 0)
        if dep<1 or candidate<1:con.close();raise RuntimeError('O candidato de Homologação não possui runtime válido.')
        payload.update({'deploy_number':dep,'candidate_number':candidate});expected=f'cloudif-p{num}-d{dep}-web';stage_code=str(row['stage_code'] or ('H'+str(candidate)))
    else:
        release=con.execute("select publication_number,candidate_number,deploy_number,stage_code,status from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone()
        if release:
            publication=int(release['publication_number'] or 0);dep=int(release['deploy_number'] or 0);candidate=int(release['candidate_number'] or 0)
            if publication<1:con.close();raise RuntimeError('A Produção ativa não possui runtime válido.')
            payload.update({'publication_number':publication,'deploy_number':dep,'candidate_number':candidate,'legacy':False});expected=f'cloudif-p{num}-p{publication}-publication-web';stage_code=str(release['stage_code'] or ('P'+str(publication)))
        else:
            legacy=con.execute("select deploy_number from project_publications where project_slug=? and status='published' and is_active=1 order by id desc limit 1",(slug,)).fetchone()
            if not legacy:con.close();raise RuntimeError('Nenhuma Produção ativa está disponível para abrir o terminal.')
            dep=int(legacy['deploy_number'] or 0)
            if dep<1:con.close();raise RuntimeError('A Produção ativa não possui runtime válido.')
            payload.update({'deploy_number':dep,'legacy':True});expected=f'cloudif-p{num}-d{dep}-web';stage_code='P'+str(dep)
    con.close();ku,kt,_=_clients();status,data=_post(ku+'/komodo/project/stage/terminal',payload,kt,timeout=60)
    if status//100!=2 or data.get('ok') is not True:raise RuntimeError(str(data.get('message') or 'O terminal deste ambiente está temporariamente indisponível.'))
    container=str(data.get('container') or '');server_id=str(data.get('server_id') or '');terminal=str(data.get('terminal') or '')
    if container!=expected or not server_id or not terminal:raise RuntimeError('stage_terminal_contract_invalid')
    target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
    return {'ok':True,'project':slug,'public_number':num,'environment':environment,'stageCode':stage_code,'container':container,'terminalUrl':target,'terminalReady':True,'terminalSource':'publication_stage','secretValuesIncluded':False,'secretReferencesIncluded':False}

def runtime_diagnostic_target(slug,user,environment='preview'):
    environment=str(environment or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('Ambiente de diagnóstico inválido.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug);containers=[];stage_code='';detail={}
    if environment=='preview':
        try:
            if _is_linked_compose_project(slug):
                binding=_linked_compose_binding(con,slug);status=_linked_compose_status(slug,num,binding);stage_code=str(status.get('stageCode') or ('W'+str(_fixed_preview_generation(slug))));candidate=str(status.get('container') or '').strip();containers=[candidate] if candidate else []
                stack_id=str(status.get('stackId') or binding.get('stackId') or '')
            else:
                status=preview_status(slug,user);stage_code=str(status.get('stageCode') or 'W1');listed=status.get('containers') if isinstance(status.get('containers'),list) else [];containers=[str(x) for x in listed if str(x)]
                if not containers:
                    candidate=str(status.get('container') or status.get('bridge') or '');containers=[candidate] if candidate else []
                match=re.fullmatch(r'W([1-9][0-9]*)',stage_code.strip().upper())
                if match:
                    generation=int(match.group(1));stage_bridge=f'cloudif-p{num}-w{generation}-preview-web';composite_app=f'cloudif-p{num}-w{generation}-preview-app'
                    if stage_bridge in containers and composite_app not in containers:containers.insert(0,composite_app)
        finally:con.close()
        result={'ok':True,'project':slug,'publicNumber':num,'environment':environment,'stageCode':stage_code,'containers':containers,'secretValuesIncluded':False}
        if 'stack_id' in locals() and stack_id:result['stackId']=stack_id
        return result
    if environment=='homologation':
        row=con.execute("select candidate_number,deploy_number,stage_code,runtime_diff_json from publication_candidates where project_slug=? and status in ('awaiting_homologation','homologated') order by candidate_number desc limit 1",(slug,)).fetchone()
        if not row:con.close();raise RuntimeError('Nenhuma Homologação ativa está disponível para diagnóstico.')
        try:detail=json.loads(row['runtime_diff_json'] or '{}')
        except Exception:detail={}
        deployment_id=str(detail.get('homologationDeploymentId') or '');stage_code=str(row['stage_code'] or ('H'+str(int(row['candidate_number'] or 0))))
        if re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):
            targets=_compose_deployment_runtime_targets(slug,deployment_id);containers=targets['containers']
            con.close();return {'ok':True,'project':slug,'publicNumber':num,'environment':environment,'stageCode':stage_code,'containers':containers,'deploymentId':deployment_id,'serviceTargets':targets['targets'],'secretValuesIncluded':False}
        containers=[f'cloudif-p{num}-d{int(row["deploy_number"] or 0)}-web']
        con.close();return {'ok':True,'project':slug,'publicNumber':num,'environment':environment,'stageCode':stage_code,'containers':containers,'secretValuesIncluded':False}
    row=con.execute("select publication_number,deploy_number,stage_code from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone()
    if not row:con.close();raise RuntimeError('Nenhuma Produção ativa está disponível para diagnóstico.')
    pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,int(row['deploy_number'] or 0))).fetchone();con.close()
    try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
    except Exception:detail={}
    deployment_id=str(detail.get('productionDeploymentId') or detail.get('homologationDeploymentId') or '');publication=int(row['publication_number'] or 0);stage_code=str(row['stage_code'] or ('P'+str(publication)))
    if re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):
        targets=_compose_deployment_runtime_targets(slug,deployment_id);containers=targets['containers']
        return {'ok':True,'project':slug,'publicNumber':num,'environment':environment,'stageCode':stage_code,'containers':containers,'deploymentId':deployment_id,'serviceTargets':targets['targets'],'secretValuesIncluded':False}
    containers=[f'cloudif-p{num}-p{publication}-publication-web']
    return {'ok':True,'project':slug,'publicNumber':num,'environment':environment,'stageCode':stage_code,'containers':containers,'secretValuesIncluded':False}


def recreate_preview(slug,user,source='production'):
    source=str(source or '').strip().lower()
    if source not in {'production','template'}:raise ValueError('Origem de Preview inválida.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project or not _owner_or_admin(con,slug,user):con.close();raise PermissionError('Somente o responsável pelo projeto pode recriar o Preview.')
    num=_number(con,slug);con.close();pc=_publication_config();summary=pc.environment_summary(slug,'preview')
    if not summary.get('valid'):raise RuntimeError('O ambiente Preview possui variáveis obrigatórias pendentes.')
    runtime=pc.execution_environment(slug,int(summary['environmentRevision']),str(summary.get('environmentDigest') or ''),'preview');values=runtime.get('values') or {}
    ku,kt,nt=_clients()
    try:status,data=_post(ku+'/komodo/project/preview/recreate',{'project':slug,'public_number':num,'actor':user.get('username') or 'portal','source':source,'environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest']),'environment_variables':values},kt,timeout=360)
    finally:
        if isinstance(values,dict):values.clear();runtime['values']={}
    if status//100!=2 or not data.get('ok'):raise RuntimeError(_publication_error('preview',data))
    generation=int(data.get('generation') or 1);pstatus,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'preview','number':generation},nt,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
    data.update({'url':_stage_identity(num,'preview',generation)['url'],'stageCode':'W'+str(generation)});return data


def _next_candidate(con,slug):
    a=int(con.execute('select coalesce(max(candidate_number),0) from publication_candidates where project_slug=?',(slug,)).fetchone()[0] or 0)
    b=int(con.execute('select coalesce(max(deploy_number),0) from project_publications where project_slug=?',(slug,)).fetchone()[0] or 0)
    c=int(con.execute("select coalesce(max(candidate_number),0) from publication_jobs where project_slug=? and operation='homologation_candidate'",(slug,)).fetchone()[0] or 0)
    return max(a,b,c)+1


def _create_multiservice_homologation_candidate(slug,num,candidate,actor,progress=None):
    notify=lambda step,msg:progress(step,msg) if progress else None
    notify('snapshot','Selecionando o último build imutável de Homologação.')
    source_preview=_current_multiservice_preview(slug)
    if not source_preview.get('configured') or not source_preview.get('healthy'):raise RuntimeError('Prepare um Preview W1 saudável antes de criar a Homologação.')
    build=_latest_multiservice_build(slug,'homologation');job=str(build['job_id'])
    if str(source_preview.get('archive_sha256') or '')!=str(build.get('archive_sha256') or ''):raise RuntimeError('O build de Homologação não corresponde ao código atualmente validado no Preview W1.')
    pc=_publication_config();summary=pc.environment_summary(slug,'homologation')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Homologação possui variáveis obrigatórias pendentes.')
    notify('deploying','Criando deployment multissserviço imutável de Homologação.')
    trace='portal-h-'+hashlib.sha256((slug+job+str(candidate)).encode()).hexdigest()[:20]
    plan,deployed=_multiservice_deploy(slug,job,'homologation',trace,'H|'+slug+'|'+str(candidate)+'|'+job)
    artifact_id,apps=_multiservice_artifact_identity(plan);deployment_id=str(deployed['deployment_id'])
    bridge=_multiservice_bridge(slug,deployment_id,num,'homologation',candidate,trace+'-bridge')
    notify('https','Preparando URL pública de Homologação.')
    _,_,npm_token=_clients();hstatus,hdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'homologation','number':candidate},npm_token,host='cloudif-publisher.internal',timeout=300)
    if hstatus//100!=2 or not hdata.get('ok'):raise RuntimeError(_publication_error('https',hdata))
    ident=_stage_identity(num,'homologation',candidate)
    if not _external_ok(ident['hostname']):raise RuntimeError('Validação HTTPS externa falhou para '+ident['hostname'])
    diff={'runtimeKind':'multiservice','buildJobId':job,'ref':str(build.get('ref') or ''),'archiveSha256':str(build.get('archive_sha256') or ''),'applications':apps,'secretValuesIncluded':False}
    runtime_meta={'runtimeKind':'multiservice','buildJobId':job,'homologationDeploymentId':deployment_id,'deploymentPlanDigest':str(plan.get('deployment_plan_digest') or ''),'environment':'homologation','dependencies':(plan.get('summary') or {}).get('dependencies') or [],'bridge':str(bridge.get('bridge') or ''),'sourcePreviewId':str(source_preview.get('preview_id') or ''),'sourcePreviewBuildJobId':str(source_preview.get('build_job_id') or ''),'sourcePreviewArchiveSha256':str(source_preview.get('archive_sha256') or ''),'sourcePreviewStageCode':'W1','secretValuesIncluded':False}
    now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    sql="insert into publication_candidates(project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    values=(slug,num,candidate,candidate,1,ident['code'],ident['hostname'],'awaiting_homologation',str(build.get('ref') or ''),str(build.get('archive_sha256') or ''),'multiservice:'+job,artifact_id,json.dumps(diff,ensure_ascii=False),json.dumps(runtime_meta,ensure_ascii=False),int(summary.get('environmentRevision') or 0),str(summary.get('environmentDigest') or ''),actor,now)
    con.execute(sql,values);con.commit();con.close()
    return {'ok':True,'project':slug,'candidateNumber':candidate,'stageCode':ident['code'],'url':ident['url'],'hostname':ident['hostname'],'commit':str(build.get('archive_sha256') or ''),'parentCommit':str(build.get('ref') or ''),'artifactImageId':artifact_id,'previewGeneration':1,'diff':diff,'runtimeDiff':runtime_meta,'environmentRevision':int(summary.get('environmentRevision') or 0),'secretValuesIncluded':False}


def create_homologation_candidate(slug,user,progress=None,candidate_number=None,authorization_checked=False):
    notify=lambda step,msg: progress(step,msg) if progress else None
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    try:
        if authorization_checked:
            # The queued Hn worker revalidates authorization and job identity
            # separately. This flag is for that internal guarded call only.
            project=con.execute('select * from projects where slug=?',(slug,)).fetchone()
        else:
            project=_project_allowed(con,slug,user)
            if project and not _can_homologate(con,slug,user):
                raise PermissionError('homologation_permission_denied')
        if not project:raise PermissionError('Projeto não encontrado ou sem permissão.')
        num=_number(con,slug)
        candidate=int(candidate_number or _next_candidate(con,slug))
        actor=(user.get('username') or 'portal').strip().lower()
    finally:
        con.close()
    if _is_linked_compose_project(slug):return _create_linked_compose_homologation_candidate(slug,num,candidate,actor,progress)
    current_preview=preview_status(slug,user);runtime_kind=str(current_preview.get('runtimeKind') or '')
    if runtime_kind=='multiservice':return _create_multiservice_homologation_candidate(slug,num,candidate,actor,progress)
    generation=int(current_preview.get('generation') or 0);numbered_bridge=f'cloudif-p{num}-w{generation}-preview-web' if generation>0 else ''
    if runtime_kind=='source-linked-preview' or (numbered_bridge and str(current_preview.get('bridge') or current_preview.get('container') or '')==numbered_bridge):
        return _create_preview_runtime_homologation_candidate(slug,num,candidate,actor,user,current_preview,progress)
    notify('snapshot','Congelando código e runtime do Preview.')
    ku,kt,nt=_clients();status,snap=_post(ku+'/komodo/project/preview/snapshot',{'project':slug,'public_number':num,'candidate_number':candidate,'actor':actor},kt,timeout=360)
    if status//100!=2 or not snap.get('ok'):raise RuntimeError(str(snap.get('message') or 'Não foi possível congelar o Preview para homologação.'))
    pc=_publication_config();summary=pc.environment_summary(slug,'homologation')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Homologação possui variáveis obrigatórias pendentes.')
    runtime=pc.execution_environment(slug,int(summary['environmentRevision']),str(summary.get('environmentDigest') or ''),'homologation');values=runtime.get('values') or {}
    payload={'project':slug,'public_number':num,'deploy_number':candidate,'commit':str(snap['commit']),'timeout':HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT,'build_timeout':HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT,'actor':actor,'base_revision':int(snap['baseRevision']),'base_image':str(snap['baseImage']),'base_image_id':str(snap['baseImageId']),'environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest']),'environment_variables':values}
    notify('deploying','Criando candidato imutável de Homologação.')
    try:dstatus,deployed=_post(ku+'/komodo/publication/deploy',payload,kt,timeout=HOMOLOGATION_DEPLOY_HTTP_TIMEOUT)
    finally:
        if isinstance(values,dict):values.clear();runtime['values']={};payload['environment_variables']={}
    if dstatus//100!=2 or not deployed.get('ok'):raise RuntimeError(_publication_error('deploy',deployed))
    notify('https','Preparando URL de Homologação.')
    vstatus,vdata=_post('http://10.62.91.3/version',{'public_number':num,'deploy_number':candidate},nt,host='cloudif-publisher.internal',timeout=300)
    if vstatus//100!=2 or not vdata.get('ok'):raise RuntimeError(_publication_error('https',vdata))
    hstatus,hdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'homologation','number':candidate},nt,host='cloudif-publisher.internal',timeout=300)
    if hstatus//100!=2 or not hdata.get('ok'):raise RuntimeError(_publication_error('https',hdata))
    ident=_stage_identity(num,'homologation',candidate);now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    con.execute('''insert into publication_candidates(project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(slug,num,candidate,candidate,int(snap.get('previewGeneration') or 1),ident['code'],ident['hostname'],'awaiting_homologation',str(snap.get('parentCommit') or ''),str(snap['commit']),str(deployed.get('expected_image') or ''),str(deployed.get('publicationImageId') or ''),json.dumps(snap.get('diff') or {},ensure_ascii=False),json.dumps(snap.get('runtimeDiff') or {},ensure_ascii=False),int(runtime['environmentRevision']),str(runtime['environmentDigest']),actor,now));con.commit();con.close()
    return {'ok':True,'project':slug,'candidateNumber':candidate,'stageCode':ident['code'],'url':ident['url'],'hostname':ident['hostname'],'commit':str(snap['commit']),'parentCommit':str(snap.get('parentCommit') or ''),'artifactImageId':str(deployed.get('publicationImageId') or ''),'previewGeneration':int(snap.get('previewGeneration') or 1),'diff':snap.get('diff') or {},'runtimeDiff':snap.get('runtimeDiff') or {},'environmentRevision':int(runtime['environmentRevision']),'secretValuesIncluded':False}


def homologate_candidate(slug,candidate_number,user,decision='approved',note=''):
    decision=str(decision or '').strip().lower();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _can_homologate(con,slug,user):con.close();raise PermissionError('Você não está autorizado a homologar este projeto.')
    row=con.execute('select * from publication_candidates where project_slug=? and candidate_number=?',(slug,int(candidate_number))).fetchone()
    if not row:con.close();raise ValueError('Candidato não encontrado.')
    if row['status'] not in ('awaiting_homologation','homologated'):con.close();raise ValueError('Este candidato não está aguardando homologação.')
    actor=(user.get('username') or 'portal').strip().lower();now=_now()
    if decision=='rejected':con.execute("update publication_candidates set status='rejected',rejected_by=?,rejected_at=?,rejection_note=? where id=?",(actor,now,str(note or '')[:1000],row['id']))
    elif decision=='approved':con.execute("update publication_candidates set status='homologated',homologated_by=?,homologated_at=?,rejected_by='',rejected_at=null,rejection_note='' where id=?",(actor,now,row['id']))
    else:con.close();raise ValueError('Decisão de homologação inválida.')
    con.commit();con.close();return {'ok':True,'project':slug,'candidateNumber':int(candidate_number),'status':'rejected' if decision=='rejected' else 'homologated','actor':actor}


def _next_publication(con,slug):
    values=[
      int(con.execute('select coalesce(max(publication_number),0) from production_releases where project_slug=?',(slug,)).fetchone()[0] or 0),
      int(con.execute("select coalesce(max(deploy_number),0) from project_publications where project_slug=? and status='published'",(slug,)).fetchone()[0] or 0),
      int(con.execute("select coalesce(max(publication_number),0) from publication_jobs where project_slug=? and operation='production_release' and publication_number>0",(slug,)).fetchone()[0] or 0),
      int(con.execute('select coalesce(max(publication_number),0) from production_activation_requests where project_slug=?',(slug,)).fetchone()[0] or 0),
      int(con.execute('select coalesce(max(publication_number),0) from publication_number_reservations where project_slug=?',(slug,)).fetchone()[0] or 0),
    ]
    return max(values)+1


def _reserve_publication_number(con,slug,candidate_number,publication_number=None):
    candidate_number=int(candidate_number);now=_now();own=not con.in_transaction
    try:
        if own:con.execute('begin immediate')
        existing=con.execute('select publication_number from publication_number_reservations where project_slug=? and candidate_number=?',(slug,candidate_number)).fetchone()
        if existing:
            publication=int(existing[0])
            if publication_number and int(publication_number)!=publication:raise RuntimeError('A candidata já possui outro número P reservado.')
        else:
            publication=int(publication_number or _next_publication(con,slug))
            owner=con.execute('select candidate_number from publication_number_reservations where project_slug=? and publication_number=?',(slug,publication)).fetchone()
            if owner and int(owner[0])!=candidate_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' já está reservada por outra candidata.')
            release=con.execute('select candidate_number from production_releases where project_slug=? and publication_number=?',(slug,publication)).fetchone()
            if release and int(release[0])!=candidate_number:raise RuntimeError('Conflito de nome: P'+str(publication)+' já pertence a outra candidata.')
            job=con.execute("select candidate_number from publication_jobs where project_slug=? and operation='production_release' and publication_number=? and candidate_number<>? order by id desc limit 1",(slug,publication,candidate_number)).fetchone()
            if job:raise RuntimeError('Conflito de nome: P'+str(publication)+' já foi usada por outro job de publicação.')
            req=con.execute('select candidate_number from production_activation_requests where project_slug=? and publication_number=? and candidate_number<>? order by created_at desc limit 1',(slug,publication,candidate_number)).fetchone()
            if req:raise RuntimeError('Conflito de nome: P'+str(publication)+' já foi reservada por outra solicitação.')
            con.execute("insert into publication_number_reservations(project_slug,candidate_number,publication_number,status,created_at,updated_at) values(?,?,?,'reserved',?,?)",(slug,candidate_number,publication,now,now))
        if own:con.commit()
        return publication
    except Exception:
        if own and con.in_transaction:con.rollback()
        raise


def _publication_for_candidate(con,slug,candidate_number):
    candidate_number=int(candidate_number)
    reserved=con.execute('select publication_number from publication_number_reservations where project_slug=? and candidate_number=?',(slug,candidate_number)).fetchone()
    if reserved:return int(reserved[0])
    row=con.execute('select published_publication_number from publication_candidates where project_slug=? and candidate_number=?',(slug,candidate_number)).fetchone()
    if row and int(row[0] or 0)>0:return int(row[0])
    row=con.execute("select publication_number from publication_jobs where project_slug=? and candidate_number=? and operation='production_release' and publication_number>0 order by id desc limit 1",(slug,candidate_number)).fetchone()
    if row:
        publication=int(row[0]);owner=con.execute('select candidate_number from production_releases where project_slug=? and publication_number=?',(slug,publication)).fetchone()
        if not owner or int(owner[0])==candidate_number:return publication
    row=con.execute('select publication_number from production_activation_requests where project_slug=? and candidate_number=? order by publication_number desc limit 1',(slug,candidate_number)).fetchone()
    if row:
        publication=int(row[0]);owner=con.execute('select candidate_number from production_releases where project_slug=? and publication_number=?',(slug,publication)).fetchone()
        if not owner or int(owner[0])==candidate_number:return publication
    return _next_publication(con,slug)


def _publish_multiservice_homologated_candidate(slug,candidate,project,publication,alias,actor,progress=None):
    notify=lambda step,msg:progress(step,msg) if progress else None
    meta=_candidate_runtime_metadata(candidate);job=str(meta.get('buildJobId') or '')
    if meta.get('runtimeKind')!='multiservice' or not re.fullmatch(r'build_[a-f0-9]{24}',job):raise RuntimeError('Metadados multissserviço do candidato estão incompletos.')
    pc=_publication_config();summary=pc.environment_summary(slug,'production')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Produção possui variáveis obrigatórias pendentes.')
    notify('production','Subindo em Produção exatamente os artefatos homologados.')
    trace='portal-p-'+hashlib.sha256((slug+job+str(publication)).encode()).hexdigest()[:20]
    plan,deployed=_multiservice_deploy(slug,job,'production',trace,'P|'+slug+'|'+str(publication)+'|'+job)
    artifact_id,apps=_multiservice_artifact_identity(plan)
    if not hmac.compare_digest(artifact_id,str(candidate['artifact_image_id'] or '')):raise RuntimeError('O conjunto de imagens de Produção difere do candidato homologado.')
    deployment_id=str(deployed['deployment_id']);num=int(candidate['public_number'])
    bridge=_multiservice_bridge(slug,deployment_id,num,'publication',publication,trace+'-bridge')
    _,_,npm_token=_clients();notify('https','Preparando URL P e domínio estável.')
    pstage,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':publication},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstage//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
    ident=_stage_identity(num,'publication',publication)
    if not _external_ok(ident['hostname']):raise RuntimeError('Validação HTTPS externa falhou para '+ident['hostname'])
    activation=_multiservice_activate_bridge(slug,num,publication,trace+'-activate')
    pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':int(candidate['deploy_number']),'alias':alias},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not publisher.get('ok'):raise RuntimeError(_publication_error('https',publisher))
    stable=f'{num}.cloudiff.duckdns.org'
    if not _external_ok(stable):raise RuntimeError('Validação da URL estável falhou após ativação.')
    now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    sql="insert into production_releases(project_slug,public_number,publication_number,candidate_number,deploy_number,stage_code,hostname,stable_hostname,artifact_image_id,status,is_active,environment_revision,environment_digest,created_by,created_at,published_at) values(?,?,?,?,?,?,?,?,?,'published',1,?,?,?,?,?)"
    con.execute('update production_releases set is_active=0 where project_slug=?',(slug,))
    con.execute(sql,(slug,num,publication,int(candidate['candidate_number']),int(candidate['deploy_number']),ident['code'],ident['hostname'],stable,artifact_id,int(summary.get('environmentRevision') or 0),str(summary.get('environmentDigest') or ''),actor,now,now))
    detail={'runtimeKind':'multiservice','stageCode':ident['code'],'publicationHostname':ident['hostname'],'candidateNumber':int(candidate['candidate_number']),'publicationNumber':publication,'artifactImageId':artifact_id,'buildJobId':job,'homologationDeploymentId':str(meta.get('homologationDeploymentId') or ''),'productionDeploymentId':deployment_id,'applications':apps,'bridge':str(bridge.get('bridge') or ''),'activeAlias':str(activation.get('active_alias') or ''),'sameArtifactAsHomologation':True,'secretValuesIncluded':False}
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,));existing=con.execute('select id from project_publications where project_slug=? and deploy_number=?',(slug,int(candidate['deploy_number']))).fetchone()
    if existing:
        con.execute("update project_publications set version=?,commit_sha=?,stable_hostname=?,version_hostname=?,status='published',is_active=1,published_at=?,message=?,detail_json=? where id=?",(ident['code'],str(candidate['commit_sha']),stable,ident['hostname'],now,'Publicada após homologação '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False),existing['id']))
    else:
        sql_pub="insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json) values(?,?,?,?,?,?,?,'published',1,?,?,?,?,?)"
        con.execute(sql_pub,(slug,num,int(candidate['deploy_number']),ident['code'],str(candidate['commit_sha']),stable,ident['hostname'],actor,now,now,'Publicada após homologação '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False)))
    con.execute("update publication_candidates set status='published',published_publication_number=? where id=?",(publication,candidate['id']))
    cols={x[1] for x in con.execute('pragma table_info(projects)')};updates={k:v for k,v in {'status':'published','komodo_status':'multiservice','updated_at':now}.items() if k in cols}
    if updates:con.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
    tenant=str(project['tenant'] if 'tenant' in project.keys() else '');con.commit();con.close();queued=_enqueue_membership_reconcile(slug,actor,tenant)
    return {'ok':True,'project':slug,'candidateNumber':int(candidate['candidate_number']),'publicationNumber':publication,'stageCode':ident['code'],'url':ident['url'],'stableUrl':'https://'+stable+'/','aliasUrl':('https://'+alias+'.cloudiff.duckdns.org/' if alias else ''),'artifactImageId':artifact_id,'sameArtifactAsHomologation':True,'environmentRevision':int(summary.get('environmentRevision') or 0),'membership':{'ok':True,'mode':'multiservice'},'reconcile':queued,'secretValuesIncluded':False}


def publish_homologated_candidate(slug,candidate_number,user,progress=None,publication_number=None,authorization_checked=False):
    notify=lambda step,msg:progress(step,msg) if progress else None
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=con.execute('select * from projects where slug=?',(slug,)).fetchone() if authorization_checked else _project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    if not authorization_checked and not _can_publish(con,slug,user):con.close();raise PermissionError('Você não está autorizado a publicar este projeto em Produção.')
    candidate=con.execute('select * from publication_candidates where project_slug=? and candidate_number=?',(slug,int(candidate_number))).fetchone()
    if not candidate or candidate['status']!='homologated':con.close();raise RuntimeError('O candidato precisa estar homologado antes da publicação.')
    publication=int(publication_number or _next_publication(con,slug));num=int(candidate['public_number']);alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();alias=str(alias_row[0]) if alias_row else '';actor=(user.get('username') or 'portal').strip().lower();con.close()
    candidate_runtime=_candidate_runtime_metadata(candidate)
    if candidate_runtime.get('runtimeKind')=='compose-snapshot':return _publish_linked_compose_homologated_candidate(slug,candidate,project,publication,alias,actor,progress)
    if candidate_runtime.get('runtimeKind')=='multiservice':return _publish_multiservice_homologated_candidate(slug,candidate,project,publication,alias,actor,progress)
    pc=_publication_config();summary=pc.environment_summary(slug,'production')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Produção possui variáveis obrigatórias pendentes.')
    runtime=pc.execution_environment(slug,int(summary['environmentRevision']),str(summary.get('environmentDigest') or ''),'production');values=runtime.get('values') or {};ku,kt,nt=_clients();notify('production','Subindo exatamente o artefato homologado em Produção.')
    payload={'project':slug,'public_number':num,'deploy_number':int(candidate['deploy_number']),'candidate_number':int(candidate_number),'publication_number':publication,'artifact_image_id':str(candidate['artifact_image_id']),'actor':actor,'environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest']),'environment_variables':values}
    try:rstatus,released=_post(ku+'/komodo/publication/release',payload,kt,timeout=300)
    finally:
        if isinstance(values,dict):values.clear();runtime['values']={};payload['environment_variables']={}
    if rstatus//100!=2 or not released.get('ok'):raise RuntimeError(str(released.get('message') or _publication_error('promote',released)))
    if not str(released.get('artifactImageId') or '') or str(released.get('artifactImageId'))!=str(candidate['artifact_image_id']):raise RuntimeError('O digest publicado não corresponde ao artefato homologado.')
    notify('https','Ativando URL de Publicação e domínio estável.')
    pstage,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':publication},nt,host='cloudif-publisher.internal',timeout=300)
    if pstage//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
    pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':int(candidate['deploy_number']),'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not publisher.get('ok'):raise RuntimeError(_publication_error('https',publisher))
    ident=_stage_identity(num,'publication',publication);stable=f'{num}.cloudiff.duckdns.org';now=_now();con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    con.execute('update production_releases set is_active=0 where project_slug=?',(slug,));con.execute('''insert into production_releases(project_slug,public_number,publication_number,candidate_number,deploy_number,stage_code,hostname,stable_hostname,artifact_image_id,status,is_active,environment_revision,environment_digest,created_by,created_at,published_at) values(?,?,?,?,?,?,?,?,?,'published',1,?,?,?,?,?)''',(slug,num,publication,int(candidate_number),int(candidate['deploy_number']),ident['code'],ident['hostname'],stable,str(candidate['artifact_image_id']),int(runtime['environmentRevision']),str(runtime['environmentDigest']),actor,now,now))
    existing=con.execute('select id from project_publications where project_slug=? and deploy_number=?',(slug,int(candidate['deploy_number']))).fetchone();detail={'stageCode':ident['code'],'publicationHostname':ident['hostname'],'candidateNumber':int(candidate_number),'artifactImageId':str(candidate['artifact_image_id']),'sameArtifactAsHomologation':True,'secretValuesIncluded':False}
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    if existing:con.execute("update project_publications set status='published',is_active=1,published_at=?,message=?,detail_json=? where id=?",(now,'Publicada após homologação '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False),existing['id']))
    else:con.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json) values(?,?,?,?,?,?,?,'published',1,?,?,?,?,?)''',(slug,num,int(candidate['deploy_number']),ident['code'],str(candidate['commit_sha']),stable,f'{num}-d{int(candidate["deploy_number"])}.cloudiff.duckdns.org',actor,now,now,'Publicada após homologação '+str(candidate['stage_code']),json.dumps(detail,ensure_ascii=False)))
    con.execute("update publication_candidates set status='published',published_publication_number=? where id=?",(publication,candidate['id']));access=_project_access_snapshot(con,slug);tenant=str(project['tenant'] if 'tenant' in project.keys() else '');con.commit();con.close()
    membership=_reconcile_publication_members(ku,kt,slug,access);queued=_enqueue_membership_reconcile(slug,actor,tenant)
    return {'ok':True,'project':slug,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':ident['code'],'url':ident['url'],'stableUrl':'https://'+stable+'/','aliasUrl':('https://'+alias+'.cloudiff.duckdns.org/' if alias else ''),'artifactImageId':str(candidate['artifact_image_id']),'sameArtifactAsHomologation':True,'environmentRevision':int(runtime['environmentRevision']),'membership':membership,'reconcile':queued,'secretValuesIncluded':False}




def _historical_release_runtime_state(slug,row,detail):
    if int(row.get('is_active') or 0)==1:
        return {'state':'active','online':True,'healthy':True,'canStart':False,'canStop':False}
    kind=str((detail or {}).get('runtimeKind') or '')
    if kind in {'multiservice','compose-snapshot'}:
        deployment_id=str((detail or {}).get('productionDeploymentId') or '')
        if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):return {'state':'offline','online':False,'healthy':False,'canStart':False,'canStop':False,'reason':'runtime-metadata-missing'}
        try:
            base,token=_executor_runtime_client();status,data=_bearer_json('GET',base+'/v1/deployments/'+urllib.parse.quote(deployment_id,safe=''),token,timeout=15)
            if status!=200 or not isinstance(data,dict) or data.get('ok') is not True:return {'state':'attention','online':False,'healthy':False,'canStart':True,'canStop':False,'deploymentId':deployment_id}
            runtime_status=str(data.get('status') or '')
            online=runtime_status in {'rollback_ready','running'}
            return {'state':'online' if online else ('deleted' if runtime_status in {'removed','deleted'} else 'offline'),'online':online,'healthy':online,'canStart':not online,'canStop':online,'canDelete':(not online and runtime_status not in {'removed','deleted'} and kind=='compose-snapshot' and bool((detail or {}).get('composeSnapshotId'))),'deploymentId':deployment_id,'runtimeStatus':runtime_status}
        except Exception:
            return {'state':'attention','online':False,'healthy':False,'canStart':True,'canStop':False,'deploymentId':deployment_id}
    try:
        ku,kt,_=_clients();status,data=_post(ku+'/komodo/publication/release/status',{'project':slug,'public_number':int(row.get('public_number') or 0),'publication_number':int(row.get('publication_number') or 0)},kt,timeout=30)
        if status//100==2 and isinstance(data,dict) and data.get('ok') is True:
            online=bool(data.get('online'));healthy=bool(data.get('healthy'));is_active=bool(data.get('isActive'));exists=bool(data.get('exists',True))
            return {'state':'online' if online else 'offline','online':online,'healthy':healthy,'canStart':not online,'canStop':online,'canDelete':(not online and not is_active),'legacy':True,'container':str(data.get('container') or ''),'exists':exists,'isActive':is_active,'deleteMode':'legacy-final'}
    except Exception:pass
    return {'state':'offline','online':False,'healthy':False,'canStart':True,'canStop':False,'legacy':True}


def historical_publication_prepare(slug,publication_number,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _owner_or_admin(con,slug,user):con.close();raise PermissionError('Somente o responsável pelo projeto pode subir uma Produção histórica.')
    row=con.execute("select * from production_releases where project_slug=? and publication_number=? and status='published'",(slug,int(publication_number))).fetchone()
    if not row:con.close();raise ValueError('Publicação P não encontrada.')
    if int(row['is_active'] or 0)==1:con.close();raise ValueError('Esta publicação já está ativa no endereço principal.')
    pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,int(row['deploy_number']))).fetchone();con.close()
    try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
    except Exception:detail={}
    num=int(row['public_number']);publication=int(row['publication_number']);trace='portal-history-prepare-'+hashlib.sha256((slug+str(publication)).encode()).hexdigest()[:20]
    _,_,npm_token=_clients()
    if detail.get('runtimeKind') in {'multiservice','compose-snapshot'}:
        deployment_id=str(detail.get('productionDeploymentId') or '')
        if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('A publicação histórica não possui deployment reativável.')
        digest=str(row['environment_digest'] or '')
        if not re.fullmatch(r'[a-f0-9]{64}',digest):digest=str(detail.get('snapshotDigest') or '')
        if not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('A publicação histórica não possui digest de ambiente válido.')
        try:
            _multiservice_reactivate(slug,deployment_id,'prepare',digest,trace)
        except RuntimeError:
            if str(detail.get('runtimeKind') or '')!='compose-snapshot':raise
            snapshot_id=str(detail.get('composeSnapshotId') or '');snapshot_digest=str(detail.get('snapshotDigest') or '')
            if not re.fullmatch(r'snap_[a-f0-9]{24}',snapshot_id) or not re.fullmatch(r'[a-f0-9]{64}',snapshot_digest):raise
            deployed=_rehydrate_historical_compose_runtime(slug,publication,row,detail);deployment_id=str(deployed.get('deployment_id') or '')
            detail['productionDeploymentId']=deployment_id;detail['rehydratedAt']=_now();detail['rehydratedFromSnapshot']=snapshot_id;detail['rehydratedThroughHomologation']=True
            con=sqlite3.connect(DB);_ensure_schema(con);con.execute('update project_publications set detail_json=? where project_slug=? and deploy_number=?',(json.dumps(detail,ensure_ascii=False),slug,int(row['deploy_number'])));con.commit();con.close()
        _multiservice_bridge(slug,deployment_id,num,'publication',publication,trace+'-bridge')
    else:
        ku,kt,_=_clients();status,data=_post(ku+'/komodo/publication/release/prepare',{'project':slug,'public_number':num,'publication_number':publication},kt,timeout=180)
        if status//100!=2 or not data.get('ok'):raise RuntimeError(_publication_error('promote',data))
    pstage,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':publication},npm_token,host='cloudif-publisher.internal',timeout=300)
    if pstage//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
    if not _external_ok(str(row['hostname'])):raise RuntimeError('A URL versionada da publicação histórica não ficou saudável.')
    _rm.project_changed(slug,'historical-production-started')
    return {'ok':True,'project':slug,'publicationNumber':publication,'stageCode':str(row['stage_code'] or ('P'+str(publication))),'url':'https://'+str(row['hostname'])+'/','runtimeState':'online','stableActivated':False,'containersRecreated':False,'secretValuesIncluded':False}


def historical_publication_stop(slug,publication_number,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _owner_or_admin(con,slug,user):con.close();raise PermissionError('Somente o responsável pelo projeto pode desligar uma Produção histórica.')
    row=con.execute("select * from production_releases where project_slug=? and publication_number=? and status='published'",(slug,int(publication_number))).fetchone()
    if not row:con.close();raise ValueError('Publicação P não encontrada.')
    if int(row['is_active'] or 0)==1:con.close();raise ValueError('A Produção ativa não pode ser desligada por esta ação.')
    pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,int(row['deploy_number']))).fetchone();con.close()
    try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
    except Exception:detail={}
    num=int(row['public_number']);publication=int(row['publication_number']);trace='portal-history-stop-'+hashlib.sha256((slug+str(publication)).encode()).hexdigest()[:20]
    _,_,npm_token=_clients();_publisher_delete_stage(num,'publication',publication,npm_token)
    if detail.get('runtimeKind') in {'multiservice','compose-snapshot'}:
        deployment_id=str(detail.get('productionDeploymentId') or '')
        if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('A publicação histórica não possui deployment reativável.')
        digest=str(row['environment_digest'] or '')
        if not re.fullmatch(r'[a-f0-9]{64}',digest):digest=str(detail.get('snapshotDigest') or '')
        if not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('A publicação histórica não possui digest de ambiente válido.')
        try:_multiservice_deactivate_bridge(slug,deployment_id,'publication',trace+'-bridge')
        except Exception:pass
        _multiservice_reactivate(slug,deployment_id,'abort',digest,trace+'-abort')
    else:
        _legacy_publication_deactivate(slug,num,publication)
    _rm.project_changed(slug,'historical-production-stopped')
    return {'ok':True,'project':slug,'publicationNumber':publication,'stageCode':str(row['stage_code'] or ('P'+str(publication))),'runtimeState':'offline','stableActivated':False,'resourcesPreserved':True,'secretValuesIncluded':False}


def historical_publication_delete_runtime(slug,publication_number,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _owner_or_admin(con,slug,user):con.close();raise PermissionError('Somente o responsável pelo projeto pode excluir containers históricos.')
    row=con.execute("select * from production_releases where project_slug=? and publication_number=? and status='published'",(slug,int(publication_number))).fetchone()
    if not row:con.close();raise ValueError('Publicação P não encontrada.')
    if int(row['is_active'] or 0)==1:con.close();raise ValueError('A Produção ativa não pode ter seus containers excluídos.')
    pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,int(row['deploy_number']))).fetchone();con.close()
    try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
    except Exception:detail={}
    num=int(row['public_number']);publication=int(row['publication_number']);_,_,npm_token=_clients();_publisher_delete_stage(num,'publication',publication,npm_token)
    kind=str(detail.get('runtimeKind') or '');snapshot_id='';deployment_id='';snapshot_preserved=False;image_preserved=False
    if kind=='compose-snapshot':
        snapshot_id=str(detail.get('composeSnapshotId') or '');deployment_id=str(detail.get('productionDeploymentId') or '')
        if not re.fullmatch(r'snap_[a-f0-9]{24}',snapshot_id) or not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):raise RuntimeError('A publicação não possui snapshot/deployment reidratável válido.')
        try:_multiservice_deactivate_bridge(slug,deployment_id,'publication','portal-history-delete-'+hashlib.sha256((slug+str(publication)).encode()).hexdigest()[:20])
        except Exception:pass
        removed=_remove_compose_runtime(deployment_id);snapshot_preserved=True
        detail['runtimeDeletedDeploymentId']=deployment_id;detail['runtimeDeletedSnapshotId']=snapshot_id;detail['runtimeDeleteMode']='compose-snapshot'
    else:
        ku,kt,_=_clients();status,data=_post(ku+'/komodo/publication/release/delete',{'project':slug,'public_number':num,'publication_number':publication,'actor':user.get('username') or 'portal'},kt,timeout=90)
        if status//100!=2 or data.get('ok') is not True:raise RuntimeError(str(data.get('message') or data.get('error') or 'Falha ao excluir publicação legada.'))
        removed={'containersRemoved':int(data.get('containersRemoved') or 0),'volumesRemoved':int(data.get('volumesRemoved') or 0)};image_preserved=bool(data.get('imagePreserved'))
        detail['runtimeDeletedLegacyContainer']=str(data.get('container') or '');detail['runtimeDeletedLegacyImageId']=str(data.get('imageId') or '');detail['runtimeDeleteMode']='legacy-final'
    detail['runtimeDeletedAt']=_now()
    con=sqlite3.connect(DB);_ensure_schema(con);con.execute('begin immediate');con.execute("update project_publications set detail_json=?,status='archived',is_active=0 where project_slug=? and deploy_number=?",(json.dumps(detail,ensure_ascii=False),slug,int(row['deploy_number'])));con.execute("update production_releases set status='archived',is_active=0 where project_slug=? and publication_number=?",(slug,publication));con.commit();con.close()
    _rm.project_changed(slug,'historical-production-deleted')
    return {'ok':True,'project':slug,'publicationNumber':publication,'stageCode':str(row['stage_code'] or ('P'+str(publication))),'runtimeState':'deleted','historyRemoved':True,'containersRemoved':int(removed.get('containersRemoved') or 0),'volumesRemoved':int(removed.get('volumesRemoved') or 0),'snapshotPreserved':snapshot_preserved,'snapshotId':snapshot_id,'imagePreserved':image_preserved,'canRehydrate':False,'stableActivated':False,'secretValuesIncluded':False}

def release_flow_status(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not (_project_allowed(con,slug,user) or _can_homologate(con,slug,user)):con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    num=_number(con,slug);candidates=[dict(x) for x in con.execute('select * from publication_candidates where project_slug=? order by candidate_number desc limit 20',(slug,)).fetchall()];releases=[dict(x) for x in con.execute("select * from production_releases where project_slug=? and status='published' order by publication_number desc limit 20",(slug,)).fetchall()];activations=[dict(x) for x in con.execute('select * from production_activation_requests where project_slug=? order by publication_number desc limit 20',(slug,)).fetchall()];hom=[str(x['username']) for x in con.execute('select username from project_homologators where project_slug=? order by username',(slug,)).fetchall()];owner=_project_owner(con,slug);permission_state=publication_permissions.snapshot(con,slug,user);can_submit=bool(_project_allowed(con,slug,user));can_homologate=_can_homologate(con,slug,user);can_publish=_can_publish(con,slug,user);is_owner=bool((user.get('username') or '').strip().lower()==owner);is_admin=publication_permissions.is_admin(user);is_professor=publication_permissions.is_professor(user)
    try:
        from cloudif_project_environment_web import authorization
        can_write=bool(authorization(slug,user.get('username') or '',user.get('groups') or []).get('canWrite'))
    except Exception:
        can_write=bool(user.get('admin') or (user.get('username') or '').strip().lower()==owner)
    jobrow=con.execute("select id,status,step,message,operation,candidate_number,publication_number,approval_id,created_at,started_at,finished_at from publication_jobs where project_slug=? order by id desc limit 1",(slug,)).fetchone();legacy=con.execute("select * from project_publications where project_slug=? and status='published' and is_active=1 order by id desc limit 1",(slug,)).fetchone();alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();primary_hostname=(str(alias_row['alias'])+'.cloudiff.duckdns.org') if alias_row and str(alias_row['alias'] or '') else (str(next((x.get('stable_hostname') for x in releases if int(x.get('is_active') or 0)==1),'')) or (str(legacy['stable_hostname']) if legacy else ''))
    publication_details={}
    for item in con.execute("select deploy_number,detail_json from project_publications where project_slug=? and status='published' order by id desc",(slug,)).fetchall():
        dep=int(item['deploy_number'] or 0)
        if dep in publication_details:continue
        try:detail=json.loads(item['detail_json'] or '{}')
        except Exception:detail={}
        if isinstance(detail,dict) and detail.get('runtimeKind') in {'multiservice','compose-snapshot'}:
            publication_details[dep]={k:detail.get(k) for k in ('runtimeKind','buildJobId','composeSnapshotId','snapshotDigest','sourceCommit','homologationDeploymentId','productionDeploymentId','bridge','activeAlias','sameArtifactAsHomologation','sameSnapshotAsHomologation','secretValuesIncluded')}
            apps=detail.get('applications') or []
            publication_details[dep]['applications']=[{k:a.get(k) for k in ('service','imageId','applicationDigest')} for a in apps if isinstance(a,dict)][:20]
    con.close()
    release_runtime_states={}
    for release in releases:
        dep=int(release.get('deploy_number') or 0);release_runtime_states[int(release.get('publication_number') or 0)]=_historical_release_runtime_state(slug,release,publication_details.get(dep,{}))
    preview={}
    try:preview=preview_status(slug,user)
    except Exception as exc:preview={'ok':False,'configured':False,'error':type(exc).__name__}
    def safe_candidate(row):
        out={k:row.get(k) for k in ('candidate_number','deploy_number','preview_generation','stage_code','hostname','status','parent_commit','commit_sha','artifact_image_id','environment_revision','created_by','created_at','homologated_by','homologated_at','rejected_by','rejected_at','rejection_note','published_publication_number')};out['url']='https://'+str(row.get('hostname') or '')+'/' if row.get('hostname') else ''
        try:out['diff']=json.loads(row.get('diff_json') or '{}')
        except Exception:out['diff']={}
        try:out['runtimeDiff']=json.loads(row.get('runtime_diff_json') or '{}')
        except Exception:out['runtimeDiff']={}
        return out
    result={'ok':True,'project':slug,'publicNumber':num,'preview':preview,'candidates':[safe_candidate(x) for x in candidates],'releases':[{**{k:x.get(k) for k in ('publication_number','candidate_number','deploy_number','stage_code','hostname','stable_hostname','artifact_image_id','status','is_active','environment_revision','created_by','created_at','published_at')},'url':'https://'+str(x.get('hostname') or '')+'/' if x.get('hostname') else '','stableUrl':'https://'+str(x.get('stable_hostname') or '')+'/' if x.get('stable_hostname') else '','runtime':publication_details.get(int(x.get('deploy_number') or 0),{}),'runtimeState':release_runtime_states.get(int(x.get('publication_number') or 0),{'state':'offline','online':False,'healthy':False})} for x in releases],'activationRequests':[{k:x.get(k) for k in ('candidate_number','publication_number','activation_digest','approval_id','requested_by','status','created_at','updated_at')} for x in activations],'job':dict(jobrow) if jobrow else None,'homologators':hom,'owner':owner,'canSubmitHomologation':can_submit,'canHomologate':can_homologate,'canPublish':can_publish,'canManagePermissions':bool(permission_state.get('canManagePermissions')),'permissionUsers':permission_state.get('users') or [],'permissionPolicy':permission_state.get('policy') or {},'isAdmin':is_admin,'isProfessor':is_professor,'isOwner':is_owner,'canWrite':can_write,'primaryHostname':primary_hostname,'primaryUrl':('https://'+primary_hostname+'/' if primary_hostname else ''),'secretValuesIncluded':False}
    if not releases and legacy:result['legacyProduction']={'deploy_number':int(legacy['deploy_number']),'stage_code':'D'+str(int(legacy['deploy_number'])),'url':'https://'+str(legacy['version_hostname'])+'/' if legacy['version_hostname'] else 'https://'+str(legacy['stable_hostname'])+'/','stableUrl':'https://'+str(legacy['stable_hostname'])+'/','artifact_image_id':'','status':'published','is_active':1,'legacy':True}
    return result


def rollback_publication(slug,publication_number,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not _owner_or_admin(con,slug,user):con.close();raise PermissionError('Somente o responsável pelo projeto pode executar rollback.')
    row=con.execute("select * from production_releases where project_slug=? and publication_number=? and status='published'",(slug,int(publication_number))).fetchone()
    if not row:con.close();raise ValueError('Publicação P não encontrada.')
    alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();alias=str(alias_row[0]) if alias_row else '';primary_host=(alias+'.cloudiff.duckdns.org') if alias else str(row['stable_hostname'])
    if int(row['is_active'] or 0)==1:
        result={'ok':True,'project':slug,'publicationNumber':int(publication_number),'stageCode':str(row['stage_code'] or ('P'+str(int(publication_number)))),'stableUrl':'https://'+primary_host+'/','numericStableUrl':'https://'+str(row['stable_hostname'])+'/','idempotent':True,'alreadyActive':True}
        con.close();return result
    num=int(row['public_number']);dep=int(row['deploy_number'])
    pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,dep)).fetchone()
    current=con.execute("select * from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone()
    current_pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,int(current['deploy_number'])),).fetchone() if current else None
    con.close();ku,kt,nt=_clients();detail={};current_detail={}
    try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
    except Exception:detail={}
    state=_historical_release_runtime_state(slug,dict(row),detail)
    if not (state.get('online') and state.get('healthy')):
        historical_publication_prepare(slug,int(publication_number),user)
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,dep)).fetchone();con.close()
        try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
        except Exception:detail={}
    try:current_detail=json.loads(current_pubrow['detail_json'] or '{}') if current_pubrow else {}
    except Exception:current_detail={}
    if detail.get('runtimeKind') in {'multiservice','compose-snapshot'}:
        target_dep=str(detail.get('productionDeploymentId') or '')
        if not re.fullmatch(r'dep_[a-f0-9]{24}',target_dep):raise RuntimeError('A publicação histórica não possui deployment de Produção reativável.')
        target_digest=str(row['environment_digest'] or '')
        if not re.fullmatch(r'[a-f0-9]{64}',target_digest):target_digest=str(detail.get('snapshotDigest') or '')
        if not re.fullmatch(r'[a-f0-9]{64}',target_digest):raise RuntimeError('A publicação histórica não possui digest de ambiente válido para rollback.')
        current_dep=str(current_detail.get('productionDeploymentId') or '') if current else ''
        current_number=int(current['publication_number']) if current else 0
        current_deploy=int(current['deploy_number']) if current else 0
        current_digest=str(current['environment_digest'] or '') if current else ''
        if current and not re.fullmatch(r'[a-f0-9]{64}',current_digest):current_digest=str(current_detail.get('snapshotDigest') or '')
        trace='portal-rollback-'+hashlib.sha256((slug+str(publication_number)+target_dep).encode()).hexdigest()[:20]
        prepared=False;switched=False
        try:
            _multiservice_reactivate(slug,target_dep,'prepare',target_digest,trace+'-prepare');prepared=True
            _multiservice_bridge(slug,target_dep,num,'publication',int(publication_number),trace+'-bridge')
            pstage,pdata=_post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':int(publication_number)},nt,host='cloudif-publisher.internal',timeout=300)
            if pstage//100!=2 or not pdata.get('ok'):raise RuntimeError(_publication_error('https',pdata))
            if not _external_ok(str(row['hostname'])):raise RuntimeError('A URL versionada da publicação histórica não ficou saudável.')
            _multiservice_activate_bridge(slug,num,int(publication_number),trace+'-activate')
            pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
            if pstatus//100!=2 or not publisher.get('ok'):raise RuntimeError(_publication_error('https',publisher))
            switched=True
            if not _external_ok(primary_host):raise RuntimeError('URL principal falhou após rollback.')
            _multiservice_reactivate(slug,target_dep,'commit',target_digest,trace+'-commit')
            if current_dep and current_dep!=target_dep:
                _multiservice_deactivate(slug,current_dep,'substituída pelo rollback para P'+str(int(publication_number)),trace+'-deactivate-current')
                _wait_deployment_inactive(current_dep)
                try:_multiservice_deactivate_bridge(slug,current_dep,'publication',trace+'-remove-current-bridge')
                except Exception:pass
                if current_number:_publisher_delete_stage(num,'publication',current_number,nt)
            con=sqlite3.connect(DB);_ensure_schema(con);con.execute('update production_releases set is_active=case when publication_number=? then 1 else 0 end where project_slug=?',(int(publication_number),slug));con.execute('update project_publications set is_active=case when deploy_number=? then 1 else 0 end where project_slug=?',(dep,slug));con.commit();con.close()
            _rm.project_changed(slug,'production-rollback')
            return {'ok':True,'project':slug,'publicationNumber':int(publication_number),'stageCode':'P'+str(int(publication_number)),'stableUrl':'https://'+primary_host+'/','numericStableUrl':'https://'+str(row['stable_hostname'])+'/','runtimeKind':str(detail.get('runtimeKind') or 'multiservice'),'deploymentId':target_dep,'containersRecreated':False,'volumesPreserved':True,'historicalRuntimeReactivated':True}
        except Exception:
            if switched and current_dep and current_number and re.fullmatch(r'[a-f0-9]{64}',current_digest):
                try:
                    _multiservice_reactivate(slug,current_dep,'commit',current_digest,trace+'-restore-current-runtime')
                    _multiservice_bridge(slug,current_dep,num,'publication',current_number,trace+'-restore-current-bridge')
                    _post('http://10.62.91.3/stage',{'public_number':num,'stage':'publication','number':current_number},nt,host='cloudif-publisher.internal',timeout=300)
                    _multiservice_activate_bridge(slug,num,current_number,trace+'-restore-current-alias')
                    _post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':current_deploy,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
                except Exception:pass
            if prepared:
                try:_multiservice_deactivate_bridge(slug,target_dep,'publication',trace+'-abort-bridge')
                except Exception:pass
                try:_multiservice_reactivate(slug,target_dep,'abort',target_digest,trace+'-abort')
                except Exception:pass
            try:_publisher_delete_stage(num,'publication',int(publication_number),nt)
            except Exception:pass
            raise
    status,data=_post(ku+'/komodo/publication/release/activate',{'project':slug,'public_number':num,'publication_number':int(publication_number)},kt,timeout=180)
    if status//100!=2 or not data.get('ok'):raise RuntimeError(_publication_error('promote',data))
    pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not publisher.get('ok'):raise RuntimeError(_publication_error('https',publisher))
    if not _external_ok(primary_host):raise RuntimeError('URL principal falhou após rollback legado.')
    current_dep=str(current_detail.get('productionDeploymentId') or '') if current else ''
    current_number=int(current['publication_number']) if current else 0
    if current_dep:
        try:_multiservice_deactivate(slug,current_dep,'substituída pelo rollback legado para P'+str(int(publication_number)),'portal-legacy-rollback-deactivate-'+str(int(publication_number)))
        except Exception:pass
        try:_multiservice_deactivate_bridge(slug,current_dep,'publication','portal-legacy-rollback-bridge-'+str(int(publication_number)))
        except Exception:pass
        if current_number:
            try:_publisher_delete_stage(num,'publication',current_number,nt)
            except Exception:pass
    con=sqlite3.connect(DB);_ensure_schema(con);con.execute('update production_releases set is_active=case when publication_number=? then 1 else 0 end where project_slug=?',(int(publication_number),slug));con.execute('update project_publications set is_active=case when deploy_number=? then 1 else 0 end where project_slug=?',(dep,slug));con.commit();con.close();_rm.project_changed(slug,'production-rollback');return {'ok':True,'project':slug,'publicationNumber':int(publication_number),'stageCode':'P'+str(int(publication_number)),'stableUrl':'https://'+primary_host+'/','numericStableUrl':'https://'+str(row['stable_hostname'])+'/','historicalRuntimeReactivated':bool(data.get('historicalRuntimeReactivated')),'containersRecreated':False}

def publish_now(slug,user,progress=None,publication_snapshot=None):
    def notify(step,message):
        if progress:
            progress(step,message)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; _ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project or not _can_publish(con,slug,user):
        con.close();raise PermissionError('legacy_publish_permission_denied')
    if slug==TARGET_SLUG:
        con.close()
        notify('preparing','Validando projeto e preparando a publicação.')
        return _publish_production(slug,user)
    notify('preparing','Validando projeto e preparando a publicação.')
    num=_number(con,slug)
    dep=int(con.execute('select coalesce(max(deploy_number),0)+1 from project_publications where project_slug=?',(slug,)).fetchone()[0])
    actor=user.get('username') or 'portal'; ku,kt,nt=_clients();pc=_publication_config()
    snapshot=publication_snapshot if isinstance(publication_snapshot,dict) else pc.capture_snapshot(slug,num,actor)
    environment_runtime=pc.execution_environment(slug,int(snapshot.get('environment_revision',snapshot.get('environmentRevision',0)) or 0),str(snapshot.get('environment_digest',snapshot.get('environmentDigest','')) or ''))
    deploy_payload={'project':slug,'public_number':num,'deploy_number':dep,'timeout':300,'actor':actor,
      'base_revision':int(snapshot.get('base_revision',snapshot.get('baseRevision',0)) or 0),'base_image':str(snapshot.get('base_image',snapshot.get('baseImage','')) or ''),'base_image_id':str(snapshot.get('base_image_id',snapshot.get('baseImageId','')) or ''),
      'environment_revision':int(environment_runtime['environmentRevision']),'environment_digest':str(environment_runtime['environmentDigest']),'environment_variables':environment_runtime['values']}
    notify('deploying','Agente de hospedagem criando a versão imutável.')
    transient_values=environment_runtime.get('values') or {}
    try:
        status,kres=_post(ku+'/komodo/publication/deploy',deploy_payload,kt,timeout=420)
    finally:
        if isinstance(transient_values,dict):transient_values.clear()
        environment_runtime['values']={}
        deploy_payload['environment_variables']={}
    if status//100!=2 or not kres.get('ok'):
        con.close(); raise RuntimeError(_publication_error('deploy',kres))
    notify('https','Configurando HTTPS e endereços públicos.')
    alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone()
    alias=str(alias_row[0]) if alias_row else ''
    status,nres=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if status//100!=2 or not nres.get('ok'):
        con.close(); raise RuntimeError(_publication_error('https',nres))
    version_host=f'{num}-d{dep}.cloudiff.duckdns.org'
    if not _external_ok(version_host):
        con.close(); raise RuntimeError('Validação HTTPS externa falhou para '+version_host)
    notify('promoting','Ativando a nova versão com rollback disponível.')
    status,pres=_post(ku+'/komodo/publication/promote',{'project':slug,'public_number':num,'deploy_number':dep},kt,timeout=120)
    if status//100!=2 or not pres.get('ok'):
        con.close(); raise RuntimeError(_publication_error('promote',pres))
    notify('validating','Validando o endereço público.')
    stable_host=f'{num}.cloudiff.duckdns.org'
    if not _external_ok(stable_host):
        con.close(); raise RuntimeError('Validação da URL estável falhou após promoção.')
    now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); commit=str(kres.get('commit') or '')
    republished=bool(kres.get('republished'));republished_from=kres.get('republished_from')
    publication_message=('Republicação do mesmo código da d'+str(republished_from) if republished and republished_from is not None else 'Nova revisão publicada a partir do Git')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    publication_snapshot_safe={'baseRevision':int(kres.get('baseRevision') or 0),'baseImageId':str(kres.get('baseImageId') or ''),'environment':'production','environmentRevision':int(kres.get('environmentRevision') or 0),'environmentDigest':str(kres.get('environmentDigest') or ''),'variableNames':[str(x) for x in (kres.get('variableNames') or [])],'secretValuesIncluded':False,'secretReferencesIncluded':False}
    con.execute('''insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json)
 values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(slug,num,dep,f'd{dep}',commit,stable_host,version_host,'published',1,actor,now,now,publication_message,json.dumps({'komodo':kres,'npm':nres,'promotion':pres,'republished':republished,'republished_from':republished_from,'snapshot':publication_snapshot_safe},ensure_ascii=False)))
    cols=[x[1] for x in con.execute('pragma table_info(projects)')]
    updates={k:v for k,v in {'status':'published','komodo_status':'running','updated_at':now}.items() if k in cols}
    if updates: con.execute('update projects set '+','.join(k+'=?' for k in updates)+' where slug=?',list(updates.values())+[slug])
    access=_project_access_snapshot(con,slug)
    project_tenant=str(project['tenant'] if 'tenant' in project.keys() else '')
    con.commit(); con.close()
    membership=_reconcile_publication_members(ku,kt,slug,access)
    queued=_enqueue_membership_reconcile(slug,actor,project_tenant)
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':dep,'stable_url':'https://'+stable_host+'/','version_url':'https://'+version_host+'/','alias':alias,'alias_url':('https://'+alias+'.cloudiff.duckdns.org/' if alias else ''),'commit':commit,'republished':republished,'republished_from':republished_from,'message':publication_message,'snapshot':publication_snapshot_safe,'membership':membership,'reconcile':queued}

def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())


def _approval_settings():
    cfg=_env('/etc/cloudif/approvals.env')
    if not cfg:cfg=_env('/etc/cloudif/approval-service.env')
    url=(cfg.get('CLOUDIF_APPROVAL_URL') or 'http://127.0.0.1:'+str(cfg.get('CLOUDIF_APPROVAL_PORT') or '18204')).rstrip('/');token=cfg.get('CLOUDIF_APPROVAL_TOKEN','')
    if not token:raise RuntimeError('Serviço de aprovação indisponível.')
    return url,token


def _approval_call(method,path,payload=None,timeout=45):
    url,token=_approval_settings();raw=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();req=urllib.request.Request(url+path,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as exc:
        try:data=json.load(exc)
        except Exception:data={'ok':False,'error':'approval_service_error'}
        return exc.code,data


def _production_activation_material(slug,candidate,publication,environment_summary):
    material={'action':'deployment.production.activate','project':slug,'candidateNumber':int(candidate['candidate_number']),'publicationNumber':int(publication),'deployNumber':int(candidate['deploy_number']),'artifactImageId':str(candidate['artifact_image_id']),'commit':str(candidate['commit_sha']),'homologatedBy':str(candidate['homologated_by'] or ''),'homologatedAt':str(candidate['homologated_at'] or ''),'productionEnvironmentRevision':int(environment_summary.get('environmentRevision') or 0),'productionEnvironmentDigest':str(environment_summary.get('environmentDigest') or '')}
    digest=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest();return material,digest


def request_production_activation(slug,candidate_number,user,reason='Publicar candidato homologado em Produção'):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project or not _can_publish(con,slug,user):con.close();raise PermissionError('Você não está autorizado a publicar este projeto em Produção.')
    candidate=con.execute("select * from publication_candidates where project_slug=? and candidate_number=? and status='homologated'",(slug,int(candidate_number))).fetchone()
    if not candidate:con.close();raise RuntimeError('O candidato precisa estar homologado antes da solicitação de Produção.')
    existing=con.execute("select * from production_activation_requests where project_slug=? and candidate_number=? and status in ('pending','approved','queued') order by publication_number desc limit 1",(slug,int(candidate_number))).fetchone()
    renewed=False
    if existing:
        aid=str(existing['approval_id'] or '');publication=int(existing['publication_number']);con.close();approval=production_approval_status(slug,aid,user) if aid else {'status':str(existing['status'])};approval_status=str(approval.get('status') or '')
        if approval_status in {'pending','pending_second','approved','reserved'}:
            return {'ok':True,'existing':True,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':'P'+str(publication),'activationDigest':str(existing['activation_digest']),'approvalId':aid,**approval}
        if approval_status not in {'expired','rejected','cancelled'}:
            return {'ok':True,'existing':True,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':'P'+str(publication),'activationDigest':str(existing['activation_digest']),'approvalId':aid,**approval}
        con=sqlite3.connect(DB);_ensure_schema(con);con.execute('update production_activation_requests set status=?,updated_at=? where project_slug=? and candidate_number=? and publication_number=?',(approval_status,_now(),slug,int(candidate_number),publication));con.commit();con.close();renewed=True
    else:
        con.commit();con.execute('begin immediate');publication=_reserve_publication_number(con,slug,int(candidate_number));con.commit();con.close()
    summary=_publication_config().environment_summary(slug,'production')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Produção possui variáveis obrigatórias pendentes.')
    material,digest=_production_activation_material(slug,candidate,publication,summary);username=(user.get('username') or 'portal').strip().lower();requested_by='portal:'+username;groups={str(x).strip().lower() for x in (user.get('groups') or [])};role='admin' if user.get('admin') or groups.intersection({'cloudif-tenants-admin','cloudif-professor'}) else 'owner'
    metadata={**material,'activationDigest':digest,'content_stored':False,'secret_values_in_metadata':False,'artifact_content_stored':False}
    payload={'project_slug':slug,'action':'deployment.production.activate','requested_by':requested_by,'requester_role':role,'ttl_seconds':1800,'reason':str(reason or '')[:500],'trace_id':'portal-production-'+digest[:20],'metadata':metadata}
    code,data=_approval_call('POST','/v1/approvals',payload)
    if code not in {200,201} or not data.get('ok'):raise RuntimeError('Não foi possível criar a autorização crítica de Produção.')
    aid=str(data.get('approval_id') or '');now=_now();con=sqlite3.connect(DB);_ensure_schema(con)
    if renewed:
        con.execute('update production_activation_requests set activation_digest=?,approval_id=?,requested_by=?,status=?,updated_at=? where project_slug=? and candidate_number=? and publication_number=?',(digest,aid,requested_by,str(data.get('status') or 'pending'),now,slug,int(candidate_number),publication))
    else:
        con.execute('insert into production_activation_requests(project_slug,candidate_number,publication_number,activation_digest,approval_id,requested_by,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)',(slug,int(candidate_number),publication,digest,aid,requested_by,str(data.get('status') or 'pending'),now,now))
    con.commit();con.close()
    return {'ok':True,'existing':False,'renewed':renewed,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':'P'+str(publication),'activationDigest':digest,'approvalId':aid,'status':str(data.get('status') or 'pending'),'twoApproversRequired':bool(data.get('two_approvers_required')),'approvalUrl':'/cloudiff/portal/?tab=aprovacoes','policyApplied':bool(data.get('policy_applied')),'secretValuesIncluded':False}


def production_approval_status(slug,approval_id,user):
    approval_id=str(approval_id or '')
    if not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):raise ValueError('Autorização de Produção inválida.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    if not (_project_allowed(con,slug,user) or _can_homologate(con,slug,user)):con.close();raise PermissionError('Sem acesso ao projeto.')
    local=con.execute('select * from production_activation_requests where project_slug=? and approval_id=?',(slug,approval_id)).fetchone();con.close()
    if not local:raise ValueError('Autorização de Produção não encontrada.')
    code,data=_approval_call('GET','/v1/approvals?status=all')
    if code!=200:raise RuntimeError('Serviço de aprovação indisponível.')
    approval=next((x for x in data.get('approvals') or [] if x.get('approval_id')==approval_id),None)
    if not approval:raise ValueError('Autorização de Produção não encontrada.')
    return {'approvalId':approval_id,'status':str(approval.get('status') or ''),'approvedBy':approval.get('approved_by'),'secondApprovedBy':approval.get('second_approved_by'),'twoApproversRequired':bool(approval.get('two_approvers_required')),'expiresAt':approval.get('expires_at'),'activationDigest':str(local['activation_digest']),'candidateNumber':int(local['candidate_number']),'publicationNumber':int(local['publication_number']),'stageCode':'P'+str(int(local['publication_number']))}


def _validate_production_approval(slug,candidate_number,publication_number,approval_id,activation_digest,actor):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);candidate=con.execute("select * from publication_candidates where project_slug=? and candidate_number=? and status='homologated'",(slug,int(candidate_number))).fetchone();local=con.execute('select * from production_activation_requests where project_slug=? and candidate_number=? and publication_number=? and approval_id=?',(slug,int(candidate_number),int(publication_number),str(approval_id))).fetchone();con.close()
    if not candidate or not local:raise PermissionError('approval_binding_mismatch')
    summary=_publication_config().environment_summary(slug,'production');material,digest=_production_activation_material(slug,candidate,int(publication_number),summary)
    if not hmac.compare_digest(digest,str(activation_digest or '')) or not hmac.compare_digest(digest,str(local['activation_digest'])):raise PermissionError('approval_binding_mismatch')
    code,data=_approval_call('GET','/v1/approvals?status=all')
    approval=next((x for x in data.get('approvals') or [] if x.get('approval_id')==approval_id),None) if code==200 else None
    if not approval or approval.get('status')!='approved' or approval.get('project_slug')!=slug or approval.get('action')!='deployment.production.activate' or approval.get('requested_by')!=str(local['requested_by']) or not approval.get('approved_by'):raise PermissionError('production_approval_not_approved')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise PermissionError('approval_binding_mismatch')
    if metadata.get('content_stored') is not False or metadata.get('secret_values_in_metadata') is not False or metadata.get('artifactImageId')!=material['artifactImageId'] or int(metadata.get('candidateNumber') or 0)!=int(candidate_number) or int(metadata.get('publicationNumber') or 0)!=int(publication_number) or int(metadata.get('productionEnvironmentRevision') or 0)!=int(material['productionEnvironmentRevision']) or not hmac.compare_digest(str(metadata.get('productionEnvironmentDigest') or ''),str(material['productionEnvironmentDigest'])) or not hmac.compare_digest(str(metadata.get('activationDigest') or ''),digest):raise PermissionError('approval_binding_mismatch')
    reservation='res_'+hashlib.sha256((str(approval_id)+digest).encode()).hexdigest()[:32];code,reserved=_approval_call('POST','/v1/approvals/'+urllib.parse.quote(str(approval_id),safe='')+'/reserve',{'reservation_id':reservation,'reserved_by':'portal:'+str(actor).strip().lower(),'ttl_seconds':900})
    if code!=200 or reserved.get('status')!='reserved':raise RuntimeError('approval_reserve_failed')
    return candidate,reservation,digest


def _finalize_production_approval(approval_id,reservation,success):
    operation='finalize' if success else 'release';payload={'reservation_id':reservation}
    if success:payload['result']='success'
    return _approval_call('POST','/v1/approvals/'+urllib.parse.quote(str(approval_id),safe='')+'/'+operation,payload)

def _active_stage_job(con,slug):
    return con.execute("select id,operation,candidate_number,publication_number from publication_jobs where project_slug=? and status in ('queued','running') order by id desc limit 1",(slug,)).fetchone()

def enqueue_homologation(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project or not _can_homologate(con,slug,user):
        con.close();raise PermissionError('homologation_permission_denied')
    role=_release_permission_role(con,slug,user)
    # Group-derived Admin/Professor privileges cannot be reconstructed from a
    # queued user name. Require trusted directory refresh before supporting them.
    if role not in ('owner','delegated'):
        con.close();raise PermissionError('homologation_role_revalidation_unavailable')
    active=_active_stage_job(con,slug)
    if active:
        out={'ok':True,'queued':True,'job_id':int(active['id']),'existing':True,'operation':str(active['operation'] or '')};con.close();return out
    candidate=_next_candidate(con,slug);actor=(user.get('username') or 'portal').strip().lower();cur=con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at,operation,candidate_number,environment,authorization_mode,authorization_role) values(?,?,?,?,?,?,?,?,?,?,?)",(slug,actor,'queued','queued','Envio para homologação recebido.',_now(),'homologation_candidate',candidate,'homologation','project_permission',role));con.commit();jid=int(cur.lastrowid);con.close();return {'ok':True,'queued':True,'job_id':jid,'candidateNumber':candidate,'stageCode':'H'+str(candidate),'existing':False}

def enqueue_candidate_publication(slug,candidate_number,user,approval_id='',activation_digest=''):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project or not _can_publish(con,slug,user):con.close();raise PermissionError('Você não está autorizado a publicar este projeto em Produção.')
    candidate=con.execute("select * from publication_candidates where project_slug=? and candidate_number=? and status='homologated'",(slug,int(candidate_number))).fetchone()
    request=con.execute("select * from production_activation_requests where project_slug=? and candidate_number=? and approval_id=? and status<>'superseded'",(slug,int(candidate_number),str(approval_id))).fetchone()
    if not candidate:con.close();raise RuntimeError('O candidato precisa estar homologado antes da publicação.')
    if not request or not hmac.compare_digest(str(request['activation_digest']),str(activation_digest or '')):con.close();raise PermissionError('approval_binding_mismatch')
    publication=int(request['publication_number']);active=_active_stage_job(con,slug)
    if active:
        out={'ok':True,'queued':True,'job_id':int(active['id']),'existing':True,'operation':str(active['operation'] or '')};con.close();return out
    con.close();approval=production_approval_status(slug,str(approval_id),user)
    if approval.get('status')!='approved':raise PermissionError('A autorização crítica de Produção ainda não foi concluída.')
    actor=(user.get('username') or 'portal').strip().lower();con=sqlite3.connect(DB);_ensure_schema(con);cur=con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at,operation,candidate_number,publication_number,environment,approval_id,activation_digest,authorization_mode,authorization_role) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(slug,actor,'queued','queued','Publicação do candidato homologado e aprovado recebida.',_now(),'production_release',int(candidate_number),publication,'production',str(approval_id),str(activation_digest),'critical_approval',_release_permission_role(con,slug,user)));con.execute("update production_activation_requests set status='queued',updated_at=? where project_slug=? and candidate_number=? and publication_number=?",(_now(),slug,int(candidate_number),publication));con.commit();jid=int(cur.lastrowid);con.close();return {'ok':True,'queued':True,'job_id':jid,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':'P'+str(publication),'approvalId':str(approval_id),'existing':False}


def _validate_project_permission_job(slug,candidate_number,publication_number,activation_digest,actor,authorization_role,job_id):
    """Revalidate current role, membership, and queued job before publish mutation.

    An authenticated current group lookup is required for Admin/Professor jobs;
    historical queue-time group claims cannot authorize production promotion.
    """
    actor=str(actor or '').strip().lower();role=str(authorization_role or '').strip().lower()
    if not actor or actor=='portal' or role not in ('owner','delegated'):
        raise PermissionError('publication_role_revalidation_unavailable')

    def current_binding():
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
        try:
            _ensure_schema(con)
            queued=con.execute(
                'select id,project_slug,actor,status,operation,authorization_mode,authorization_role, '
                'candidate_number,publication_number,activation_digest '
                'from publication_jobs where id=? and project_slug=?',
                (int(job_id),slug)).fetchone()
            if (not queued or str(queued['status'])!='running'
                    or str(queued['operation'])!='production_release'
                    or str(queued['authorization_mode'])!='project_permission'
                    or str(queued['actor'] or '').strip().lower()!=actor
                    or str(queued['authorization_role'] or '').strip().lower()!=role
                    or int(queued['candidate_number'] or 0)!=int(candidate_number)
                    or int(queued['publication_number'] or 0)!=int(publication_number)
                    or not hmac.compare_digest(str(queued['activation_digest'] or ''),str(activation_digest or ''))):
                raise PermissionError('publication_job_binding_mismatch')
            user={'username':actor,'groups':[],'admin':False}
            if (not _project_allowed(con,slug,user)
                    or not _can_publish(con,slug,user)
                    or _release_permission_role(con,slug,user)!=role):
                raise PermissionError('publication_permission_revoked')
            candidate=con.execute("select * from publication_candidates where project_slug=? and candidate_number=? and status='homologated'",(slug,int(candidate_number))).fetchone()
            if not candidate:raise PermissionError('publication_binding_mismatch')
            return candidate
        finally:
            con.close()

    candidate=current_binding()
    summary=_publication_config().environment_summary(slug,'production')
    _material,digest=_production_activation_material(slug,candidate,int(publication_number),summary)
    meta=_candidate_runtime_metadata(candidate);dep=str(meta.get('homologationDeploymentId') or '');partial=False
    if meta.get('runtimeKind')=='compose-snapshot' and re.fullmatch(r'dep_[a-f0-9]{24}',dep):
        try:partial=str(_compose_deployment_status(dep).get('environment') or '')=='production'
        except Exception:partial=False
    if not partial and not hmac.compare_digest(str(digest),str(activation_digest or '')):raise PermissionError('publication_binding_mismatch')
    if partial and not re.fullmatch(r'[a-f0-9]{64}',str(activation_digest or '')):raise PermissionError('publication_binding_mismatch')
    # Environment materialization may be slow or call external services; revoke
    # or cancel during that window must not leave a stale successful preflight.
    refreshed_candidate=current_binding()
    if dict(refreshed_candidate)!=dict(candidate):
        raise PermissionError('publication_binding_mismatch')
    return candidate,digest

def enqueue_authorized_publication(slug,candidate_number,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project or not _can_publish(con,slug,user):con.close();raise PermissionError('Você não está autorizado a publicar este projeto em Produção.')
    candidate=con.execute("select * from publication_candidates where project_slug=? and candidate_number=? and status='homologated'",(slug,int(candidate_number))).fetchone()
    if not candidate:con.close();raise RuntimeError('O candidato precisa estar homologado antes da publicação.')
    active=_active_stage_job(con,slug)
    if active:
        out={'ok':True,'queued':True,'job_id':int(active['id']),'existing':True,'operation':str(active['operation'] or '')};con.close();return out
    con.commit();con.execute('begin immediate');publication=_reserve_publication_number(con,slug,int(candidate_number));role=_release_permission_role(con,slug,user);actor=(user.get('username') or 'portal').strip().lower();con.commit();con.close()
    summary=_publication_config().environment_summary(slug,'production')
    if not summary.get('valid'):raise RuntimeError('O ambiente de Produção possui variáveis obrigatórias pendentes.')
    _material,digest=_production_activation_material(slug,candidate,publication,summary)
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    legacy_requests=[dict(row) for row in con.execute("select approval_id,requested_by,status,candidate_number from production_activation_requests where project_slug=? and status in ('pending','pending_second','approved','reserved')",(slug,)).fetchall()]
    con.close()
    for legacy in legacy_requests:
        aid=str(legacy.get('approval_id') or '');requester=str(legacy.get('requested_by') or '')
        if aid and requester:
            try:_approval_call('POST','/v1/approvals/'+urllib.parse.quote(aid,safe='')+'/cancel',{'requested_by':requester,'cancellation_reason':'Substituída por autorização direta vinculada às permissões do projeto.'})
            except Exception:pass
    con=sqlite3.connect(DB);_ensure_schema(con)
    con.execute("update production_activation_requests set status='superseded',updated_at=? where project_slug=? and status in ('pending','pending_second','approved','reserved')",(_now(),slug))
    cur=con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at,operation,candidate_number,publication_number,environment,approval_id,activation_digest,authorization_mode,authorization_role) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
      (slug,actor,'queued','queued','Publicação autorizada pelo papel do usuário no projeto.',_now(),'production_release',int(candidate_number),publication,'production','',digest,'project_permission',role))
    con.commit();jid=int(cur.lastrowid);con.close()
    return {'ok':True,'queued':True,'job_id':jid,'candidateNumber':int(candidate_number),'publicationNumber':publication,'stageCode':'P'+str(publication),'authorizationMode':'project_permission','authorizationRole':role,'existing':False}

def homologate_and_enqueue(slug,candidate_number,user,note=''):
    homologate_candidate(slug,candidate_number,user,'approved',note);approval=request_production_activation(slug,candidate_number,user,'Homologar e publicar candidato em Produção')
    if approval.get('status')=='approved':
        queued=enqueue_candidate_publication(slug,candidate_number,user,approval.get('approvalId') or '',approval.get('activationDigest') or '');return {**approval,'queued':queued}
    return approval

def enqueue_publish(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project or not _can_publish(con,slug,user):
        con.close();raise PermissionError('legacy_publish_permission_denied')
    role=_release_permission_role(con,slug,user)
    if role not in ('owner','delegated'):
        con.close();raise PermissionError('legacy_publish_role_revalidation_unavailable')
    active=con.execute("select id from publication_jobs where project_slug=? and status in ('queued','running') order by id desc limit 1",(slug,)).fetchone()
    if active:
        job_id=int(active[0]);con.close();return {'ok':True,'queued':True,'job_id':job_id,'existing':True}
    actor=user.get('username') or 'portal';now=_now();num=_number(con,slug)
    snapshot=_publication_config().capture_snapshot(slug,num,actor)
    cur=con.execute("""insert into publication_jobs(project_slug,actor,status,step,message,created_at,base_revision,base_image,base_image_id,environment,environment_revision,environment_digest,operation,authorization_mode,authorization_role)
      values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(slug,actor,'queued','queued','Solicitação recebida com base e ambiente congelados.',now,int(snapshot['baseRevision']),str(snapshot.get('baseImage') or ''),str(snapshot['baseImageId']),'production',int(snapshot['environmentRevision']),str(snapshot.get('environmentDigest') or ''),'legacy_publish','project_permission',role))
    con.commit();job_id=int(cur.lastrowid);con.close()
    return {'ok':True,'queued':True,'job_id':job_id,'existing':False,'baseRevision':int(snapshot['baseRevision']),'baseImageId':str(snapshot['baseImageId']),'environmentRevision':int(snapshot['environmentRevision']),'environmentDigest':str(snapshot.get('environmentDigest') or ''),'secretValuesIncluded':False}

def latest_job(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    row=con.execute("""select j.*,a.job_id as acknowledged_job_id from publication_jobs j
        left join publication_job_acknowledgements a on a.job_id=j.id
        where j.project_slug=? order by j.id desc limit 1""",(slug,)).fetchone();con.close()
    if not row or row['acknowledged_job_id'] is not None:return None
    result=dict(row);result.pop('acknowledged_job_id',None);return result

def acknowledge_job(slug,job_id,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    job=con.execute('select id,status from publication_jobs where id=? and project_slug=?',(int(job_id),slug)).fetchone()
    if not job:con.close();raise ValueError('Publicação não encontrada.')
    if job['status'] not in ('succeeded','failed'):con.close();raise ValueError('A publicação ainda está em andamento.')
    con.execute('insert or replace into publication_job_acknowledgements(job_id,actor,acknowledged_at) values(?,?,?)',(int(job_id),user.get('username') or 'portal',_now()))
    con.commit();con.close();return {'ok':True,'job_id':int(job_id)}

def claim_next_job():
    con=sqlite3.connect(DB,timeout=30);con.row_factory=sqlite3.Row;_ensure_schema(con)
    # Schema/permission migrations may open an implicit transaction. Claiming a job
    # intentionally starts its own IMMEDIATE transaction, so close migration work first.
    con.commit()
    con.execute('begin immediate')
    stale=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()-1800))
    con.execute("update publication_jobs set status='queued',step='queued',message='Job recuperado após reinício do worker.',started_at=null where status='running' and started_at<?",(stale,))
    row=con.execute("select * from publication_jobs where status='queued' order by id limit 1").fetchone()
    if not row:con.commit();con.close();return None
    con.execute("update publication_jobs set status='running',step='preparing',message='Preparando publicação.',started_at=? where id=? and status='queued'",(_now(),row['id']))
    con.commit();result=dict(row);result['status']='running';con.close();return result

def _job_update(job_id,status=None,step=None,message=None,detail=None,finished=False):
    con=_publication_db(30);_ensure_schema(con);con.commit();sets=[];vals=[]
    for key,value in (('status',status),('step',step),('message',message),('detail_json',json.dumps(detail or {},ensure_ascii=False) if detail is not None else None)):
        if value is not None:sets.append(key+'=?');vals.append(value)
    if finished:sets.append('finished_at=?');vals.append(_now())
    vals.append(job_id);con.execute('update publication_jobs set '+','.join(sets)+' where id=?',vals);con.commit();con.close()

def _validate_homologation_job(slug,candidate_number,actor,authorization_role,job_id):
    """Require live project ACL and exact queued job identity before Hn effects.

    Never recover implicit Admin/Professor groups from a queue-time role string.
    The worker only has the actor name, not a fresh trusted directory identity.
    """
    actor=str(actor or '').strip().lower()
    role=str(authorization_role or '').strip().lower()
    if not actor or actor=='portal' or role not in ('owner','delegated'):
        raise PermissionError('homologation_role_revalidation_unavailable')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
    try:
        _ensure_schema(con)
        row=con.execute('''select id,project_slug,actor,status,operation,candidate_number,
            environment,authorization_mode,authorization_role
            from publication_jobs where id=? and project_slug=?''',(int(job_id),slug)).fetchone()
        if (not row or str(row['status'])!='running'
                or str(row['operation'])!='homologation_candidate'
                or str(row['environment'])!='homologation'
                or str(row['authorization_mode'])!='project_permission'
                or str(row['actor'] or '').strip().lower()!=actor
                or str(row['authorization_role'] or '').strip().lower()!=role
                or int(row['candidate_number'] or 0)!=int(candidate_number)
                or int(candidate_number)<=0):
            raise PermissionError('homologation_job_binding_mismatch')
        user={'username':actor,'groups':[],'admin':False}
        if (not _project_allowed(con,slug,user)
                or not _can_homologate(con,slug,user)
                or _release_permission_role(con,slug,user)!=role):
            raise PermissionError('homologation_permission_revoked')
    finally:
        con.close()
    return True


def _homologation_job_update_if_running(job_id,step,message,status=None,detail=None,finished=False):
    """Do not resurrect cancelled Hn jobs through status/progress writes."""
    con=_publication_db(30,True)
    try:
        _ensure_schema(con)
        sets=['step=?','message=?'];params=[step,message]
        if status is not None:sets.append('status=?');params.append(status)
        if detail is not None:sets.append('detail_json=?');params.append(json.dumps(detail,ensure_ascii=False))
        if finished:sets.append('finished_at=?');params.append(_now())
        params.append(int(job_id))
        rc=con.execute('update publication_jobs set '+','.join(sets)+" where id=? and status='running'",params).rowcount
        con.commit()
    finally:
        con.close()
    if rc!=1:raise PermissionError('homologation_job_no_longer_running')


def _validate_legacy_publish_job(slug,actor,role,job_id,expected_snapshot):
    """Fail closed on legacy publication queue jobs without current publish grant.

    A queue-time Admin/Professor role is not proof of current group membership.
    Every caller must also fence the external publisher before runtime effects.
    """
    actor=str(actor or '').strip().lower();role=str(role or '').strip().lower()
    if not actor or role not in ('owner','delegated'):
        raise PermissionError('legacy_publish_role_revalidation_unavailable')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
    try:
        _ensure_schema(con)
        row=con.execute('''select * from publication_jobs where id=? and project_slug=?''',(int(job_id),slug)).fetchone()
        if (not row or str(row['status'])!='running'
                or str(row['operation'])!='legacy_publish'
                or str(row['environment'])!='production'
                or str(row['authorization_mode'])!='project_permission'
                or str(row['authorization_role'] or '').strip().lower()!=role
                or str(row['actor'] or '').strip().lower()!=actor):
            raise PermissionError('legacy_publish_job_binding_mismatch')
        if any(str(row[key])!=str(expected_snapshot.get(key)) for key in
               ('base_revision','base_image','base_image_id','environment_revision','environment_digest')):
            raise PermissionError('legacy_publish_snapshot_mismatch')
        user={'username':actor,'groups':[],'admin':False}
        if (not _project_allowed(con,slug,user) or not _can_publish(con,slug,user)
                or _release_permission_role(con,slug,user)!=role):
            raise PermissionError('legacy_publish_permission_revoked')
    finally:
        con.close()
    return True


def run_job(job):
    job_id=int(job['id']);slug=job['project_slug'];actor=job['actor']
    user={'username':actor,'groups':[],'admin':False}
    try:
        def progress(step,message):
            _job_update(job_id,status='running',step=step,message=message)
        operation=str(job.get('operation') or 'legacy_publish')
        if operation=='homologation_candidate':
            candidate_number=int(job.get('candidate_number') or 0)
            queued_role=str(job.get('authorization_role') or '')
            _validate_homologation_job(slug,candidate_number,actor,queued_role,job_id)
            def guarded_progress(step,message):
                # Recheck status/membership before every controlled stage.
                # A cross-service lock is still required to close TOCTOU after
                # the last check; do not claim runtime authorization from this.
                _validate_homologation_job(slug,candidate_number,actor,queued_role,job_id)
                _homologation_job_update_if_running(job_id,step,message)
                _validate_homologation_job(slug,candidate_number,actor,queued_role,job_id)
            result=create_homologation_candidate(slug,user,progress=guarded_progress,candidate_number=candidate_number,authorization_checked=True)
            _validate_homologation_job(slug,candidate_number,actor,queued_role,job_id)
            message='Candidato '+str(result.get('stageCode') or '')+' pronto para homologação.'
        elif operation=='production_release':
            authorization_mode=str(job.get('authorization_mode') or 'critical_approval')
            activation_digest=str(job.get('activation_digest') or '')
            if authorization_mode=='project_permission':
                _validate_project_permission_job(slug,int(job.get('candidate_number') or 0),int(job.get('publication_number') or 0),activation_digest,actor,job.get('authorization_role'),job_id)
                result=publish_homologated_candidate(slug,int(job.get('candidate_number') or 0),user,progress=progress,publication_number=int(job.get('publication_number') or 0),authorization_checked=True);message='Publicação '+str(result.get('stageCode') or '')+' ativada em Produção.'
            else:
                approval_id=str(job.get('approval_id') or '');reservation=''
                try:
                    _candidate,reservation,_digest=_validate_production_approval(slug,int(job.get('candidate_number') or 0),int(job.get('publication_number') or 0),approval_id,activation_digest,actor)
                    result=publish_homologated_candidate(slug,int(job.get('candidate_number') or 0),user,progress=progress,publication_number=int(job.get('publication_number') or 0),authorization_checked=True);message='Publicação '+str(result.get('stageCode') or '')+' ativada em Produção.'
                    code,finalized=_finalize_production_approval(approval_id,reservation,True)
                    if code!=200 or finalized.get('status')!='consumed':raise RuntimeError('approval_finalize_failed')
                    con=sqlite3.connect(DB);_ensure_schema(con);con.execute("update production_activation_requests set status='consumed',updated_at=? where approval_id=?",(_now(),approval_id));con.commit();con.close()
                except Exception:
                    if reservation:_finalize_production_approval(approval_id,reservation,False)
                    raise
        elif operation=='legacy_publish':
            queued_role=str(job.get('authorization_role') or '')
            _validate_legacy_publish_job(slug,actor,queued_role,job_id,job)
            def guarded_legacy_progress(step,message):
                _validate_legacy_publish_job(slug,actor,queued_role,job_id,job)
                _homologation_job_update_if_running(job_id,step,message)
                _validate_legacy_publish_job(slug,actor,queued_role,job_id,job)
            result=publish_now(slug,user,progress=guarded_legacy_progress,publication_snapshot=job)
            _validate_legacy_publish_job(slug,actor,queued_role,job_id,job)
            message='Site publicado e ativado.'
        else:
            raise PermissionError('unsupported_publication_operation')
        if operation=='homologation_candidate':
            _validate_homologation_job(slug,int(job.get('candidate_number') or 0),actor,job.get('authorization_role'),job_id)
            _homologation_job_update_if_running(job_id,'completed',message,status='succeeded',detail=result,finished=True)
        elif operation=='legacy_publish':
            _validate_legacy_publish_job(slug,actor,job.get('authorization_role'),job_id,job)
            _homologation_job_update_if_running(job_id,'completed',message,status='succeeded',detail=result,finished=True)
        else:
            _job_update(job_id,status='succeeded',step='completed',message=message,detail=result,finished=True)
        return result
    except Exception as exc:
        if str(job.get('operation') or '') in ('homologation_candidate','legacy_publish'):
            # Preserve external cancellation; it must never be overwritten by
            # the worker's generic failed/succeeded update.
            try:
                _homologation_job_update_if_running(job_id,'failed',str(exc),status='failed',
                    detail={'error':type(exc).__name__,'message':str(exc)[:800]},finished=True)
            except PermissionError:pass
        else:
            _job_update(job_id,status='failed',step='failed',message=str(exc),detail={'error':type(exc).__name__,'message':str(exc)[:800]},finished=True)
        return None


def set_alias(slug,alias,user):
    alias=str(alias or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',alias):raise ValueError('Alias inválido. Use letras minúsculas, números e hífen.')
    if alias in {'www','api','admin','cloudiff','auth','login','status','mail'}:raise ValueError('Alias reservado.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    # Changing a public DNS alias is a production-facing mutation, not merely
    # viewing a shared project. Require the current publish grant before any
    # publisher call or reservation write.
    if not project or not _can_publish(con,slug,user):
        con.close();raise PermissionError('publication_alias_permission_denied')
    other=con.execute('select project_slug from project_publication_aliases where alias=? and project_slug<>?',(alias,slug)).fetchone()
    if other:con.close();raise ValueError('Este alias já está em uso.')
    now=_now();actor=user.get('username') or 'portal'
    previous=con.execute('select alias,created_by,created_at,updated_at from project_publication_aliases where project_slug=?',(slug,)).fetchone()
    pub=con.execute('select public_number,deploy_number from project_publications where project_slug=? and is_active=1 order by id desc limit 1',(slug,)).fetchone();public_number=int(pub['public_number']) if pub else int(_number(con,slug));deploy_number=int(pub['deploy_number']) if pub else 0
    _,_,nt=_clients();status,data=_post('http://10.62.91.3/alias',{'public_number':public_number,'deploy_number':deploy_number,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if status//100!=2 or not data.get('ok'):
        con.close()
        raise RuntimeError(_publication_error('https',data))
    con.execute('insert into project_publication_aliases(alias,project_slug,created_by,created_at,updated_at) values(?,?,?,?,?) on conflict(project_slug) do update set alias=excluded.alias,updated_at=excluded.updated_at',(alias,slug,actor,(previous['created_at'] if previous else now),now))
    con.commit();con.close()
    result={'ok':True,'alias':alias,'hostname':alias+'.cloudiff.duckdns.org','active':bool(pub),'reserved':not bool(pub)};result.update(data)
    return result

def _project_access_snapshot(con,slug):
    row=con.execute('select * from projects where slug=?',(slug,)).fetchone()
    owner=''
    if row:
        keys=set(row.keys())
        owner=str((row['owner'] if 'owner' in keys else '') or (row['created_by'] if 'created_by' in keys else '') or '').strip().lower()
    acl=[{'type':str(x['subject_type']),'subject':str(x['subject'])} for x in con.execute('select subject_type,subject from project_acl where slug=? order by id',(slug,)).fetchall()]
    return {'owner':owner,'acl':acl}

def _reconcile_publication_members(ku,kt,slug,access):
    status,data=_post(ku+'/komodo/project/membership/reconcile',{'project':slug,'access':access},kt,timeout=180)
    return {'ok':status//100==2 and data.get('ok') is not False,'status':status,'result':data}

def _enqueue_membership_reconcile(slug,actor,tenant=''):
    try:
        from cloudif_reconcile_client import enqueue
        return enqueue('project.membership.changed',actor=actor or 'portal',username=actor or '',project=slug,tenant=tenant or '',payload={'source':'publication_activation','operation':'reconcile'},dedupe_seconds=0)
    except Exception as exc:
        return {'ok':False,'error':type(exc).__name__}

def activate(slug,deploy_number,user):
    if slug==TARGET_SLUG:raise RuntimeError('Use o rollback blue/green da produção real.')
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    row=con.execute('select * from project_publications where project_slug=? and deploy_number=? and status=?',(slug,int(deploy_number),'published')).fetchone()
    if not row:con.close();raise RuntimeError('Publicação não encontrada ou não está válida.')
    num=int(row['public_number']);dep=int(deploy_number);commit=str(row['commit_sha'] or '').strip();ku,kt,nt=_clients()
    promote_payload={'project':slug,'public_number':num,'deploy_number':dep}
    status,pres=_post(ku+'/komodo/publication/promote',promote_payload,kt,timeout=120)
    rebuilt=None
    if status//100!=2 or not pres.get('ok'):
        reason=str(pres.get('error') or '')
        if reason!='target_not_healthy':
            con.close();raise RuntimeError(_publication_error('promote',pres))
        if len(commit)!=40:
            con.close();raise RuntimeError('A versão não possui commit imutável registrado e não pode ser reconstruída automaticamente.')
        deploy_status,rebuilt=_post(ku+'/komodo/publication/deploy',{'project':slug,'public_number':num,'deploy_number':dep,'commit':commit,'timeout':600},kt,timeout=900)
        if deploy_status//100!=2 or not rebuilt.get('ok'):
            con.close();raise RuntimeError(_publication_error('rebuild',rebuilt))
        status,pres=_post(ku+'/komodo/publication/promote',promote_payload,kt,timeout=180)
        if status//100!=2 or not pres.get('ok'):
            con.close();raise RuntimeError(_publication_error('promote',pres))
    alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();alias=str(alias_row[0]) if alias_row else ''
    pstatus,publisher=_post('http://10.62.91.3/publish',{'public_number':num,'deploy_number':dep,'alias':alias},nt,host='cloudif-publisher.internal',timeout=300)
    if pstatus//100!=2 or not publisher.get('ok'):
        con.close();raise RuntimeError(_publication_error('https',publisher))
    if not _external_ok(f'{num}.cloudiff.duckdns.org'):
        con.close();raise RuntimeError('URL estável falhou após ativação.')
    access=_project_access_snapshot(con,slug)
    tenant=str(project['tenant'] if 'tenant' in project.keys() else '')
    con.execute('update project_publications set is_active=0 where project_slug=?',(slug,))
    detail={}
    try:detail=json.loads(row['detail_json'] or '{}')
    except Exception:detail={}
    detail['last_activation']={'at':_now(),'actor':user.get('username') or 'portal','promotion':pres,'publisher':publisher,'rebuilt':rebuilt}
    con.execute('update project_publications set is_active=1,message=?,detail_json=? where project_slug=? and deploy_number=?',('Ativada manualmente pelo Portal',json.dumps(detail,ensure_ascii=False),slug,dep))
    con.commit();con.close()
    membership=_reconcile_publication_members(ku,kt,slug,access)
    queued=_enqueue_membership_reconcile(slug,user.get('username') or 'portal',tenant)
    return {'ok':True,'slug':slug,'public_number':num,'deploy_number':dep,'stable_url':f'https://{num}.cloudiff.duckdns.org/','rebuilt':rebuilt is not None,'runtime':rebuilt,'membership':membership,'reconcile':queued}


# CloudIFF v144 BEGIN - terminal Stack contract and temporary homologation cleanup
_v143_preview_terminal_portal=preview_terminal
def preview_terminal(slug,user):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    from cloudif_project_environment_web import authorization
    auth=authorization(slug,user.get('username') or '',user.get('groups') or [])
    if not auth.get('canWrite'):con.close();raise PermissionError('O terminal do Preview exige permissão de escrita no projeto.')
    num=_number(con,slug);source_link=None;linked_compose=None
    try:
        row=con.execute('select * from project_preview_source_links where project_slug=?',(slug,)).fetchone();source_link=dict(row) if row else None
    except sqlite3.Error:source_link=None
    if _is_linked_compose_project(slug):
        binding=_linked_compose_binding(con,slug);status=_linked_compose_status(slug,num,binding);generation=int(status.get('generation') or _fixed_preview_generation(slug))
        linked_compose={'stack_id':str(binding.get('stackId') or ''),'stack_name':str(binding.get('stackName') or ''),'container':str(status.get('container') or ''),'stage_code':str(status.get('stageCode') or ('W'+str(generation)))}
    con.close();ku,kt,_=_clients();payload={'project':slug,'public_number':num,'actor':user.get('username') or 'portal'}
    if linked_compose and linked_compose.get('stack_id'):
        payload['linked_compose']=linked_compose
    elif source_link and str(source_link.get('status') or '').lower() in {'online','ready','healthy'} and str(source_link.get('app_container') or ''):
        payload['source_link']={'app_container':str(source_link.get('app_container') or ''),'source_commit':str(source_link.get('source_commit') or ''),'stage_code':str(source_link.get('stage_code') or 'W1')}
    else:
        current=preview_status(slug,user);stage=str(current.get('stageCode') or 'W1').strip().upper();match=re.fullmatch(r'W([1-9][0-9]*)',stage);bridge=str(current.get('container') or current.get('bridge') or '')
        if match:
            generation=int(match.group(1));expected_bridge=f'cloudif-p{num}-w{generation}-preview-web'
            if bridge==expected_bridge:payload['composite_app']={'container':f'cloudif-p{num}-w{generation}-preview-app','stage_code':stage}
    status,data=_post(ku+'/komodo/project/preview/terminal',payload,kt,timeout=60)
    if status//100!=2 or data.get('ok') is not True:raise RuntimeError(str(data.get('message') or 'O terminal do Preview está temporariamente indisponível.'))
    container=str(data.get('container') or '');terminal=str(data.get('terminal') or '');generation=int(data.get('generation') or 1)
    if data.get('linkedCompose') is True:
        expected_stack=str((linked_compose or {}).get('stack_id') or '');expected_container=str((linked_compose or {}).get('container') or '');service=str(data.get('service') or '');expected_stage=str((linked_compose or {}).get('stage_code') or ('W'+str(generation)))
        if generation<1 or str(data.get('stack_id') or '')!=expected_stack or (expected_container and container!=expected_container) or not service or not container or not terminal or data.get('target_mode')!='stack' or str(data.get('stageCode') or '')!=expected_stage:raise RuntimeError('linked_compose_preview_terminal_contract_invalid')
        target='https://komodoiff.duckdns.org/stacks/'+urllib.parse.quote(expected_stack,safe='')+'/service/'+urllib.parse.quote(service,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
        return {'ok':True,'project':slug,'public_number':num,'generation':generation,'stageCode':expected_stage,'container':container,'stackId':expected_stack,'service':service,'terminalUrl':target,'terminalReady':True,'terminalSource':'linked_compose_preview_service','linkedCompose':True,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    if data.get('sourceLinked') is True:
        expected=str((source_link or {}).get('app_container') or '');server_id=str(data.get('server_id') or '')
        if generation<1 or container!=expected or not server_id or not terminal or data.get('target_mode')!='container':raise RuntimeError('source_linked_preview_terminal_contract_invalid')
        target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
        return {'ok':True,'project':slug,'public_number':num,'generation':generation,'stageCode':'W'+str(generation),'container':container,'terminalUrl':target,'terminalReady':True,'terminalSource':'source_linked_preview_app','sourceLinked':True,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    if data.get('compositePreview') is True:
        expected=f'cloudif-p{num}-w{generation}-preview-app';server_id=str(data.get('server_id') or '')
        if generation<1 or container!=expected or not server_id or not terminal or data.get('target_mode')!='container':raise RuntimeError('composite_preview_terminal_contract_invalid')
        target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
        return {'ok':True,'project':slug,'public_number':num,'generation':generation,'stageCode':'W'+str(generation),'container':container,'service':'app','terminalUrl':target,'terminalReady':True,'terminalSource':'composite_preview_app','compositePreview':True,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    stack_id=str(data.get('stack_id') or '');expected=f'cloudif-p{num}-preview-web'
    if generation!=1 or container!=expected or not stack_id or not terminal or data.get('target_mode')!='stack':raise RuntimeError('preview_terminal_contract_invalid')
    target='https://komodoiff.duckdns.org/stacks/'+urllib.parse.quote(stack_id,safe='')+'/service/web/terminal/'+urllib.parse.quote(terminal,safe='')
    return {'ok':True,'project':slug,'public_number':num,'generation':1,'stageCode':'W1','container':container,'stackId':stack_id,'terminalUrl':target,'terminalReady':True,'terminalSource':'preview_stack','continuous':True,'secretValuesIncluded':False,'secretReferencesIncluded':False}

_v143_stage_terminal_portal=stage_terminal
def stage_terminal(slug,user,environment='preview'):
    environment=str(environment or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('Ambiente de terminal inválido.')
    if environment=='preview':return preview_terminal(slug,user)
    con=_publication_db(30,True);_ensure_schema(con);project=_project_allowed(con,slug,user)
    if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')
    from cloudif_project_environment_web import authorization
    auth=authorization(slug,user.get('username') or '',user.get('groups') or [])
    if not auth.get('canWrite'):con.close();raise PermissionError('O terminal exige permissão de escrita no projeto.')
    if environment=='production' and not _owner_or_admin(con,slug,user):con.close();raise PermissionError('O terminal de Produção exige o responsável pelo projeto ou administrador.')
    num=_number(con,slug);payload={'project':slug,'public_number':num,'environment':environment,'actor':user.get('username') or 'portal'};stage_code='';deployment_id='';dep=0
    if environment=='homologation':
        row=con.execute("select * from publication_candidates where project_slug=? and status in ('awaiting_homologation','homologated') order by candidate_number desc limit 1",(slug,)).fetchone()
        if not row:con.close();raise RuntimeError('Nenhum candidato temporário de Homologação está disponível.')
        dep=int(row['deploy_number'] or 0);candidate=int(row['candidate_number'] or 0);meta=_candidate_runtime_metadata(row)
        if dep<1 or candidate<1:con.close();raise RuntimeError('O candidato de Homologação não possui runtime válido.')
        if meta.get('runtimeKind')=='compose-snapshot':deployment_id=str(meta.get('homologationDeploymentId') or '')
        payload.update({'deploy_number':dep,'candidate_number':candidate});stage_code=str(row['stage_code'] or ('H'+str(candidate)))
    else:
        release=con.execute("select * from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone()
        if not release:con.close();return _v143_stage_terminal_portal(slug,user,environment)
        publication=int(release['publication_number'] or 0);dep=int(release['deploy_number'] or 0);candidate=int(release['candidate_number'] or 0)
        if publication<1 or dep<1:con.close();raise RuntimeError('A Produção ativa não possui runtime válido.')
        pubrow=con.execute('select detail_json from project_publications where project_slug=? and deploy_number=?',(slug,dep)).fetchone();detail={}
        try:detail=json.loads(pubrow['detail_json'] or '{}') if pubrow else {}
        except Exception:detail={}
        if detail.get('runtimeKind')=='compose-snapshot':deployment_id=str(detail.get('productionDeploymentId') or detail.get('homologationDeploymentId') or '')
        legacy_publication=not bool(deployment_id);payload.update({'publication_number':publication,'deploy_number':dep,'candidate_number':candidate,'legacy':legacy_publication});stage_code=str(release['stage_code'] or ('P'+str(publication)))
        if legacy_publication:payload['container_candidates']=[f'cloudif-p{num}-p{publication}-publication-web']
    deployment_targets=None
    if deployment_id:
        if not re.fullmatch(r'dep_[a-f0-9]{24}',deployment_id):con.close();raise RuntimeError('O deployment deste ambiente é inválido para Terminal.')
        deployment_targets=_compose_deployment_runtime_targets(slug,deployment_id)
        payload['deployment_id']=deployment_id;payload['container_candidates']=deployment_targets['containers'];payload['service_candidates']=deployment_targets['services']
    con.close();ku,kt,_=_clients();status,data=_post(ku+'/komodo/project/stage/terminal',payload,kt,timeout=60)
    if status//100!=2 or data.get('ok') is not True:raise RuntimeError(str(data.get('message') or data.get('error') or 'O terminal deste ambiente está temporariamente indisponível.'))
    container=str(data.get('container') or '');terminal=str(data.get('terminal') or '');mode=str(data.get('target_mode') or '')
    if deployment_id:
        server_id=str(data.get('server_id') or '');service=str(data.get('service') or '');allowed={(x['container'],x['service']) for x in (deployment_targets or {}).get('targets',[])}
        if mode!='container' or (container,service) not in allowed or str(data.get('deployment_id') or '')!=deployment_id or not server_id or not terminal:raise RuntimeError('stage_terminal_compose_contract_invalid')
        target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
        return {'ok':True,'project':slug,'public_number':num,'environment':environment,'stageCode':stage_code,'container':container,'service':service,'deploymentId':deployment_id,'terminalUrl':target,'terminalReady':True,'terminalSource':'compose_deployment_service','sameRuntimeAcrossPromotion':True,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    if environment=='production' and data.get('legacyPublication') is True:
        expected=f'cloudif-p{num}-p{publication}-publication-web';server_id=str(data.get('server_id') or '');service=str(data.get('service') or '')
        if mode!='container' or container!=expected or service!='web' or not server_id or not terminal:raise RuntimeError('stage_terminal_legacy_contract_invalid')
        target='https://komodoiff.duckdns.org/servers/'+urllib.parse.quote(server_id,safe='')+'/container/'+urllib.parse.quote(container,safe='')+'/terminal/'+urllib.parse.quote(terminal,safe='')
        return {'ok':True,'project':slug,'public_number':num,'environment':environment,'stageCode':stage_code,'container':container,'service':'web','terminalUrl':target,'terminalReady':True,'terminalSource':'legacy_publication_container','sameRuntimeAcrossPromotion':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}
    stack_id=str(data.get('stack_id') or '');expected=f'cloudif-p{num}-d{dep}-web'
    if container!=expected or not stack_id or not terminal or mode!='stack':raise RuntimeError('stage_terminal_contract_invalid')
    target='https://komodoiff.duckdns.org/stacks/'+urllib.parse.quote(stack_id,safe='')+'/service/web/terminal/'+urllib.parse.quote(terminal,safe='')
    return {'ok':True,'project':slug,'public_number':num,'environment':environment,'stageCode':stage_code,'container':container,'stackId':stack_id,'terminalUrl':target,'terminalReady':True,'terminalSource':'publication_stack','sameRuntimeAcrossPromotion':environment=='production','secretValuesIncluded':False,'secretReferencesIncluded':False}


_v143_homologate_candidate=homologate_candidate
def homologate_candidate(slug,candidate_number,user,decision='approved',note=''):
    decision=str(decision or '').strip().lower()
    if decision!='rejected':
        result=_v143_homologate_candidate(slug,candidate_number,user,decision,note);_rm.project_changed(slug,'homologation-'+decision);return result
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    row=con.execute('select * from publication_candidates where project_slug=? and candidate_number=?',(slug,int(candidate_number))).fetchone()
    if not row:con.close();raise ValueError('Candidato não encontrado.')
    runtime_meta=_candidate_runtime_metadata(row);num=int(row['public_number']);dep=int(row['deploy_number']);con.close()
    result=_v143_homologate_candidate(slug,candidate_number,user,decision,note)
    cleanup={'ok':True,'skipped':False}
    kind=str(runtime_meta.get('runtimeKind') or '')
    if kind not in {'multiservice','compose-snapshot'}:
        ku,kt,_=_clients();status,data=_post(ku+'/komodo/publication/reject',{'project':slug,'public_number':num,'deploy_number':dep,'candidate_number':int(candidate_number)},kt,timeout=240)
        cleanup={'ok':status//100==2 and data.get('ok') is not False,'status':status,'result':data}
    else:
        cleanup={'ok':True,'skipped':True,'reason':'broker_managed_runtime'}
    try:
        _,_,nt=_clients()
        pstatus,pdata=_post('http://10.62.91.3/stage/delete',{'public_number':num,'stage':'homologation','number':int(candidate_number)},nt,host='cloudif-publisher.internal',timeout=120)
        cleanup['publisher']={'ok':pstatus//100==2 and pdata.get('ok') is not False,'status':pstatus}
    except Exception as exc:
        cleanup['publisher']={'ok':False,'error':type(exc).__name__}
    result['runtimeCleanup']=cleanup
    _rm.project_changed(slug,'homologation-rejected')
    return result

# CloudIFF v144 END

_v144_publish_homologated_candidate_base=publish_homologated_candidate
def publish_homologated_candidate(slug,candidate_number,user,progress=None,publication_number=None,authorization_checked=False):
    result=_v144_publish_homologated_candidate_base(slug,candidate_number,user,progress,publication_number,authorization_checked)
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
        row=con.execute('select public_number from publication_candidates where project_slug=? and candidate_number=?',(slug,int(candidate_number))).fetchone();con.close()
        if row:
            _,_,nt=_clients();status,data=_post('http://10.62.91.3/stage/delete',{'public_number':int(row['public_number']),'stage':'homologation','number':int(candidate_number)},nt,host='cloudif-publisher.internal',timeout=120)
            result['homologationStageRemoved']=bool(status//100==2 and data.get('ok') is not False)
    except Exception as exc:
        result['homologationStageRemoved']=False;result['homologationStageCleanupError']=type(exc).__name__
    _rm.project_changed(slug,'production-published')
    return result

_v144_ensure_preview_base=ensure_preview
def ensure_preview(slug,user):
    result=_v144_ensure_preview_base(slug,user)
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=con.execute('select * from projects where slug=?',(slug,)).fetchone();tenant=str(project['tenant'] if project and 'tenant' in project.keys() else '');con.close()
        result['reconcile']=_enqueue_membership_reconcile(slug,user.get('username') or 'portal',tenant)
    except Exception as exc:result['reconcile']={'ok':False,'error':type(exc).__name__}
    _rm.project_changed(slug,'preview-ensured')
    return result

_v144_create_homologation_candidate_base=create_homologation_candidate
def create_homologation_candidate(slug,user,progress=None,candidate_number=None,authorization_checked=False):
    result=_v144_create_homologation_candidate_base(slug,user,progress,candidate_number,authorization_checked)
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);project=con.execute('select * from projects where slug=?',(slug,)).fetchone();tenant=str(project['tenant'] if project and 'tenant' in project.keys() else '');con.close()
        result['reconcile']=_enqueue_membership_reconcile(slug,user.get('username') or 'portal',tenant)
    except Exception as exc:result['reconcile']={'ok':False,'error':type(exc).__name__}
    _rm.project_changed(slug,'homologation-created')
    return result

def _executor_runtime_client():
    cfg=_env('/etc/cloudif/multiservice-deployment-executor.env');token=cfg.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN','')
    if not token:raise RuntimeError('Credencial interna do executor ausente.')
    return 'http://10.62.91.2:18098/cloudif/executor',token

def _remove_compose_runtime(deployment_id):
    base,token=_executor_runtime_client();status,result=_bearer_json('DELETE',base+'/v1/deployments/'+urllib.parse.quote(str(deployment_id),safe=''),token,timeout=180)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('Não foi possível remover o runtime da Homologação substituída.')
    return result

def _rehydrate_historical_compose_runtime(slug,publication,row,detail):
    snapshot_id=str(detail.get('composeSnapshotId') or '');snapshot_digest=str(detail.get('snapshotDigest') or '');environment_digest=str(row['environment_digest'] or '')
    if not re.fullmatch(r'snap_[a-f0-9]{24}',snapshot_id) or not re.fullmatch(r'[a-f0-9]{64}',snapshot_digest) or not re.fullmatch(r'[a-f0-9]{64}',environment_digest):raise RuntimeError('A publicação histórica não possui identidade de snapshot reidratável.')
    deleted_at=str(detail.get('runtimeDeletedAt') or '');material='historical-rehydrate|'+slug+'|'+str(publication)+'|'+snapshot_id+'|'+snapshot_digest+'|'+deleted_at;deployment_id='dep_'+hashlib.sha256(material.encode()).hexdigest()[:24]
    base,token=_executor_runtime_client();status,result=_bearer_json('POST',base+'/v1/compose-snapshots/rehydrate-historical',token,{'deployment_id':deployment_id,'project_slug':slug,'snapshot_id':snapshot_id,'snapshot_digest':snapshot_digest,'historical_environment_digest':environment_digest},timeout=1200)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('Não foi possível reidratar a publicação histórica pelo snapshot aprovado.')
    if str(result.get('deployment_id') or '')!=deployment_id or str(result.get('snapshot_id') or '')!=snapshot_id or str(result.get('snapshot_digest') or '')!=snapshot_digest or str(result.get('environment') or '')!='production' or result.get('rehydratedThroughHomologation') is not True:raise RuntimeError('A reidratação histórica retornou identidade divergente.')
    return result

# Reconciled live lifecycle helpers — 2026-11-22
def _active_compose_environment_target(slug,environment):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    try:
        if environment=='homologation':
            rows=con.execute("select * from publication_candidates where project_slug=? and status in ('awaiting_homologation','homologated') order by candidate_number desc",(slug,)).fetchall()
            for row in rows:
                meta=_candidate_runtime_metadata(row);dep=str(meta.get('homologationDeploymentId') or '')
                if meta.get('sameInstancePromotionRequired') is True and re.fullmatch(r'dep_[a-f0-9]{24}',dep):
                    return {'deploymentId':dep,'rowId':int(row['id']),'candidateNumber':int(row['candidate_number']),'hostname':str(row['hostname'] or ''),'kind':'candidate'}
            raise RuntimeError('Nenhuma Homologação ativa existe para receber variáveis.')
        if environment=='production':
            release=con.execute("select * from production_releases where project_slug=? and is_active=1 and status='published' order by publication_number desc limit 1",(slug,)).fetchone()
            if not release:raise RuntimeError('Nenhuma Produção ativa existe para receber variáveis.')
            candidate=con.execute('select * from publication_candidates where project_slug=? and candidate_number=?',(slug,int(release['candidate_number']))).fetchone()
            meta=_candidate_runtime_metadata(candidate) if candidate else {};dep=str(meta.get('homologationDeploymentId') or '')
            if not re.fullmatch(r'dep_[a-f0-9]{24}',dep):
                publication=con.execute('select detail_json from project_publications where project_slug=? and is_active=1 order by id desc limit 1',(slug,)).fetchone()
                try:detail=json.loads(publication['detail_json'] or '{}') if publication else {}
                except Exception:detail={}
                dep=str(detail.get('productionDeploymentId') or '')
            if not re.fullmatch(r'dep_[a-f0-9]{24}',dep):raise RuntimeError('Produção ativa não possui deployment configurável.')
            return {'deploymentId':dep,'releaseId':int(release['id']),'candidateNumber':int(release['candidate_number']),'publicationNumber':int(release['publication_number']),'hostname':str(release['stable_hostname'] or release['hostname'] or ''),'kind':'release'}
        raise ValueError('Ambiente não possui target Compose configurável.')
    finally:con.close()

def _compose_snapshot_promote(slug,deployment_id,snapshot_id,snapshot_digest,trace,execution_material):
    client=_multiservice_clients();plan_payload={'project_slug':slug,'deployment_id':deployment_id,'snapshot_id':snapshot_id,'snapshot_digest':snapshot_digest,'trace_id':trace}
    status,plan=_bearer_json('POST',client['deploymentUrl']+'/v1/compose-promotion-plan',client['deploymentToken'],plan_payload,timeout=75)
    if status!=200 or plan.get('ok') is not True:raise RuntimeError('O plano de promoção da Homologação não pôde ser criado.')
    blockers=plan.get('blockers') or []
    if plan.get('execution_allowed') is not True or blockers:raise RuntimeError('Promoção da Homologação bloqueada: '+','.join(str(x) for x in blockers[:12]))
    if plan.get('sameDeploymentRequired') is not True or plan.get('containerRecreationForbidden') is not True:raise RuntimeError('O plano não garante promoção da mesma instância homologada.')
    digest=str(plan.get('promotion_plan_digest') or '')
    if not re.fullmatch(r'[a-f0-9]{64}',digest):raise RuntimeError('Digest do plano de promoção inválido.')
    execution_id='exec_'+hashlib.sha256(str(execution_material).encode()).hexdigest()[:24]
    payload={**plan_payload,'promotion_plan_digest':digest,'execution_id':execution_id}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/compose-promotion-execute',client['deploymentToken'],payload,timeout=300)
    if status//100!=2 or result.get('ok') is not True:raise RuntimeError('O Deployment Broker não conseguiu promover a Homologação em Produção.')
    if str(result.get('deployment_id') or '')!=deployment_id or result.get('sameHomologatedDeployment') is not True or result.get('containersRecreated') is not False:raise RuntimeError('A promoção alterou a identidade da Homologação.')
    return plan,result

def _legacy_publication_deactivate(slug,public_number,publication_number):
    ku,kt,_=_clients();payload={'project':slug,'public_number':int(public_number),'publication_number':int(publication_number)}
    status,result=_post(ku+'/komodo/publication/deactivate-legacy',payload,kt,timeout=90)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('Não foi possível desativar a Produção legada anterior.')
    return result

def _linked_compose_previous_active_homologation(slug):
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
    row=con.execute("select * from publication_candidates where project_slug=? and status in ('awaiting_homologation','homologated') order by candidate_number desc limit 1",(slug,)).fetchone();con.close()
    if not row:return None
    meta=_candidate_runtime_metadata(row);dep=str(meta.get('homologationDeploymentId') or '')
    return {'candidateNumber':int(row['candidate_number']),'deploymentId':dep} if re.fullmatch(r'dep_[a-f0-9]{24}',dep) else None

def _multiservice_deactivate(slug,deployment_id,reason,trace):
    client=_multiservice_clients();payload={'project_slug':slug,'deployment_id':deployment_id,'reason':reason,'trace_id':trace}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-deactivate',client['deploymentToken'],payload,timeout=180)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('Não foi possível desativar o deployment anterior.')
    return result

def _multiservice_deactivate_bridge(slug,deployment_id,stage,trace):
    client=_multiservice_clients();payload={'project_slug':slug,'deployment_id':deployment_id,'stage':stage,'trace_id':trace}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-publication-deactivate',client['deploymentToken'],payload,timeout=90)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('Não foi possível desativar o bridge '+stage+' do deployment.')
    return result

def _multiservice_reactivate(slug,deployment_id,phase,environment_digest,trace):
    client=_multiservice_clients();payload={'project_slug':slug,'deployment_id':deployment_id,'phase':phase,'environment_digest':environment_digest,'trace_id':trace}
    status,result=_bearer_json('POST',client['deploymentUrl']+'/v1/multiservice-reactivate',client['deploymentToken'],payload,timeout=360)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:
        error=result.get('error') if isinstance(result,dict) else {}
        message=error.get('message') if isinstance(error,dict) else ''
        raise RuntimeError(message or 'Não foi possível reativar a publicação histórica.')
    return result

def _multiservice_remove_deployment(slug,deployment_id):
    client=_multiservice_clients();status,result=_bearer_json('DELETE',client['deploymentUrl']+'/v1/deployments/'+urllib.parse.quote(str(deployment_id),safe=''),client['deploymentToken'],timeout=120)
    if status//100!=2 or not isinstance(result,dict) or result.get('ok') is not True:raise RuntimeError('Não foi possível excluir os containers da publicação histórica.')
    return result

def _publisher_delete_stage(public_number,stage,number,npm_token):
    if stage not in {'preview','homologation','publication'}:raise RuntimeError('Estágio inválido para remoção no Publisher.')
    status,data=_post('http://10.62.91.3/stage/delete',{'public_number':int(public_number),'stage':stage,'number':int(number)},npm_token,host='cloudif-publisher.internal',timeout=120)
    if status//100!=2 or not isinstance(data,dict) or data.get('ok') is not True:raise RuntimeError('O Publisher não conseguiu remover o estágio '+stage+'.')
    return {'ok':True,'removed':bool(data.get('removed')),'certificatePreserved':bool(data.get('certificate_preserved'))}

def apply_environment_to_runtime(slug,environment,actor='portal'):
    environment=str(environment or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('Ambiente inválido.')
    pc=_publication_config();runtime=pc.execution_environment_services(slug,environment)
    values=runtime.get('valuesByService') or {};names=runtime.get('managedNamesByService') or {}
    material={'managed_names_by_service':names,'values_by_service':values};variables_digest=hashlib.sha256(json.dumps(material,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        if environment=='preview':
            if slug=='agenda-unica' or _is_linked_compose_project(slug):
                ku,kt,_=_clients();status,result=_post(ku+'/komodo/project/linked-preview/environment/apply',{'project':slug,'actor':actor,'values_by_service':values,'managed_names_by_service':names,'variables_digest':variables_digest,'environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest'])},kt,timeout=360)
                if status//100!=2 or result.get('ok') is not True:raise RuntimeError(str(result.get('message') or result.get('error') or 'Falha ao aplicar variáveis no Preview.'))
            else:
                con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con);num=_number(con,slug);con.close();flat={}
                for service_values in values.values():
                    for key,value in service_values.items():
                        if key in flat and flat[key]!=value:raise RuntimeError('Variável global possui valores conflitantes entre serviços: '+key)
                        flat[key]=value
                result=_runtime_preview(slug,num,'ensure',{'actor':actor,'environment_revision':int(runtime['environmentRevision']),'environment_digest':str(runtime['environmentDigest']),'environment_variables':flat},240)
            return {'ok':True,'environment':'preview','environmentRevision':int(runtime['environmentRevision']),'environmentDigest':str(runtime['environmentDigest']),'changedServices':result.get('changedServices') or [],'containersRecreated':bool(result.get('containersRecreated')),'databasePreserved':bool(result.get('databasePreserved',True)),'secretValuesIncluded':False}
        target=_active_compose_environment_target(slug,environment);base,token=_executor_runtime_client()
        payload={'deployment_id':target['deploymentId'],'project_slug':slug,'environment':environment,'values_by_service':values,'managed_names_by_service':names,'variables_digest':variables_digest,'runtime_environment_digest':str(runtime.get('runtimeEnvironmentDigest') or runtime['environmentDigest']),'environment_digest':str(runtime['environmentDigest'])}
        status,result=_bearer_json('POST',base+'/v1/compose-deployments/reconfigure',token,payload,timeout=360)
        if status//100!=2 or result.get('ok') is not True:
            error=result.get('error') or {};message=error.get('message') if isinstance(error,dict) else str(error or '')
            raise RuntimeError(message or 'Falha ao aplicar variáveis no runtime do estágio.')
        if target.get('hostname') and not _external_ok(str(target['hostname'])):raise RuntimeError('Runtime reconfigurado, mas a validação HTTPS do estágio falhou.')
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row;_ensure_schema(con)
        if environment=='homologation':con.execute('update publication_candidates set environment_revision=?,environment_digest=? where id=?',(int(runtime['environmentRevision']),str(runtime['environmentDigest']),int(target['rowId'])))
        else:
            con.execute('update production_releases set environment_revision=?,environment_digest=? where id=?',(int(runtime['environmentRevision']),str(runtime['environmentDigest']),int(target['releaseId'])))
            prow=con.execute('select id,detail_json from project_publications where project_slug=? and is_active=1 order by id desc limit 1',(slug,)).fetchone()
            if prow:
                try:detail=json.loads(prow['detail_json'] or '{}')
                except Exception:detail={}
                detail['environmentRevision']=int(runtime['environmentRevision']);detail['environmentDigest']=str(runtime['environmentDigest']);con.execute('update project_publications set detail_json=? where id=?',(json.dumps(detail,ensure_ascii=False,separators=(',',':')),int(prow['id'])))
        con.commit();con.close()
        return {'ok':True,'environment':environment,'deploymentId':target['deploymentId'],'environmentRevision':int(runtime['environmentRevision']),'environmentDigest':str(runtime['environmentDigest']),'changedServices':result.get('changedServices') or [],'deploymentIdentityPreserved':bool(result.get('deploymentIdentityPreserved')),'snapshotPreserved':bool(result.get('snapshotPreserved')),'volumesPreserved':bool(result.get('volumesPreserved')),'containersRecreated':bool(result.get('containersRecreated')),'secretValuesIncluded':False}
    finally:
        for service_values in values.values():
            if isinstance(service_values,dict):service_values.clear()
        runtime['valuesByService']={}

def environment_runtime_target(slug,environment):
    environment=str(environment or '').strip().lower()
    if environment=='preview':
        if slug=='agenda-unica' or _is_linked_compose_project(slug):return {'environment':'preview','kind':'linked-preview'}
        return {'environment':'preview','kind':'preview'}
    if environment in {'homologation','production'}:
        target=_active_compose_environment_target(slug,environment);target['environment']=environment;return target
    raise ValueError('Ambiente inválido.')

def _wait_deployment_inactive(deployment_id,timeout_seconds=45):
    deadline=time.time()+max(5,int(timeout_seconds));last={}
    while time.time()<deadline:
        last=_compose_deployment_status(deployment_id)
        status=str(last.get('status') or '').lower()
        if status in {'inactive','removed'}:
            return {'ok':True,'deploymentId':deployment_id,'status':status}
        time.sleep(1.0)
    raise RuntimeError('A Produção anterior não confirmou estado Offline após a ativação da nova Produção.')
