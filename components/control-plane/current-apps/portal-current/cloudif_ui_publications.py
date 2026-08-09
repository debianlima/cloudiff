#!/usr/bin/env python3
import html
import json
import sqlite3
import glob
import os
import urllib.request

DB='/var/lib/cloudif/portal/cloudif-portal.db'

def h(value):
    return html.escape(str(value if value is not None else ''), quote=True)

def _rows(slug):
    try:
        con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
        rows=[dict(x) for x in con.execute("select * from project_publications where project_slug=? and status='published' order by deploy_number desc",(slug,))]
        con.close(); return rows
    except Exception:
        return []

def _runtime_from_job(slug):
    paths=sorted(glob.glob('/srv/cloudif/jobs/project-provision-*-'+slug+'.json'),key=lambda x:os.path.getmtime(x),reverse=True)
    for path in paths:
        try:
            job=json.load(open(path)); runtime=str(job.get('runtime_template') or ''); php=str(job.get('php_version') or '')
            node=runtime.replace('node','') if runtime.startswith('node') else ''
            if node or php:
                return {'node':node or '—','php':php or '—','apache':'2.4','environment':'Apache + PHP + Node.js','versions':f"Apache 2.4 · PHP {php or '—'} · Node.js {node or '—'}",'framework':'Aplicação PHP com API Node.js'}
        except Exception: pass
    return {}

def _komodo_web_status(slug,stack_id=''):
    env={}
    try:
        for raw in open('/etc/cloudif/komodo-agent-client.env'):
            if '=' in raw and not raw.lstrip().startswith('#'):
                k,v=raw.rstrip().split('=',1);env[k]=v.strip().strip('"').strip("'")
    except Exception:return {}
    base=(env.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/');token=env.get('KOMODO_AGENT_TOKEN') or ''
    if not token:return {}
    payload=json.dumps({'project':slug,'stack_id':stack_id,'service':'web','terminal':'cloudif-'+slug,'shell':'sh'}).encode()
    req=urllib.request.Request(base+'/komodo/project/audit',data=payload,method='POST',headers={'Content-Type':'application/json','X-CloudIF-Token':token,'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=12) as r:return json.loads(r.read().decode())
    except Exception:return {}

def _project_context(slug, framework_hint=''):
    context={'slug':slug,'framework':framework_hint or '', 'database':'', 'repo_url':'', 'security':'Aguardando publicação','service_status':'Não verificado','runtime':{}}
    try:
        con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
        project=con.execute('select * from projects where slug=?',(slug,)).fetchone()
        if project:
            keys=set(project.keys())
            context['repo_url']=str(project['repo_url'] or '') if 'repo_url' in keys else ''
            context['database']=str((project['tenant_default'] if 'tenant_default' in keys else '') or (project['tenant'] if 'tenant' in keys else '') or '')
        try:
            integration=con.execute('select * from project_integrations where project=?',(slug,)).fetchone()
            stack_id=str((integration['komodo_stack_id'] if integration and 'komodo_stack_id' in integration.keys() else '') or (integration['stack_id'] if integration and 'stack_id' in integration.keys() else '') or '')
        except Exception: stack_id=''
        runtime=_runtime_from_job(slug); context['runtime']=runtime
        audit=_komodo_web_status(slug,stack_id)
        if audit:
            healthy=bool(audit.get('healthy')); state=str(audit.get('state') or ('running' if healthy else 'atenção'))
            context['service_status']='Rodando e saudável' if healthy else state
            if healthy: context['security']='HTTPS ativo · Health validado'
        if runtime and not context['framework']: context['framework']=runtime.get('framework') or 'Aplicação web'
        if not context['database']:
            try:
                tenant=con.execute('select tenant from project_tenants where project=? order by is_primary desc,id limit 1',(slug,)).fetchone()
                context['database']=str(tenant['tenant'] or '') if tenant else ''
            except Exception:
                pass
        active=con.execute("select detail_json from project_publications where project_slug=? and status='published' and is_active=1 order by id desc limit 1",(slug,)).fetchone()
        if active:
            try:detail=json.loads(active['detail_json'] or '{}')
            except Exception:detail={}
            komodo=detail.get('komodo') or {}
            source=komodo.get('publication_source') or ''
            if not context['framework']:
                if source in {'site','dist','build','public','root'} and not context.get('runtime'):context['framework']='Site estático'
                elif komodo.get('generated_placeholder'):context['framework']='Não identificado'
            context['security']='HTTPS ativo' + (' · Health validado' if komodo.get('healthy') else '')
        con.close()
    except Exception:
        pass
    context['framework']=context['framework'] or 'Não identificado'
    context['database']=context['database'] or 'Nenhum banco vinculado'
    return context


def _project_information(context):
    repo=context.get('repo_url') or ''
    database=context.get('database') or ''
    repo_value=(f'<a href="{h(repo)}" target="_blank" rel="noopener">Abrir repositório</a>' if repo else '<span>Nenhum repositório vinculado</span>')
    if database and database!='Nenhum banco vinculado':
        studio=f'https://{database}.cloudiff.duckdns.org/project/default'
        database_value=f'<a class="publication-database-link" href="{h(studio)}" target="_blank" rel="noopener" title="Abrir Studio do banco">{h(database)}</a>'
    else:
        database_value=f'<strong>{h(database or "Nenhum banco vinculado")}</strong>'
    return (
        '<div class="publication-information">'
        f'<div class="publication-info-card publication-runtime-card"><span>PHP</span><strong>Configuração do PHP</strong><small>Versão, módulos e parâmetros ativos</small><a class="publication-runtime-text" data-publication-environments data-publication-tool="php" data-project-slug="{h(context.get("slug") or "")}" href="/cloudiff/portal/action/project-runtime-info?slug={h(context.get("slug") or "")}&amp;kind=php" target="_blank" rel="noopener">Ver informações do PHP</a></div>'
        f'<div class="publication-info-card publication-runtime-card"><span>Node.js</span><strong>Runtime do Node.js</strong><small>Versões, npm e dependências da API</small><a class="publication-runtime-text" data-publication-environments data-publication-tool="node" data-project-slug="{h(context.get("slug") or "")}" href="/cloudiff/portal/action/project-runtime-info?slug={h(context.get("slug") or "")}&amp;kind=node" target="_blank" rel="noopener">Ver informações do Node.js</a></div>'
        f'<div class="publication-info-card publication-runtime-card"><span>Site</span><strong>Preview do site</strong><small>Visualize Preview, Homologação e Produção pela URL real</small><a class="publication-runtime-text publication-card-action" data-publication-environments data-publication-tool="site" data-project-slug="{h(context.get("slug") or "")}" href="/cloudiff/portal/?tab=publicacao">Visualizar sites</a></div>'
        f'<div class="publication-info-card publication-runtime-card"><span>Terminal</span><strong>Terminal do ambiente</strong><small>Abra o container correspondente no Komodo</small><a class="publication-runtime-text publication-card-action" data-publication-environments data-publication-tool="terminal" data-project-slug="{h(context.get("slug") or "")}" href="/cloudiff/portal/?tab=publicacao">Abrir terminal</a></div>'
        f'<div class="publication-info-card"><span>Versões</span><strong>{h((context.get("runtime") or {}).get("versions") or "Não identificadas")}</strong><small>Runtime provisionado</small></div>'
        f'<div class="publication-info-card"><span>Serviço web</span><strong>{h(context.get("service_status"))}</strong><small>Estado real do container</small></div>'
        f'<div class="publication-info-card"><span>Banco vinculado</span>{database_value}<small>Tenant da aplicação</small></div>'
        f'<div class="publication-info-card"><span>Segurança</span><strong>{h(context.get("security"))}</strong><small>HTTPS e healthcheck</small></div>'
        f'<div class="publication-info-card publication-info-wide"><span>Repositório Forge</span>{repo_value}<small>Código-fonte do projeto</small></div>'
        '</div>'
    )


def _publication_snapshot_from_rows(rows):
    active=next((x for x in rows if int(x.get('is_active') or 0)==1),rows[0] if rows else {})
    try:detail=json.loads(active.get('detail_json') or '{}') if active else {}
    except Exception:detail={}
    snapshot=detail.get('snapshot') if isinstance(detail.get('snapshot'),dict) else {}
    return snapshot

def _configuration_controls(slug,rows):
    return (
      '<section class="publication-release-flow" data-release-flow-summary="'+h(slug)+'">'
      '<div class="publication-release-flow__head"><div><span>Fluxo de publicação</span><strong>Preview → Homologação → Publicação</strong><p>Desenvolva no Preview vivo, homologue um candidato imutável e publique exatamente o mesmo artefato.</p></div>'
      '<button class="btn" type="button" data-release-flow-open data-project-slug="'+h(slug)+'">Gerenciar publicação</button></div>'
      '<div class="publication-release-flow__stages" aria-label="Estágios da publicação">'
      '<article><span class="publication-stage-code">W</span><div><strong>Preview</strong><small>Workspace vivo</small></div><span class="publication-stage-state" data-release-summary-w>Consultar</span></article>'
      '<article><span class="publication-stage-code">H</span><div><strong>Homologação</strong><small>Candidato imutável</small></div><span class="publication-stage-state" data-release-summary-h>Consultar</span></article>'
      '<article><span class="publication-stage-code">P</span><div><strong>Publicação</strong><small>Produção aprovada</small></div><span class="publication-stage-state" data-release-summary-p>Consultar</span></article>'
      '</div><div class="publication-release-flow__tools"><button class="btn light" type="button" data-publication-environments data-publication-tool="variables" data-project-slug="'+h(slug)+'">Variáveis por ambiente</button></div></section>'
    )

def publication_panel(slug, framework_hint=''):
    rows=_rows(slug);context=_project_context(slug,framework_hint);information=_project_information(context);configuration=_configuration_controls(slug,rows)
    try:
        from cloudif_portal_publications import latest_job
        job=latest_job(slug)
    except Exception:job=None
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
    try:
        alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();alias=str(alias_row['alias']) if alias_row else ''
    except Exception:alias=''
    finally:con.close()
    job_html=''
    if job and job.get('status') in ('queued','running','failed'):
        labels={'queued':'Na fila','running':'Em andamento','failed':'Atenção'};progress={'queued':1,'preparing':2,'snapshot':2,'deploying':3,'https':4,'production':4,'completed':5}.get(job.get('step'),1)
        job_html=(f'<div class="publication-job is-{h(job.get("status"))}" data-publication-job="{int(job.get("id") or 0)}"><div class="publication-job-copy"><div><strong>{h(labels.get(job.get("status"),job.get("status") or ""))}</strong><span>{h(job.get("message") or "")}</span></div></div><progress max="5" value="{progress}"></progress></div>')
    if alias:
        alias_host=alias+'.cloudiff.duckdns.org';alias_html=('<div class="publication-alias is-saved"><div class="publication-alias-view"><div><span>Endereço amigável</span><a href="https://'+h(alias_host)+'/" target="_blank" rel="noopener">'+h(alias_host)+'</a></div><button class="btn light" type="button" data-alias-edit>Editar endereço</button></div><form class="publication-alias-form" hidden method="post" action="/cloudiff/portal/action/publication"><input type="hidden" name="slug" value="'+h(slug)+'"><label><span>Novo endereço</span><div><input name="alias" value="'+h(alias)+'" pattern="[a-z0-9][a-z0-9-]{0,62}"><span>.cloudiff.duckdns.org</span></div></label><div class="publication-alias-actions"><button class="btn" name="op" value="set_alias">Salvar</button><button class="btn light" type="button" data-alias-cancel>Cancelar</button></div></form></div>')
    else:
        alias_html=('<div class="publication-alias"><div><strong>Endereço amigável de Produção</strong><p>Opcional. O alias sempre acompanha a publicação P ativa.</p></div><form method="post" action="/cloudiff/portal/action/publication"><input type="hidden" name="slug" value="'+h(slug)+'"><label><span>Nome</span><div><input name="alias" placeholder="ex.: meu-site" pattern="[a-z0-9][a-z0-9-]{0,62}"><span>.cloudiff.duckdns.org</span></div></label><button class="btn light" name="op" value="set_alias">Salvar endereço</button></form></div>')
    active=next((x for x in rows if int(x.get('is_active') or 0)==1),rows[0] if rows else None)
    if active:
        stable=active.get('stable_hostname') or f"{int(active.get('public_number') or 0)}.cloudiff.duckdns.org";active_host=(alias+'.cloudiff.duckdns.org') if alias else stable
        production=('<div class="publication-active-card"><div><span>Produção atual</span><a href="https://'+h(active_host)+'/" target="_blank" rel="noopener">'+h(active_host)+'</a></div><span class="pill ok">Online</span></div>')
    else:production='<div class="publication-active-card"><div><span>Produção atual</span><strong>Ainda não publicada</strong></div><span class="pill warn">Sem P ativa</span></div>'
    history=''
    if rows:
        trs=[]
        for r in rows:
            dep=int(r.get('deploy_number') or 0);trs.append(f'<tr><td>d{dep}</td><td><code>{h((r.get("commit_sha") or "")[:12])}</code></td><td><a href="https://{h(r.get("version_hostname") or "")}/" target="_blank" rel="noopener">Abrir</a></td><td>{"ativa" if int(r.get("is_active") or 0)==1 else h(r.get("status") or "")}</td></tr>')
        history='<details class="publication-technical-history"><summary>Detalhes técnicos e versões legadas</summary><div style="overflow:auto"><table><tr><th>Artefato</th><th>Commit</th><th>URL técnica</th><th>Estado</th></tr>'+''.join(trs)+'</table></div></details>'
    return '<div class="cm-resource publication-manager-resource">'+configuration+job_html+production+alias_html+history+information+'</div>'

def admin_publications():
    try:
        con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
        rows=[dict(x) for x in con.execute('select pp.*,p.name,p.created_by from project_publications pp left join projects p on p.slug=pp.project_slug order by pp.created_at desc limit 500')]
        con.close()
    except Exception as exc:
        return f'<div class="cm-card"><h3>Publicações</h3><p>{h(exc)}</p></div>'
    trs=[]
    for r in rows:
        state='<span class="pill ok">Ativa</span>' if int(r.get('is_active') or 0)==1 else h(r.get('status') or '')
        trs.append(
            f'<tr><td>{h(r.get("project_slug") or "")}</td><td>{h(r.get("created_by") or "")}</td>'
            f'<td>d{int(r.get("deploy_number") or 0)}</td><td>{state}</td>'
            f'<td><a href="https://{h(r.get("version_hostname") or "")}/" target="_blank">Abrir</a></td>'
            f'<td><code>{h((r.get("commit_sha") or "")[:12])}</code></td></tr>'
        )
    body=''.join(trs) if trs else '<tr><td colspan="6">Nenhuma publicação.</td></tr>'
    return (
        '<div class="cm-card"><h3>Todas as publicações</h3>'
        '<p class="cm-muted">Visão administrativa de projetos, versões, estado ativo e commit.</p>'
        '<div style="overflow:auto"><table><tr><th>Projeto</th><th>Usuário</th><th>Versão</th><th>Estado</th><th>URL</th><th>Commit</th></tr>'
        + body + '</table></div></div>'
    )
