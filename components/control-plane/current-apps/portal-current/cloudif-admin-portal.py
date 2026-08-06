#!/usr/bin/env python3
"""CloudIFF portal launcher with canonical authorization and UI normalization."""
from pathlib import Path
import re

_POLICY_OLD = "return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins'}))"
_POLICY_NEW = "return bool(groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))"
_MESSAGE_REPLACEMENTS = (
    ('Área restrita à administração global.', 'Área restrita a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
    ('Acesso restrito à administração global.', 'Acesso restrito a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
)

_ADMIN_LOOKUP_BOX = '''  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Use a aba Administração para pesquisar usuários/grupos reais no AD antes de vincular.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
'''

_TENANT_DETAILS_OLD = '''  <details class="db96-details"><summary>Serviços detectados e permissões</summary><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div><div class="action-group"><button class="btn light" type="button" onclick="toggle__Panel('{acl_id}')">Permissões do banco</button><div id="{acl_id}" class="wizard-panel">{tenant_acl_html(tenant, user)}</div></div></details>
'''.replace('toggle__Panel', 'togglePanel')

_TENANT_DETAILS_NEW = '''  <div class="db96-compact-tools">
    <details class="db96-compact db96-services">
      <summary><span><b>Serviços detectados</b><small>Containers que compõem este banco</small></span><span class="db96-summary-count">{len(chips)} serviços</span></summary>
      <div class="db96-service-list">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div>
    </details>
    <details class="db96-compact db96-permissions" data-tenant-permissions="{h(tenant)}">
      <summary><span><b>Permissões do banco</b><small>Adicionar ou retirar usuários e grupos</small></span><span class="db96-summary-action">Gerenciar</span></summary>
      <div class="db96-permissions-content">{tenant_acl_html(tenant, user)}</div>
    </details>
  </div>
'''


def _replace_all(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f'Contrato visual não encontrado: {label}')
    return source.replace(old, new)


def _load_patched_portal():
    candidates = (
        Path(__file__).with_name('cloudif-admin-portal-base.py'),
        Path('/srv/cloudif/portal/cloudif-admin-portal-base.py'),
        Path('/srv/cloudif/current-apps/portal-current/cloudif-admin-portal-base.py'),
    )
    source_path = next((path for path in candidates if path.is_file()), None)
    if source_path is None:
        raise RuntimeError('Arquivo-base do Portal CloudIFF não encontrado.')

    source = source_path.read_text(encoding='utf-8')
    if _POLICY_OLD in source:
        source = source.replace(_POLICY_OLD, _POLICY_NEW, 1)
    elif _POLICY_NEW not in source:
        raise RuntimeError('Contrato de autorização da exclusão divergiu do esperado.')
    for old, new in _MESSAGE_REPLACEMENTS:
        if old in source:
            source = source.replace(old, new)
    source = _replace_all(source, _ADMIN_LOOKUP_BOX, '', 'atalho de administração do AD no banco')
    source, removed_ad_boxes = re.subn(
        r'  <div class="box">\s*<h3>Busca AD</h3>.*?</div>\n?',
        '',
        source,
        flags=re.DOTALL,
    )
    if '<h3>Busca AD</h3>' in source or 'Ir para Administração</a>' in source:
        raise RuntimeError('Atalhos residuais de Administração do AD encontrados no banco.')
    source = _replace_all(source, _TENANT_DETAILS_OLD, _TENANT_DETAILS_NEW, 'serviços e permissões do tenant')
    owner_remove_old = '''        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")
'''
    owner_remove_new = '''        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            if row and row["subject_type"] == "user" and norm(row["subject"]) == norm(row["tenant"]):
                con.close()
                log_action(user["username"], "tenant_acl_remove_owner_blocked", row["tenant"], 1, str(dict(row)), "proprietário imutável")
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">O proprietário do banco não pode ser removido.</p><a class="btn light" href="/?tab=bancos">Voltar</a></div>'), 409)
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")
'''
    source = _replace_all(source, owner_remove_old, owner_remove_new, 'proteção do proprietário do tenant')
    return source, source_path


_source, _source_path = _load_patched_portal()
globals()['__file__'] = str(_source_path)
exec(compile(_source, str(_source_path), 'exec'), globals(), globals())


def tenant_acl_html(tenant, user):
    """Renderiza o proprietário natural como vínculo obrigatório e ACLs adicionais removíveis."""
    rows = tenant_acl_rows(tenant)
    owner = (tenant or '').strip()
    extra_rows = [
        row for row in rows
        if not (row['subject_type'] == 'user' and norm(row['subject']) == norm(owner))
    ]
    owner_row = (
        f'<tr class="tenant-owner-row"><td>Proprietário</td><td><strong>{h(owner)}</strong>'
        '<span class="pill ok tenant-owner-badge">Dono do banco</span></td>'
        '<td><span class="tenant-owner-lock" title="O proprietário não pode ser removido">Protegido</span></td></tr>'
    )
    trs = owner_row
    for row in extra_rows:
        remove = ''
        if user['admin']:
            remove = f'''<form method="post" action="{url('/action/tenant_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(row['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>'''
        kind = 'Usuário' if row['subject_type'] == 'user' else 'Grupo'
        trs += f'<tr><td>{h(kind)}</td><td>{h(row["subject"])}</td><td>{remove}</td></tr>'
    table = f'<table class="tenant-acl-table"><tr><th>Vínculo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>'
    if not user['admin']:
        return table
    return table + f'''<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão ao banco</h3>
    <form method="post" action="{url('/action/tenant_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <label>Tipo</label>
      <select name="subject_type"><option value="user">Usuário</option><option value="group">Grupo</option></select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="Digite para pesquisar no AD">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
</div>'''
