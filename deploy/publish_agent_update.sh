#!/usr/bin/env bash
set -euo pipefail
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CFG="$ROOT/config/agent-update.json"
REPO=/var/lib/cloudiff-agent/repository
KEY=/etc/cloudiff-v2/agent-update-signing.key.pem
PUB=/etc/cloudiff-v2/agent-update-signing.pub.pem
BIN=${1:-/var/lib/cloudiff-v2/build-v32-debug/cloudiff-agent}
VERSION=${2:-}
[ -x "$BIN" ]
if [ -z "$VERSION" ];then VERSION=$($BIN --version | sed -n 's/.* \([0-9][0-9.]*\)-shadow$/\1/p');fi
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
install -d -m 0751 /etc/cloudiff-v2
install -d -m 0755 "$REPO/releases/$VERSION" "$REPO/stable"
if [ ! -s "$KEY" ];then umask 077;openssl genpkey -algorithm ED25519 -out "$KEY";fi
chmod 0600 "$KEY";chown root:root "$KEY"
openssl pkey -in "$KEY" -pubout -out "$PUB" >/dev/null 2>&1
chmod 0644 "$PUB";chown root:root "$PUB"
install -m 0755 "$BIN" "$REPO/releases/$VERSION/cloudiff-agent"
sha=$(sha256sum "$REPO/releases/$VERSION/cloudiff-agent"|awk '{print $1}')
size=$(stat -c %s "$REPO/releases/$VERSION/cloudiff-agent")
tmp=$(mktemp -d);trap 'rm -rf "$tmp"' EXIT
python3 - "$VERSION" "$sha" "$size" > "$tmp/manifest.json" <<'PY'
import json,sys,datetime
v,sha,size=sys.argv[1:]
print(json.dumps({"version":v,"artifact":f"releases/{v}/cloudiff-agent","sha256":sha,"size":int(size),"published_at":datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),"restart_service":"cloudiff-v2-agent.service"},sort_keys=True,separators=(',',':')))
PY
openssl pkeyutl -sign -rawin -inkey "$KEY" -in "$tmp/manifest.json" -out "$tmp/manifest.sig"
install -m 0644 "$tmp/manifest.json" "$REPO/stable/manifest.json.new"
install -m 0644 "$tmp/manifest.sig" "$REPO/stable/manifest.sig.new"
mv -f "$REPO/stable/manifest.json.new" "$REPO/stable/manifest.json"
mv -f "$REPO/stable/manifest.sig.new" "$REPO/stable/manifest.sig"
chown -R root:root "$REPO";find "$REPO" -type d -exec chmod 0755 {} +;find "$REPO" -type f -exec chmod 0644 {} +;chmod 0755 "$REPO/releases/$VERSION/cloudiff-agent"
echo AGENT_UPDATE_PUBLISH=PASS
