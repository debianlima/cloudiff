#!/usr/bin/env python3
"""CloudIFF portal launcher with canonical authorization and UI normalization."""
from pathlib import Path

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

_TENANT_DETAILS_OLD = '''  <details class="db96-details"><summary>Serviços detectados e permissões</summary><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div><div class="action-group"><button class="btn light" type="button" onclick="togglePanel('{acl_id}')">Permissões do banco</button><div id="{acl_id}" class="wizard-panel">{tenant_acl_html(tenant, user)}</div></div></details>
'''

_TENANT_DETAILS_NEW = '''  <section class="db96-section db96-services"><div class="db96-section-title"><div><span>3</span><h3>Serviços detectados</h3></div><p>Recursos ativos vinculados ao tenant.</p></div><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div></section>
  <section class="db96-section db96-permissions"><div class="db96-section-title"><div><span>4</span><h3>Permissões do banco</h3></div><p>Usuários e grupos autorizados neste tenant.</p></div><div class="action-group db96-permissions-content">{tenant_acl_html(tenant, user)}</div></section>
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
    if source.count(_POLICY_OLD) != 1:
        raise RuntimeError('Contrato de autorização da exclusão divergiu do esperado.')
    source = source.replace(_POLICY_OLD, _POLICY_NEW, 1)
    for old, new in _MESSAGE_REPLACEMENTS:
        source = _replace_all(source, old, new, old)
    source = _replace_all(source, _ADMIN_LOOKUP_BOX, '', 'atalho de administração do AD no banco')
    source = _replace_all(source, _TENANT_DETAILS_OLD, _TENANT_DETAILS_NEW, 'serviços e permissões do tenant')
    return source, source_path


_source, _source_path = _load_patched_portal()
globals()['__file__'] = str(_source_path)
exec(compile(_source, str(_source_path), 'exec'), globals(), globals())
