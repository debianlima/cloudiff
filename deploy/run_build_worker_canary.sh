#!/usr/bin/env bash
set -euo pipefail
EVID=${CLOUDIFF_BUILD_CANARY_EVIDENCE:-/var/lib/cloudiff-v2/build-worker-canary-v25}
SLUG=system-build-canary
KIND=cloudiff.v2.build.classic
PG=cloudiff-v2-postgres
install -d -m 0700 "$EVID"
set -a; . /etc/cloudiff-v2/build-broker.env; . /etc/cloudiff-v2/build-worker.env; set +a
: "${CLOUDIFF_BUILD_TOKEN:?}" "${CLOUDIFF_BUILD_WORKSPACE_TOKEN:?}"
pg(){ printf '%s\n' "$1" | docker exec -i "$PG" sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'; }
active=$(pg "select count(*) from cloudiff_v2.jobs where kind='$KIND' and status in ('ready','waiting_retry','leased') and payload->>'project_slug' <> '$SLUG';" | tr -d '[:space:]')
[ "$active" = 0 ] || { echo "other_classic_jobs_active:$active" >&2;exit 3; }
existing=$(pg "select count(*) from cloudiff_v2.jobs where kind='$KIND' and payload->>'project_slug'='$SLUG';" | tr -d '[:space:]')
[ "$existing" -le 1 ] || { echo "fixture_job_count_invalid:$existing" >&2;exit 3; }
# Workspace preflight with the same token used by ClassicBuildWorker.
python3 - "$EVID/workspace.json" <<'PY'
import json,os,sys,urllib.request
payload=json.dumps({'project_slug':'system-build-canary','ref':'main','trace_id':'p11-preflight'},separators=(',',':')).encode()
r=urllib.request.Request('http://127.0.0.1:18206/v1/test-static',data=payload,method='POST',headers={'Authorization':'Bearer '+os.environ['CLOUDIFF_BUILD_WORKSPACE_TOKEN'],'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=240) as x:raw=x.read();assert x.status==200
open(sys.argv[1],'wb').write(raw);v=json.loads(raw);res=v['result'];assert v['ok'] is True and res['valid'] is True;assert res['compose']['parser_ok'] is True and res['violations']==[];print('WORKSPACE_VALID=PASS');print('ARCHIVE_SHA256='+res['archive_sha256'])
PY
# Obtain current runtime-policy digest; never hardcode it.
curl -fsS --max-time 15 -H 'Content-Type: application/json' --data '{"framework":"static"}' http://127.0.0.1:18212/v1/plan > "$EVID/plan.json"
PLAN=$(python3 - "$EVID/plan.json" <<'PY'
import json,re,sys
x=json.load(open(sys.argv[1]));d=x.get('build_plan_digest','');assert x.get('ok') is True and re.fullmatch(r'[a-f0-9]{64}',d);print(d)
PY
)
# Reserve through BuildBroker shadow only when no prior canary exists; otherwise resume the preserved attempt-1 job.
RUN_WORKER=1
if [ "$existing" = 1 ]; then
  row=$(pg "select job_id::text||'|'||status||'|'||attempt::text||'|'||(payload->>'build_plan_digest') from cloudiff_v2.jobs where kind='$KIND' and payload->>'project_slug'='$SLUG';")
  IFS='|' read -r BUILD_ID status attempt saved_plan <<< "$row"
  [ "$saved_plan" = "$PLAN" ] || { echo "fixture_plan_drift" >&2;exit 3; }
  if [ "$status" = waiting_retry ] && [ "$attempt" = 1 ]; then EXPECTED_ATTEMPTS=2;echo BUILD_RESUME=PASS
  elif [ "$status" = succeeded ] && [ "$attempt" = 2 ]; then EXPECTED_ATTEMPTS=2;RUN_WORKER=0;echo BUILD_ALREADY_SUCCEEDED=PASS
  else echo "fixture_resume_state_invalid:$status:$attempt" >&2;exit 3;fi
else
  EXPECTED_ATTEMPTS=1
  python3 - "$PLAN" "$EVID/reserve.json" <<'PY'
import json,os,sys,urllib.request
plan,out=sys.argv[1:];payload=json.dumps({'project_slug':'system-build-canary','ref':'main','framework':'static','build_plan_digest':plan},separators=(',',':')).encode()
r=urllib.request.Request('http://127.0.0.1:18221/v1/builds',data=payload,method='POST',headers={'Authorization':'Bearer '+os.environ['CLOUDIFF_BUILD_TOKEN'],'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=30) as x:raw=x.read();assert x.status==202
open(out,'wb').write(raw);v=json.loads(raw);assert v['ok'] is True and v['status']=='queued';print('BUILD_RESERVED=PASS');print('BUILD_ID='+v['build_id'])
PY
  BUILD_ID=$(python3 -c 'import json,re;v=json.load(open("'"$EVID"'/reserve.json"));b=v["build_id"];assert re.fullmatch(r"[0-9a-f-]{36}",b);print(b)')
  status=$(pg "select status from cloudiff_v2.jobs where job_id='$BUILD_ID'::uuid and kind='$KIND' and payload->>'project_slug'='$SLUG';" | tr -d '[:space:]')
  [ "$status" = ready ];echo JOB_READY=PASS
fi
printf '%s\n' "$BUILD_ID" > "$EVID/build-id"
if [ "$RUN_WORKER" = 1 ]; then
  systemctl reset-failed cloudiff-v2-build-worker-canary.service || true
  systemctl start cloudiff-v2-build-worker-canary.service
  [ "$(systemctl show cloudiff-v2-build-worker-canary.service -p Result --value)" = success ]
fi
# Query status/artifact/logs through BuildBroker, not directly from result JSON in PostgreSQL.
python3 - "$BUILD_ID" "$EVID" "$EXPECTED_ATTEMPTS" <<'PY'
import json,os,sys,urllib.request,re
bid,e,expected=sys.argv[1:];expected=int(expected);base=f'http://127.0.0.1:18221/v1/projects/system-build-canary/builds/{bid}';hdr={'Authorization':'Bearer '+os.environ['CLOUDIFF_BUILD_TOKEN']}
def get(suffix,name):
 r=urllib.request.Request(base+suffix,headers=hdr)
 with urllib.request.urlopen(r,timeout=20) as x:raw=x.read();assert x.status==200
 open(e+'/'+name,'wb').write(raw);return json.loads(raw)
st=get('','status.json');assert st['build']['status']=='succeeded' and st['build']['attempts']==expected
art=get('/artifact','artifact.json');a=art['artifact'];assert art['attestation_verified'] is True and a['attestation_verified'] is True;assert a['production_ready'] is True and a['valid'] is True and a['image_created'] is True;img=a['artifact_image_id'];assert isinstance(img,str) and img.startswith('sha256:')
logs=get('/logs','logs.json')['logs'];assert 'status:succeeded' in logs;assert not re.search(r'(?i)(authorization|password|secret|api[_-]?key)\s*[:=]\s*\S+',logs)
open(e+'/artifact-image-id','w').write(img+'\n');print('BUILD_SUCCEEDED=PASS');print('ATTESTATION_VERIFIED=PASS');print('ARTIFACT_IMAGE_ID='+img)
PY
# Exact attempt sequence for this resumed canary: the pre-P14 failure followed by the v28 success.
seq=$(pg "select string_agg(attempt::text||':'||worker_id||':'||coalesce(outcome,'')||':'||coalesce(error,''),',' order by attempt) from cloudiff_v2.job_attempts where job_id='$BUILD_ID'::uuid;")
if [ "$EXPECTED_ATTEMPTS" = 2 ]; then [ "$seq" = '1:hospedagem-worker-v2:waiting_retry:upstream_http_422,2:hospedagem-worker-v2:succeeded:' ];fi
echo ATTEMPT_SEQUENCE=PASS
# Persist selected evidence before destructive cleanup.
pg "select status||'|'||attempt::text||'|'||coalesce(result->>'artifact_image_id','') from cloudiff_v2.jobs where job_id='$BUILD_ID'::uuid;" > "$EVID/db-before-cleanup.txt"
# Cleanup is scoped to the returned UUID only; repository fixture remains persistent.
pg "begin; delete from cloudiff_v2.job_partition_leases where job_id='$BUILD_ID'::uuid; delete from cloudiff_v2.job_attempts where job_id='$BUILD_ID'::uuid; delete from cloudiff_v2.jobs where job_id='$BUILD_ID'::uuid; commit;" > "$EVID/cleanup-sql.txt"
left=$(pg "select count(*) from cloudiff_v2.jobs where job_id='$BUILD_ID'::uuid;" | tr -d '[:space:]');[ "$left" = 0 ]
echo JOB_CLEANUP=PASS
printf 'WORKER_NRESTARTS=';systemctl show cloudiff-v2-build-worker-canary.service -p NRestarts --value
printf 'WORKER_FINAL=';systemctl is-active cloudiff-v2-build-worker-canary.service 2>/dev/null || true
printf 'LEGACY_BUILD_BROKER=';systemctl is-active cloudif-build-broker.service
printf 'V2_BUILD_BROKER=';systemctl is-active cloudiff-v2-build-broker-shadow.service
echo CANARY_E2E=PASS
