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
    if source.count(_POLICY_OLD) != 1:
        raise RuntimeError('Contrato de autorização da exclusão divergiu do esperado.')
    source = source.replace(_POLICY_OLD, _POLICY_NEW, 1)
    for old, new in _MESSAGE_REPLACEMENTS:
        source = _replace_all(source, old, new, old)
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
    return source, source_path


_source, _source_path = _load_patched_portal()
globals()['__file__'] = str(_source_path)
exec(compile(_source, str(_source_path), 'exec'), globals(), globals())
