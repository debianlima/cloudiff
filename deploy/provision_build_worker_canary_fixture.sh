#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-status}
ROOT=${CLOUDIFF_V2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CFG="$ROOT/config/build-worker-canary-fixture.json"
PATCH_FILE="$ROOT/compat/forja-agent-system-fixture.patch"
TEST_FILE="$ROOT/tests/test_forja_agent_system_fixture.py"
SERVICE=cloudif-forja-agent.service
POINTER=/srv/cloudif/app-pointers/forja-agent-current
STATE=/var/lib/cloudiff-v2/build-worker-canary-fixture
BASE_SHA=d0329556d5c83665a455a0c6f82321b6e4dcd6a11bc1081a8bb652c54223ad74
PATCHED_SHA=67c1b4ba2673333775957bad68796241f19debe9be858f5a7fa9ed991a086194
install -d -m 0700 "$STATE"
[ -s "$CFG" ] && [ -s "$PATCH_FILE" ] && [ -x "$TEST_FILE" ]
set -a; . /etc/cloudif/forja-agent.env; set +a
: "${FORGEJO_URL:?}" "${FORGEJO_TOKEN:?}" "${FORGEJO_OWNER:?}" "${FORJA_AGENT_TOKEN:?}"
PORT=${FORJA_AGENT_PORT:-18095}
SMOKE_HOST=${FORJA_AGENT_HOST:-127.0.0.1}
[ "$SMOKE_HOST" != "0.0.0.0" ] || SMOKE_HOST=127.0.0.1

verify_sources(){
  python3 - "$ROOT" "$CFG" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);x=json.load(open(sys.argv[2]))
assert x['identity']=={'canonicalName':'BuildWorkerCanaryFixture','slug':'system-build-canary','systemOwned':True,'containsUserData':False}
for f in x['files']:
 p=root/f['source'];assert p.is_file();assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
print('FIXTURE_SOURCE_DIGESTS=PASS')
PY
}

provision_repo(){
  python3 - "$ROOT" "$CFG" <<'PY'
import base64,json,os,sys,urllib.error,urllib.parse,urllib.request
from pathlib import Path
root=Path(sys.argv[1]);cfg=json.load(open(sys.argv[2])); owner=os.environ['FORGEJO_OWNER'];token=os.environ['FORGEJO_TOKEN'];base=os.environ['FORGEJO_URL'].rstrip('/')+'/api/v1';repo=cfg['forgejo']['repository'];branch=cfg['forgejo']['branch']
headers={'Authorization':'token '+token,'Accept':'application/json','User-Agent':'CloudIFF-BuildWorkerCanaryFixture/1'}
def call(method,path,payload=None):
 data=None;h=dict(headers)
 if payload is not None:data=json.dumps(payload,separators=(',',':')).encode();h['Content-Type']='application/json'
 r=urllib.request.Request(base+path,data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(r,timeout=15) as x:
   raw=x.read();return x.status,(json.loads(raw.decode()) if raw else {})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:body=json.loads(raw.decode() or '{}')
  except Exception:body={}
  return e.code,body
q=lambda v:urllib.parse.quote(str(v),safe='')
status,data=call('GET',f'/repos/{q(owner)}/{q(repo)}');created=False
if status==404:
 status,data=call('POST',f'/admin/users/{q(owner)}/repos',{'name':repo,'private':True,'auto_init':True,'default_branch':branch,'description':'CloudIFF system-owned ClassicBuildWorker E2E fixture'})
 assert status in (201,202), (status,data);created=True
 status,data=call('GET',f'/repos/{q(owner)}/{q(repo)}')
assert status==200 and data.get('private') is True and data.get('name')==repo

def content(path):return call('GET',f'/repos/{q(owner)}/{q(repo)}/contents/{urllib.parse.quote(path,safe="/")}?ref={q(branch)}')
def ensure(path,raw):
 status,cur=content(path); payload={'content':base64.b64encode(raw).decode(),'message':'CloudIFF system canary fixture: '+path,'branch':branch}
 if status==200:
  existing=base64.b64decode((cur.get('content') or '').encode()) if cur.get('content') else b''
  if existing==raw:return
  payload['sha']=cur['sha'];status,_=call('PUT',f'/repos/{q(owner)}/{q(repo)}/contents/{urllib.parse.quote(path,safe="/")}',payload);assert status in (200,201)
 elif status==404:
  status,_=call('POST',f'/repos/{q(owner)}/{q(repo)}/contents/{urllib.parse.quote(path,safe="/")}',payload);assert status in (200,201)
 else:raise AssertionError((path,status,cur))
for f in cfg['files']:ensure(f['path'],(root/f['source']).read_bytes())
# auto_init may create README; remove only that known bootstrap file.
status,readme=content('README.md')
if status==200:
 status,_=call('DELETE',f'/repos/{q(owner)}/{q(repo)}/contents/README.md',{'sha':readme['sha'],'message':'Remove bootstrap README from system canary fixture','branch':branch});assert status in (200,204)
status,root_items=call('GET',f'/repos/{q(owner)}/{q(repo)}/contents?ref={q(branch)}');assert status==200
assert sorted(x.get('name') for x in root_items)==['compose.yml','site']
status,site_items=call('GET',f'/repos/{q(owner)}/{q(repo)}/contents/site?ref={q(branch)}');assert status==200
assert [x.get('name') for x in site_items]==['index.html']
status,hooks=call('GET',f'/repos/{q(owner)}/{q(repo)}/hooks');assert status==200 and hooks==[]
print('REPO_CREATED='+('yes' if created else 'no'));print('REPO_PRIVATE=PASS');print('REPO_FILES=EXACT');print('REPO_WEBHOOKS=0')
PY
}

write_registry(){
  local dir file tmp
  dir=$(python3 -c 'import json;print(json.load(open("'"$CFG"'"))["registry"]["directory"])')
  file=$(python3 -c 'import json;print(json.load(open("'"$CFG"'"))["registry"]["file"])')
  install -d -m 0750 "$dir"
  tmp=$(mktemp "$dir/.fixture.XXXXXX")
  python3 - "$CFG" "$FORGEJO_OWNER" > "$tmp" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));print(json.dumps({'system_fixture':True,'project_slug':x['identity']['slug'],'system_owned':True,'forgejo':{'owner':sys.argv[2],'repo':x['forgejo']['repository']},'branch':x['forgejo']['branch']},separators=(',',':'),sort_keys=True))
PY
  chmod 0640 "$tmp"; chown root:root "$tmp"; mv -f "$tmp" "$dir/$file"
  [ ! -e "/var/lib/cloudif/forja-agent/projects/system-build-canary.json" ]
  echo SYSTEM_FIXTURE_REGISTRY=PASS
}

agent_smoke(){
  local ready=0
  for _ in $(seq 1 60); do if curl -fsS --max-time 2 "http://${SMOKE_HOST}:${PORT}/health" >/dev/null 2>&1; then ready=1;break;fi;sleep .25;done
  [ "$ready" = 1 ]
  python3 - "$ROOT" "$CFG" "$SMOKE_HOST" <<'PY'
import hashlib,io,json,os,tarfile,urllib.error,urllib.parse,urllib.request,sys
from pathlib import Path
root=Path(sys.argv[1]);cfg=json.load(open(sys.argv[2]));host=sys.argv[3];port=os.environ.get('FORJA_AGENT_PORT','18095');token=os.environ['FORJA_AGENT_TOKEN'];slug=cfg['identity']['slug']
def get(path,binary=False):
 r=urllib.request.Request('http://'+host+':'+port+path,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
 try:
  with urllib.request.urlopen(r,timeout=20) as x:return x.status,x.read(),dict(x.headers)
 except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
status,raw,_=get('/projects');assert status==200;projects=json.loads(raw).get('projects') or [];assert all((p.get('project_slug') if isinstance(p,dict) else p)!=slug for p in projects)
status,_,_=get('/project/status?slug='+urllib.parse.quote(slug));assert status==404
status,raw,h=get('/project/archive?slug='+urllib.parse.quote(slug)+'&ref=main',True);assert status==200 and raw[:2]==b'\x1f\x8b';assert h.get('X-CloudIF-SHA256')==hashlib.sha256(raw).hexdigest()
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tf:
 members=[m for m in tf.getmembers() if m.isfile()];names=[m.name for m in members]
 for f in cfg['files']:
  matches=[m for m in members if m.name.endswith('/'+f['path']) or m.name==f['path']];assert len(matches)==1,(f['path'],names)
  data=tf.extractfile(matches[0]).read();assert hashlib.sha256(data).hexdigest()==f['sha256']
 assert not any(n.endswith('/README.md') or n=='README.md' for n in names)
print('FORJA_ARCHIVE_FIXTURE=PASS');print('PROJECT_LIST_ISOLATION=PASS');print('PROJECT_STATUS_ISOLATION=PASS')
PY
}

apply_agent(){
  local current src sha release tmp old
  current=$(readlink -f "$POINTER");src="$current/cloudif-forja-agent.py";sha=$(sha256sum "$src"|awk '{print $1}')
  if [ "$sha" = "$PATCHED_SHA" ]; then agent_smoke;echo AGENT_ALREADY_PATCHED;return;fi
  [ "$sha" = "$BASE_SHA" ] || { echo "unexpected_forja_agent_sha:$sha" >&2;exit 3; }
  release=/srv/cloudif/app-releases/forja-agent/platform-v25-system-fixture-20260821;tmp="$release.tmp"
  rm -rf "$tmp";cp -a "$current" "$tmp"
  (cd "$tmp" && patch --batch --forward -p1 < "$PATCH_FILE")
  python3 -m py_compile "$tmp/cloudif-forja-agent.py"
  python3 "$TEST_FILE" --base "$src" --patch "$PATCH_FILE" --source "$tmp/cloudif-forja-agent.py"
  [ "$(sha256sum "$tmp/cloudif-forja-agent.py"|awk '{print $1}')" = "$PATCHED_SHA" ]
  rm -rf "$release";mv "$tmp" "$release"
  printf '%s\n' "$current" > "$STATE/previous-forja-pointer";chmod 0600 "$STATE/previous-forja-pointer"
  ln -sfn "$release" "$POINTER"
  if ! systemctl restart "$SERVICE" || ! agent_smoke; then ln -sfn "$current" "$POINTER";systemctl restart "$SERVICE" || true;echo FORJA_AGENT_ROLLBACK >&2;exit 4;fi
  echo FORJA_AGENT_PATCH=PASS
}

case "$ACTION" in
 status)
  verify_sources
  printf 'CURRENT=';readlink -f "$POINTER"
  printf 'SHA256=';sha256sum "$POINTER/cloudif-forja-agent.py"|awk '{print $1}'
  printf 'REGISTRY=';[ -f /var/lib/cloudif/forja-agent/system-fixtures/system-build-canary.json ]&&echo present||echo absent
  ;;
 apply)
  verify_sources;provision_repo;write_registry;apply_agent
  [ ! -e /var/lib/cloudif/forja-agent/projects/system-build-canary.json ]
  echo BUILD_WORKER_CANARY_FIXTURE=READY
  ;;
 rollback-agent)
  [ -s "$STATE/previous-forja-pointer" ];old=$(cat "$STATE/previous-forja-pointer");[ -f "$old/cloudif-forja-agent.py" ];ln -sfn "$old" "$POINTER";systemctl restart "$SERVICE";echo FORJA_AGENT_ROLLBACK=PASS
  ;;
 *) echo 'usage: provision_build_worker_canary_fixture.sh apply|status|rollback-agent' >&2;exit 2;;
esac
