#!/usr/bin/env python3
"""CloudIFF portal launcher with the professor/admin deletion policy applied.

The preserved base file remains byte-for-byte identical to the generated portal.
Only the dedicated project-deletion guard and its denial messages are changed
before execution. The route keeps its existing CSRF check (`_prod_csrf_equal`)
and endpoint `/cloudiff/portal/action/admin-delete-project`.
"""
from pathlib import Path

_POLICY_OLD = "return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins'}))"
_POLICY_NEW = "return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins','cloudif-professor'}))"
_REPLACEMENTS = (
    ('Área restrita à administração global.', 'Área restrita a professor ou administrador.'),
    ('Acesso restrito à administração global.', 'Acesso restrito a professor ou administrador.'),
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
