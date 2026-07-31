#!/bin/bash
set -euo pipefail
. /etc/cloudif/komodo-publication-client.env
curl -sS --max-time 420 \
  -H "X-CloudIF-Token: $KOMODO_PUBLICATION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"project":"primeiros-passos-cloudif-iff1860746","public_number":1006,"deploy_number":2,"timeout":300}' \
  "$KOMODO_PUBLICATION_URL/komodo/publication/deploy" \
  -o /var/lib/cloudif/portal/d2-deploy-result.json
python3 - <<'PY'
import json
p='/var/lib/cloudif/portal/d2-deploy-result.json'
x=json.load(open(p)); assert x.get('ok') is True, x
print({'ok':True,'stack':x.get('stack_name'),'container':x.get('container'),'commit':x.get('commit')})
PY
