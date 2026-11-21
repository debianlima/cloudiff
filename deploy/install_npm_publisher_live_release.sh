#!/usr/bin/env bash
set -euo pipefail

usage(){ echo "usage: $0 --release-dir DIR --release-id ID [--smoke-url URL]" >&2; exit 64; }
INPUT=''; RELEASE_ID=''; SMOKE_URL=''
while (($#)); do
  case "$1" in
    --release-dir) INPUT=${2:-}; shift 2;;
    --release-id) RELEASE_ID=${2:-}; shift 2;;
    --smoke-url) SMOKE_URL=${2:-}; shift 2;;
    *) usage;;
  esac
done
[[ $EUID -eq 0 ]] || { echo 'root required' >&2; exit 77; }
[[ -d "$INPUT" && "$RELEASE_ID" =~ ^[A-Za-z0-9._-]+$ ]] || usage
for cmd in python3 sha256sum readelf curl systemctl docker install ln cp; do command -v "$cmd" >/dev/null; done

INPUT=$(readlink -f "$INPUT")
MANIFEST="$INPUT/release-manifest.json"
BINARY="$INPUT/bin/cloudiff-agent"
[[ -r "$MANIFEST" && -x "$BINARY" ]] || { echo 'release input incomplete' >&2; exit 65; }
read -r SOURCE_COMMIT SOURCE_TREE EXPECTED_SHA BUILD_ID < <(python3 - "$MANIFEST" <<'PY'
import json,sys,re
x=json.load(open(sys.argv[1]))
vals=[x.get('source_commit',''),x.get('source_tree',''),x.get('binary_sha256',''),x.get('gnu_build_id','')]
assert re.fullmatch(r'[a-f0-9]{40}',vals[0]);assert re.fullmatch(r'[a-f0-9]{40}',vals[1]);assert re.fullmatch(r'[a-f0-9]{64}',vals[2]);assert re.fullmatch(r'[a-f0-9]+',vals[3]);assert x.get('tests',{}).get('npm_publisher_provider')=='PASS'
print(*vals)
PY
)
ACTUAL_SHA=$(sha256sum "$BINARY" | awk '{print $1}')
ACTUAL_BUILD_ID=$(readelf -n "$BINARY" 2>/dev/null | awk '/Build ID:/{print $3;exit}')
[[ "$ACTUAL_SHA" == "$EXPECTED_SHA" && "$ACTUAL_BUILD_ID" == "$BUILD_ID" ]] || { echo 'binary provenance mismatch' >&2; exit 65; }

ROOT=/opt/cloudiff-v2
DEST="$ROOT/releases/$RELEASE_ID"
LIVE_LINK="$ROOT/publisher-live-current"
PREVIOUS_LINK="$ROOT/publisher-live-previous"
CANARY_LINK="$ROOT/publisher-canary-current"
[[ ! -e "$DEST" ]] || { echo 'release id already exists' >&2; exit 65; }
OLD_LIVE=$(readlink -f "$LIVE_LINK")
[[ -x "$OLD_LIVE/bin/cloudiff-agent" ]] || { echo 'current live release invalid' >&2; exit 65; }
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/srv/cloudif/backups/npm-publisher-release-$STAMP"
install -d -m 0700 "$BACKUP"

# Load envs privately; never print token values.
set -a
. /etc/cloudiff-v2/publisher-live.env
LIVE_BIND=$CLOUDIFF_PUBLISHER_BIND; LIVE_PORT=$CLOUDIFF_PUBLISHER_PORT; LIVE_TOKEN=$CLOUDIFF_PUBLISHER_TOKEN; LIVE_STATE=$CLOUDIFF_PUBLISHER_STATE; LIVE_CONF=$CLOUDIFF_PUBLISHER_NGINX_CONF
set +a
unset CLOUDIFF_PUBLISHER_TOKEN
cp -a "$LIVE_STATE" "$BACKUP/state.before.json"
cp -a "$LIVE_CONF" "$BACKUP/http.conf.before"
printf '%s\n' "$OLD_LIVE" > "$BACKUP/live-target.before"
chmod 0600 "$BACKUP"/*

install -d -m 0755 "$DEST/bin"
install -m 0755 "$BINARY" "$DEST/bin/cloudiff-agent"
install -m 0644 "$MANIFEST" "$DEST/release-manifest.json"
cp -a "$INPUT/SHA256SUMS" "$DEST/SHA256SUMS"
printf '%s\n' "$SOURCE_COMMIT" > "$DEST/SOURCE_SHA"
cat > "$DEST/DEPLOYMENT-METADATA" <<META
release_id=$RELEASE_ID
source_commit=$SOURCE_COMMIT
source_tree=$SOURCE_TREE
binary_sha256=$EXPECTED_SHA
gnu_build_id=$BUILD_ID
purpose=publisher_stage_delete_automatic_homologation_cleanup
build_profile=Release-clang
META
chmod 0644 "$DEST/SOURCE_SHA" "$DEST/DEPLOYMENT-METADATA" "$DEST/SHA256SUMS"

rollback(){
  set +e
  systemctl stop cloudiff-v2-npm-publisher-canary.service >/dev/null 2>&1
  ln -sfn "$OLD_LIVE" "$LIVE_LINK"
  cp -a "$BACKUP/state.before.json" "$LIVE_STATE"
  cp -a "$BACKUP/http.conf.before" "$LIVE_CONF"
  systemctl restart cloudiff-v2-npm-publisher-live.service
  docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null 2>&1 && docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null 2>&1
}
trap 'rc=$?; if ((rc!=0)); then rollback; fi; exit $rc' EXIT

# Canary uses its own env/port but same managed state/config. Test a guaranteed-absent stage delete and require zero semantic drift.
ln -sfn "$DEST" "$CANARY_LINK"
set -a
. /etc/cloudiff-v2/publisher-canary.env
CANARY_BIND=$CLOUDIFF_PUBLISHER_BIND; CANARY_PORT=$CLOUDIFF_PUBLISHER_PORT; CANARY_TOKEN=$CLOUDIFF_PUBLISHER_TOKEN; CANARY_STATE=$CLOUDIFF_PUBLISHER_STATE; CANARY_CONF=$CLOUDIFF_PUBLISHER_NGINX_CONF
set +a
unset CLOUDIFF_PUBLISHER_TOKEN
[[ "$CANARY_STATE" == "$LIVE_STATE" && "$CANARY_CONF" == "$LIVE_CONF" ]] || { echo 'canary/live managed paths mismatch' >&2; exit 65; }
CANARY_HOST=$CANARY_BIND; [[ "$CANARY_HOST" == '0.0.0.0' || "$CANARY_HOST" == '::' ]] && CANARY_HOST=127.0.0.1
BEFORE_STATE=$(python3 - "$LIVE_STATE" <<'PY'
import json,hashlib,sys
x=json.load(open(sys.argv[1]));assert '999999999-h999999-homologation' not in (x.get('stages') or {})
print(hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest())
PY
)
BEFORE_CONF=$(sha256sum "$LIVE_CONF" | awk '{print $1}')
systemctl restart cloudiff-v2-npm-publisher-canary.service
for _ in $(seq 1 20); do curl -fsS --max-time 2 "http://$CANARY_HOST:$CANARY_PORT/health" >/dev/null && break; sleep 0.5; done
printf 'header = "Content-Type: application/json"\nheader = "X-CloudIF-Token: %s"\ndata = "{\"public_number\":999999999,\"stage\":\"homologation\",\"number\":999999}"\n' "$CANARY_TOKEN" | curl -fsS --max-time 10 --config - "http://$CANARY_HOST:$CANARY_PORT/stage/delete" > "$BACKUP/canary-delete-response.json"
python3 - "$BACKUP/canary-delete-response.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));assert x.get('ok') is True and x.get('removed') is False
PY
AFTER_STATE=$(python3 - "$LIVE_STATE" <<'PY'
import json,hashlib,sys
x=json.load(open(sys.argv[1]));print(hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest())
PY
)
AFTER_CONF=$(sha256sum "$LIVE_CONF" | awk '{print $1}')
[[ "$BEFORE_STATE" == "$AFTER_STATE" && "$BEFORE_CONF" == "$AFTER_CONF" ]] || { echo 'canary stage-delete caused drift' >&2; exit 70; }
docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null
systemctl stop cloudiff-v2-npm-publisher-canary.service

ln -sfn "$OLD_LIVE" "$PREVIOUS_LINK"
ln -sfn "$DEST" "$LIVE_LINK"
systemctl restart cloudiff-v2-npm-publisher-live.service
LIVE_HOST=$LIVE_BIND; [[ "$LIVE_HOST" == '0.0.0.0' || "$LIVE_HOST" == '::' ]] && LIVE_HOST=127.0.0.1
for _ in $(seq 1 20); do curl -fsS --max-time 2 "http://$LIVE_HOST:$LIVE_PORT/health" >/dev/null && break; sleep 0.5; done
curl -fsS --max-time 4 "http://$LIVE_HOST:$LIVE_PORT/health" >/dev/null
# Prove the new endpoint on live with an idempotent no-op.
printf 'header = "Content-Type: application/json"\nheader = "X-CloudIF-Token: %s"\ndata = "{\"public_number\":999999999,\"stage\":\"homologation\",\"number\":999999}"\n' "$LIVE_TOKEN" | curl -fsS --max-time 10 --config - "http://$LIVE_HOST:$LIVE_PORT/stage/delete" > "$BACKUP/live-delete-response.json"
python3 - "$BACKUP/live-delete-response.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));assert x.get('ok') is True and x.get('removed') is False
PY
docker exec cloudif-nginx-proxy-manager nginx -t >/dev/null
docker exec cloudif-nginx-proxy-manager nginx -s reload >/dev/null
if [[ -n "$SMOKE_URL" ]]; then curl -fsS --max-time 15 "$SMOKE_URL" >/dev/null; fi
trap - EXIT
printf 'install_ok=true\nrelease_id=%s\nsource_commit=%s\nbinary_sha256=%s\nbackup=%s\n' "$RELEASE_ID" "$SOURCE_COMMIT" "$EXPECTED_SHA" "$BACKUP"
