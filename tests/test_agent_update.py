#!/usr/bin/env python3
from pathlib import Path
import json,re,tempfile,subprocess,os,hashlib
root=Path(__file__).resolve().parents[1]
s=json.load(open(root/'contratos/agent-update.schema.json'));cfg=json.load(open(root/'config/agent-update.json'))
import jsonschema;jsonschema.Draft202012Validator.check_schema(s);jsonschema.validate(cfg,s)
assert cfg['layout']['root']=='/opt/cloudiff-agent';assert cfg['polling']=={'interval_seconds':300,'random_delay_seconds':60};assert cfg['repository']['url']=='https://cloudiff.duckdns.org/__cloudiff_agent_updates';assert cfg['repository']['bind']=='127.0.0.1'
assert cfg['recovery']['reboot_default'] is True and cfg['recovery']['admin_can_disable_reboot'] is True
pub=(root/'deploy/publish_agent_update.sh').read_text();upd=(root/'deploy/agent_updater.sh').read_text();repo=(root/'deploy/systemd/cloudiff-v2-agent-update-repository.service').read_text();ng=(root/'config/nginx/agent-updates.conf').read_text()
assert cfg['policy']['url_template']=='https://cloudiff.duckdns.org/cloudiff/portal/api/node-recovery-policy?node_id={node_id}'
assert 'refresh_policy' in upd and 'reboot_enabled' in upd and 'maybe_reboot' in upd and 'CLOUDIFF_AGENT_UPDATE_TEST_MODE' in upd
assert 'AGENT_RECOVERY_REBOOT=DISABLED' in upd and 'AGENT_RECOVERY_REBOOT=COOLDOWN' in upd
assert 'openssl genpkey -algorithm ED25519' in pub and 'openssl pkeyutl -sign -rawin' in pub
assert 'install -d -m 0751 /etc/cloudiff-v2' in pub
assert 'chmod 0600 "$KEY"' in pub
assert 'openssl pkeyutl -verify -rawin -pubin' in upd and 'sha256sum' in upd and 'mv -Tf "$CURRENT.new" "$CURRENT"' in upd and 'AGENT_UPDATE=ROLLBACK' in upd
assert '--read-only' in repo and '--cap-drop ALL' in repo and '--security-opt no-new-privileges' in repo and '--entrypoint nginx' in repo
assert 'listen 127.0.0.1:18250;' in ng and 'allow 127.0.0.1;' in ng
assert 'deny all;' in ng and 'autoindex off;' in ng and 'client_body_temp_path /tmp/client_temp;' in ng
for p in (root/'config/agent-update.json',root/'config/nginx/agent-updates.conf',root/'deploy/publish_agent_update.sh',root/'deploy/agent_updater.sh'):
 t=p.read_text();assert ('-----BEGIN ' + 'PRIVATE KEY-----') not in t
print('AGENT_UPDATE_OFFLINE=PASS')
