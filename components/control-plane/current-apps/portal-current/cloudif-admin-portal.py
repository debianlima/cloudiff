#!/usr/bin/env python3
"""CloudIFF portal launcher with canonical CloudIF deletion authorization.

The generated base portal is preserved. Only the dedicated project-deletion
guard is replaced so that CloudIF-Tenants-Admin and CloudIF-Professor are the
only accepted groups. CSRF and confirmation protections remain in the base.
"""
from pathlib import Path

_POLICY_OLD = "return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins'}))"
_POLICY_NEW = "return bool(groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))"
_REPLACEMENTS = (
    ('Área restrita à administração global.', 'Área restrita a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
    ('Acesso restrito à administração global.', 'Acesso restrito a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
)


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
    for old, new in _REPLACEMENTS:
        if old not in source:
            raise RuntimeError(f'Mensagem de autorização esperada não encontrada: {old}')
        source = source.replace(old, new, 1)
    return source, source_path


_source, _source_path = _load_patched_portal()
globals()['__file__'] = str(_source_path)
exec(compile(_source, str(_source_path), 'exec'), globals(), globals())
