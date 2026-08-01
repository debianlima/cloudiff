#!/usr/bin/env python3
import html
import sqlite3

DB='/var/lib/cloudif/portal/cloudif-portal.db'

def h(value):
    return html.escape(str(value if value is not None else ''), quote=True)

def _rows(slug):
    try:
        con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
        rows=[dict(x) for x in con.execute('select * from project_publications where project_slug=? order by deploy_number desc',(slug,))]
        con.close(); return rows
    except Exception:
        return []

def publication_panel(slug):
    rows=_rows(slug)
    if not rows:
        return (
            '<div class="cm-resource">'
            '<div class="cm-resource-title"><strong>Publicação</strong><span class="pill">Ainda não publicada</span></div>'
            '<div class="cm-actions">'
            '<form method="post" action="/cloudiff/portal/action/publication">'
            f'<input type="hidden" name="slug" value="{h(slug)}">'
            '<button class="btn" name="op" value="publish_version">Publicar site</button>'
            '</form></div></div>'
        )
    active=next((x for x in rows if int(x.get('is_active') or 0)==1),rows[0])
    num=int(active.get('public_number') or 0)
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
                '<button class="btn light" name="op" value="activate_version">Ativar esta versão</button>'
                '</form>'
            )
        trs.append(
            f'<tr><td>d{dep}</td><td><code>{h((r.get("commit_sha") or "")[:12])}</code></td>'
            f'<td><a href="https://{h(r.get("version_hostname") or "")}/" target="_blank">Abrir</a></td><td>{action}</td></tr>'
        )
    return (
        '<div class="cm-resource">'
        f'<div class="cm-resource-title"><strong>Publicações</strong><span class="pill ok">d{int(active.get("deploy_number") or 0)} ativa</span></div>'
        '<div class="cm-actions">'
        f'<a class="btn light" href="https://{num}.cloudiff.duckdns.org/" target="_blank">Abrir site</a>'
        '<form method="post" action="/cloudiff/portal/action/publication">'
        f'<input type="hidden" name="slug" value="{h(slug)}">'
        '<button class="btn" name="op" value="publish_version">Publicar nova versão</button>'
        '</form></div><div style="overflow:auto">'
        '<table><tr><th>Versão</th><th>Commit</th><th>URL</th><th>Ação</th></tr>'
        + ''.join(trs) + '</table></div></div>'
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
