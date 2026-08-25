#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'deploy/install_webdev_route.sh').read_text()
for needle in ('/__cloudiff_webdev/','cloudiff.duckdns.org','allow 10.0.0.0/16','deny all','proxy_pass http://10.62.91.2:17900/','Upgrade $http_upgrade','Connection "upgrade"','nginx -t','WEBDEV_ROUTE_ROLLBACK=PASS'):
 assert needle in s,needle
for banned in ('auth_request','opencode','open-code','/var/run/docker.sock','privileged: true'):
 assert banned.lower() not in s.lower(),banned
assert 'allow 0.0.0.0/0' not in s
print('WEBDEV_ROUTE_OFFLINE=PASS vpn_only=true websocket=true rollback=true')
