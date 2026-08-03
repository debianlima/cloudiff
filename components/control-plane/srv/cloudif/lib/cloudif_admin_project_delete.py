import glob
import html
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from cloudif_delete_git_komodo_action import forja_rollback

DB = Path('/var/lib/cloudif/portal/cloudif-portal.db')
ONBOARDING_DB = Path('/var/lib/cloudif/onboarding/onboarding.db')
AUDIT_ROOT = Path('/srv/cloudif/admin-project-deletions')
JOBS = Path('/srv/cloudif/jobs')
PROVISIONING = Path('/srv/cloudif/provisioning/projects')


def h(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def _rows(db, table, key, slug):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(f'SELECT * FROM {table} WHERE {key}=?', (slug,))]
    except sqlite3.DatabaseError:
        return []
    finally:
        con.close()


def projects():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(
            "SELECT slug,name,owner,tenant,repo_url,komodo_status,status FROM projects ORDER BY lower(name),slug"
        )]
    finally:
        con.close()


def preview(slug):
    project = _rows(DB, 'projects', 'slug', slug)
    if not project:
        return {'ok': False, 'error': 'project_not_found', 'slug': slug}
    tenant = str(project[0].get('tenant') or '')
    local = {}
    con = sqlite3.connect(DB)
    try:
        for table, in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            cols = {row[1] for row in con.execute(f'PRAGMA table_info({table})')}
            key = next((candidate for candidate in ('slug', 'project_slug', 'project') if candidate in cols), None)
            if not key:
                continue
            count = con.execute(f'SELECT COUNT(*) FROM {table} WHERE {key}=?', (slug,)).fetchone()[0]
            if count:
                local[table] = count
    finally:
        con.close()
    remote = forja_rollback(slug, execute=False)
    return {
        'ok': True,
        'slug': slug,
        'project': project[0],
        'tenant_preserved': tenant,
        'local_rows': local,
        'jobs': sorted(glob.glob(str(JOBS / f'*{slug}*'))),
        'provisioning_path': str(PROVISIONING / slug) if (PROVISIONING / slug).exists() else '',
        'remote_preview': remote,
    }


def _delete_rows(con, slug):
    removed = {}
    tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    # Dependents first; projects last.
    tables = [t for t in tables if t != 'projects'] + (['projects'] if 'projects' in tables else [])
    for table in tables:
        cols = {row[1] for row in con.execute(f'PRAGMA table_info({table})')}
        key = next((candidate for candidate in ('slug', 'project_slug', 'project') if candidate in cols), None)
        if not key:
            continue
        try:
            count = con.execute(f'DELETE FROM {table} WHERE {key}=?', (slug,)).rowcount
            if count:
                removed[table] = count
        except sqlite3.DatabaseError:
            continue
    return removed


def execute(slug, confirmation, actor):
    expected = f'EXCLUIR {slug}'
    if confirmation != expected:
        return {'ok': False, 'error': 'invalid_confirmation', 'expected': expected}
    plan = preview(slug)
    if not plan.get('ok'):
        return plan
    stamp = time.strftime('%Y%m%d-%H%M%S')
    audit = AUDIT_ROOT / f'{stamp}-{slug}'
    audit.mkdir(parents=True, exist_ok=False)
    shutil.copy2(DB, audit / 'cloudif-portal.db')
    if ONBOARDING_DB.exists():
        shutil.copy2(ONBOARDING_DB, audit / 'onboarding.db')
    (audit / 'preview.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')

    remote = forja_rollback(slug, execute=True)
    if not remote.get('ok'):
        result = {'ok': False, 'error': 'remote_delete_failed', 'remote': remote, 'audit_dir': str(audit)}
        (audit / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        return result

    con = sqlite3.connect(DB)
    try:
        con.execute('BEGIN IMMEDIATE')
        removed = _delete_rows(con, slug)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    onboarding_removed = 0
    if ONBOARDING_DB.exists():
        con = sqlite3.connect(ONBOARDING_DB)
        try:
            cols = {row[1] for row in con.execute('PRAGMA table_info(project_onboarding)')}
            if 'project_slug' in cols:
                onboarding_removed = con.execute('DELETE FROM project_onboarding WHERE project_slug=?', (slug,)).rowcount
                con.commit()
        finally:
            con.close()

    removed_paths = []
    for candidate in glob.glob(str(JOBS / f'*{slug}*')):
        try:
            os.remove(candidate)
            removed_paths.append(candidate)
        except FileNotFoundError:
            pass
    provision_dir = PROVISIONING / slug
    if provision_dir.exists():
        shutil.rmtree(provision_dir)
        removed_paths.append(str(provision_dir))

    subprocess.run(['systemctl', 'start', 'cloudif-project-state-reconcile.service'], check=False, timeout=15)
    result = {
        'ok': True,
        'slug': slug,
        'actor': actor,
        'tenant_preserved': plan.get('tenant_preserved') or '',
        'remote': remote,
        'removed_rows': removed,
        'onboarding_removed': onboarding_removed,
        'removed_paths': removed_paths,
        'audit_dir': str(audit),
        'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'secrets_exposed': False,
    }
    (audit / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def render(csrf_token, selected='', result=None):
    rows = projects()
    options = ''.join(
        f'<option value="{h(p["slug"])}"{" selected" if p["slug"] == selected else ""}>{h(p.get("name") or p["slug"])} — {h(p["slug"])}</option>'
        for p in rows
    )
    result_html = ''
    if result is not None:
        cls = 'ok' if result.get('ok') else 'bad'
        title = 'Projeto excluído' if result.get('ok') else 'Exclusão não concluída'
        result_html = (
            f'<section class="card"><span class="pill {cls}">{h(title)}</span>'
            f'<pre style="white-space:pre-wrap;overflow:auto;max-height:420px">{h(json.dumps(result, ensure_ascii=False, indent=2))}</pre></section>'
        )
    selected_preview = preview(selected) if selected else None
    preview_html = ''
    if selected_preview:
        preview_html = f'<pre style="white-space:pre-wrap;overflow:auto;max-height:360px">{h(json.dumps(selected_preview, ensure_ascii=False, indent=2))}</pre>'
    return f'''
<section class="card admin-delete-project">
  <div class="section-title"><div><h1>Excluir projeto</h1><p>Remoção administrativa de Portal, Forgejo, Komodo, onboarding, jobs e artefatos. O tenant/banco é preservado.</p></div><span class="pill bad">Ação irreversível</span></div>
  <form method="get" action="/cloudiff/portal/">
    <input type="hidden" name="tab" value="admin-excluir-projeto">
    <label>Projeto<select name="slug" required><option value="">Selecione</option>{options}</select></label>
    <button class="btn light" type="submit">Gerar prévia</button>
  </form>
  {preview_html}
  {f'''<form method="post" action="/cloudiff/portal/action/admin-delete-project">
    <input type="hidden" name="csrf_token" value="{h(csrf_token)}">
    <input type="hidden" name="slug" value="{h(selected)}">
    <label>Digite exatamente <code>EXCLUIR {h(selected)}</code><input name="confirm_text" required autocomplete="off"></label>
    <button class="btn danger" type="submit">Excluir projeto definitivamente</button>
  </form>''' if selected_preview and selected_preview.get('ok') else ''}
</section>{result_html}
'''
