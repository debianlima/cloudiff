#!/usr/bin/env python3
from pathlib import Path
import ast,subprocess,tempfile,shutil,hashlib
root=Path(__file__).resolve().parents[1]
patch=root/'compat/portal-admin-observability.patch'
assert patch.is_file() and patch.stat().st_size>0
repo_baseline=root/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py'
state=Path('/var/lib/cloudiff-v2/portal-admin-observability/previous')
if repo_baseline.is_file():
    baseline=repo_baseline
elif state.is_file() and state.read_text().strip():
    baseline=Path(state.read_text().strip())/'cloudif-admin-portal.py'
else:
    raise AssertionError('baseline do Portal anterior ao AdminObservability não disponível')
assert baseline.is_file(),baseline
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'cloudif-admin-portal.py'
    shutil.copy2(baseline,p)
    subprocess.run(['patch','-s','-d',td,'-p0'],input=patch.read_bytes(),check=True)
    subprocess.run(['python3','-m','py_compile',str(p)],check=True)
    tree=ast.parse(p.read_text());inject=None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_ADMIN_OBSERVABILITY_INJECT' for t in node.targets):
            inject=ast.literal_eval(node.value)
    assert isinstance(inject,str) and inject
    for needle in ("path=='/admin'","/cloudiff/portal/api/admin-observability","/cloudiff/portal/action/node-recovery","/cloudiff/portal/api/node-recovery-policy","cloudif-tenants-admin","_prod_csrf_equal","http://127.0.0.1:18260"):
        assert needle in inject,needle
    live=Path('/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py')
    if live.is_file() and '_ADMIN_OBSERVABILITY_INJECT' in live.read_text():
        assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(live.read_bytes()).hexdigest()
text=patch.read_text()
assert 'tabs.insert' not in text
assert 'cloudif-admin-portal-base.py' not in text
assert '-----BEGIN' not in text
print('PORTAL_ADMIN_OBSERVABILITY_OFFLINE=PASS')
