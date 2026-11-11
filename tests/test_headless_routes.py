#!/usr/bin/env python3
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];s=(root/'deploy/install_agent_update_route.sh').read_text()
assert 'location ^~ /__cloudiff_agent_updates/' in s
assert s.count('location = /cloudiff/portal/api/node-recovery-policy')==2
assert s.count('$arg_node_id !~*')==2
assert 'proxy_pass http://127.0.0.1:18250/;' in s
assert 'proxy_pass http://10.62.92.7:8099;' in s
for ip in ('10.62.91.2','10.62.91.3','10.62.91.5','10.62.92.7'):assert f'allow {ip};' in s
# Router only admits NPM source .3; NPM block carries the four node allow entries.
r=s[s.index('router_block(){'):s.index('npm_block(){')];assert 'allow 10.62.91.3;' in r and 'allow 10.62.91.2;' not in r
assert s.count('limit_except GET HEAD { deny all; }')==4
assert s.count('if ($args != "") { return 400; }')==2
assert 'router-rollback)' in s and 'npm-rollback)' in s
assert 'agent-update-route-v35' in s and 'baseline' in s
print('AGENT_UPDATE_ROUTE_OFFLINE=PASS')
