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
                return {'node':node or '—','php':php or '—','apache':'2.4','label':f"Apache 2.4 + PHP {php or '—'} + Node.js {node or '—'}"}
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
    context={'framework':framework_hint or '', 'database':'', 'repo_url':'', 'security':'Aguardando publicação','service_status':'Não verificado','runtime':{}}
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
        if context['service_status']!='Rodando e saudável':
            try:
                jobs=sorted(glob.glob('/srv/cloudif/jobs/project-provision-*-'+slug+'.json'),key=lambda x:os.path.getmtime(x),reverse=True)
                if jobs and json.load(open(jobs[0])).get('status')=='succeeded':
                    context['service_status']='Rodando e saudável'; context['security']='HTTPS ativo · Health validado'
            except Exception: pass
        if runtime and not context['framework']: context['framework']=runtime.get('label') or ''
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
        f'<div><span>Framework</span><strong>{h(context.get("framework"))}</strong></div>'
        f'<div><span>Serviço web</span><strong>{h(context.get("service_status"))}</strong></div>'
        f'<div><span>Versões</span><strong>{h((context.get("runtime") or {}).get("label") or context.get("framework"))}</strong></div>'
        f'<div><span>Banco vinculado</span>{database_value}</div>'
        f'<div><span>Segurança</span><strong>{h(context.get("security"))}</strong></div>'
        f'<div><span>Repositório Forge</span>{repo_value}</div>'
        '</div>'
    )


def publication_panel(slug, framework_hint=''):
    rows=_rows(slug)
    context=_project_context(slug,framework_hint)
    information=_project_information(context)
    try:
        from cloudif_portal_publications import latest_job
        job=latest_job(slug)
    except Exception:
        job=None
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
    try:
        alias_row=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone()
        alias=str(alias_row['alias']) if alias_row else ''
    except Exception:
        alias=''
    finally:
        con.close()

    job_html=''
    if job:
        states={'queued':'Na fila','running':'Publicando','succeeded':'Concluída','failed':'Falhou'}
        status=states.get(job.get('status'),job.get('status') or '')
        progress_values={'queued':1,'preparing':2,'deploying':3,'https':4,'promoting':5,'validating':5,'completed':6}
        progress_value=progress_values.get(job.get('step'),0)
        acknowledge=''
        if job.get('status') in ('succeeded','failed'):
            acknowledge=(
                '<form method="post" action="/cloudiff/portal/action/publication">'
                f'<input type="hidden" name="slug" value="{h(slug)}">'
                f'<input type="hidden" name="job_id" value="{int(job.get("id") or 0)}">'
                '<button class="btn light" name="op" value="acknowledge_job">OK</button></form>'
            )
        job_html=(f'<div class="publication-job is-{h(job.get("status"))}" data-publication-job="{int(job.get("id") or 0)}">'
                  f'<div class="publication-job-copy"><div><strong>{h(status)}</strong><span>{h(job.get("message") or "")}</span></div>{acknowledge}</div>'
                  f'<progress max="6" value="{progress_value}"></progress></div>')

    if alias:
        alias_host=alias+'.cloudiff.duckdns.org'
        alias_html=(
            '<div class="publication-alias is-saved">'
            '<div class="publication-alias-view"><div><span>Endereço ativo</span>'
            f'<a href="https://{h(alias_host)}/" target="_blank" rel="noopener">{h(alias_host)}</a></div>'
            '<button class="btn light" type="button" data-alias-edit>Editar endereço</button></div>'
            '<form class="publication-alias-form" hidden method="post" action="/cloudiff/portal/action/publication">'
            f'<input type="hidden" name="slug" value="{h(slug)}">'
            f'<label><span>Novo endereço</span><div><input name="alias" value="{h(alias)}" pattern="[a-z0-9][a-z0-9-]{{0,62}}"><span>.cloudiff.duckdns.org</span></div></label>'
            '<div class="publication-alias-actions"><button class="btn" name="op" value="set_alias">Salvar</button><button class="btn light" type="button" data-alias-cancel>Cancelar</button></div>'
            '</form></div>'
        )
    else:
        alias_html=(
            '<div class="publication-alias"><div><strong>Endereço amigável</strong><p>Escolha um nome curto para o endereço ativo do site.</p></div>'
            '<form method="post" action="/cloudiff/portal/action/publication">'
            f'<input type="hidden" name="slug" value="{h(slug)}">'
            '<label><span>Nome</span><div><input name="alias" placeholder="ex.: lima" pattern="[a-z0-9][a-z0-9-]{0,62}"><span>.cloudiff.duckdns.org</span></div></label>'
            '<button class="btn" name="op" value="set_alias">Salvar endereço</button></form></div>'
        )

    if not rows:
        return (
            '<div class="cm-resource publication-manager-resource">'+information+job_html+alias_html+
            '<div class="publication-active-card"><div><span>Estado</span><strong>Ainda não publicado</strong></div></div>'
            '<div class="cm-actions"><form method="post" action="/cloudiff/portal/action/publication">'
            f'<input type="hidden" name="slug" value="{h(slug)}">'
            '<button class="btn" name="op" value="publish_version">Publicar site</button></form></div></div>'
        )

    active=next((x for x in rows if int(x.get('is_active') or 0)==1),rows[0])
    active_dep=int(active.get('deploy_number') or 0)
    numeric_host=active.get('stable_hostname') or f"{int(active.get('public_number') or 0)}.cloudiff.duckdns.org"
    active_host=(alias+'.cloudiff.duckdns.org') if alias else numeric_host
    trs=[]
    for r in rows:
        dep=int(r.get('deploy_number') or 0)
        if int(r.get('is_active') or 0)==1:
            action='<span class="pill ok">Ativa</span>'
        else:
            action=(
                '<form method="post" action="/cloudiff/portal/action/publication" style="display:inline">'
                f'<input type="hidden" name="slug" value="{h(slug)}">'
                f'<input type="hidden" name="deploy_number" value="{dep}">'
                '<button class="btn light" name="op" value="activate_version">Ativar esta versão</button></form>'
            )
        trs.append(
            f'<tr><td>d{dep}</td><td><code>{h((r.get("commit_sha") or "")[:12])}</code></td>'
            f'<td><a href="https://{h(r.get("version_hostname") or "")}/" target="_blank" rel="noopener">Abrir</a></td><td>{action}</td></tr>'
        )
    return (
        '<div class="cm-resource publication-manager-resource">'+information+job_html+alias_html+
        '<div class="publication-active-card"><div><span>Site publicado</span>'
        f'<a href="https://{h(active_host)}/" target="_blank" rel="noopener">{h(active_host)}</a></div><span class="pill ok">d{active_dep} ativa</span></div>'
        '<div class="cm-actions">'
        f'<a class="btn light" href="https://{h(active_host)}/" target="_blank" rel="noopener">Abrir site</a>'
        '<form method="post" action="/cloudiff/portal/action/publication">'
        f'<input type="hidden" name="slug" value="{h(slug)}">'
        '<button class="btn" name="op" value="publish_version">Publicar nova versão</button></form></div>'
        '<div class="publication-versions"><div class="cm-resource-title"><strong>Versões publicadas</strong></div>'
        '<div style="overflow:auto"><table><tr><th>Versão</th><th>Commit</th><th>URL</th><th>Ação</th></tr>'
        + ''.join(trs) + '</table></div></div></div>'
    )


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
