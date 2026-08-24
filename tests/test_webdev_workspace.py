#!/usr/bin/env python3
from pathlib import Path
import json,re,subprocess,urllib.request
import jsonschema
root=Path(__file__).resolve().parents[1]
schema=json.load(open(root/'contratos/webdev-workspace.schema.json'));cfg=json.load(open(root/'config/webdev-workspace.json'))
jsonschema.Draft202012Validator.check_schema(schema);jsonschema.validate(cfg,schema)
compose=(root/'deploy/compose.webdev.yaml').read_text();install=(root/'deploy/install_webdev_workspace.sh').read_text();unit=(root/'deploy/systemd/cloudiff-webdev.service').read_text()
assert cfg['host']['address']=='10.62.91.2';assert cfg['simulation']['physical_ad_host']=='10.68.128.252'
assert '9569014786466376d3e5cf8a7758562368cd9637f783dcd3abdb2eaf3a0d5cd7' in compose
assert '127.0.0.1:14444:4444' in compose and '10.62.91.2:17900:7900' in compose
assert '10.68.128.252' in compose and 'SE_VNC_NO_PASSWORD: "true"' in compose
for banned in ('/var/run/docker.sock','privileged: true','opencode','open-code','OpenCodeWorkspace'):
 assert banned.lower() not in compose.lower(),banned
assert '/srv/cloudif/webdev-workspace:/workspace:ro' in compose
assert '/srv/cloudif/app-' not in compose and '/srv/cloudif-v2' not in compose
assert '10.0.0.0/16' in install and 'CLOUDIFF_WEBDEV' in install and '-j DROP' in install
assert 'restart: "no"' in compose
assert 'ExecStartPre=/var/lib/cloudiff-webdev/current/deploy/install_webdev_workspace.sh firewall-apply' in unit
assert 'ExecStart=/usr/bin/docker compose' in unit and 'ExecStopPost=/var/lib/cloudiff-webdev/current/deploy/install_webdev_workspace.sh firewall-remove' in unit
for banned in ('apt install','apt-get install','opencode','npm install -g','pip install'):
 assert banned.lower() not in install.lower(),banned
if __import__('os').environ.get('CLOUDIFF_WEBDEV_LIVE')=='1':
 data=json.load(urllib.request.urlopen('http://127.0.0.1:14444/status',timeout=5));assert data['value']['ready'] is True
 print('WEBDEV_SELENIUM_STATUS=PASS')
print('WEBDEV_WORKSPACE_OFFLINE=PASS')
