#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'deploy/install_headless_routes.sh').read_text()
proxy=(root/'components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf').read_text()
assert 'ssl_client_certificate /data/nginx/custom/cloudiff-agent-client-ca.pem;' in s
assert 'ssl_verify_client optional;' in s
assert s.count('if ($ssl_client_verify != SUCCESS) { return 403; }')==3
assert 'location ^~ /__cloudiff_agent_updates/' in s
assert 'location = /cloudiff/portal/api/node-recovery-policy' in s
assert 'location ^~ /__cloudif_distribution/' in s
assert 'proxy_pass http://10.62.92.7:8099;' in s
assert 'proxy_pass http://10.62.91.3:18240/;' in s
assert 'proxy_pass http://127.0.0.1:18250/;' in s
for ip in ('10.62.91.2','10.62.91.5','10.62.92.7'):
    assert f'allow {ip};' not in s
router=s[s.index('router_block(){'):s.index('agent_block(){')]
assert 'allow 10.62.91.3;' in router
assert 'npm-rollback)' in s and 'router-rollback)' in s
assert 'headless-routes-v51' in s
assert 'CLIENT_CA_SOURCE' in s and 'CLIENT_CA_DEST' in s
assert proxy.count('if ($ssl_client_verify != SUCCESS) { return 403; }')==3
assert 'allow 10.62.91.2;' not in proxy and 'allow 10.62.92.7;' not in proxy
print('HEADLESS_ROUTES_MTLS=PASS')
