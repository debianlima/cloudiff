#!/usr/bin/env bash
set -uo pipefail
OUT=/var/log/cloudif-healthcheck.log
STATE=/var/lib/cloudif/health/integrated-health.json
LOCK=/run/cloudif-healthcheck.lock
NOW=$(date -Is)
START_EPOCH=$(date +%s)
status=0
mkdir -p /var/lib/cloudif/health
exec 9>"$LOCK"
if ! flock -n 9; then
  printf '%s healthcheck state=busy
' "$NOW" >>"$OUT"
  exit 0
fi
write_state(){
  local result=$1 finished duration tmp
  finished=$(date -Is); duration=$(( $(date +%s)-START_EPOCH )); tmp=$(mktemp /var/lib/cloudif/health/.integrated-health.XXXXXX)
  printf '{"ok":%s,"status":"%s","started_at":"%s","finished_at":"%s","duration_seconds":%s,"secrets_exposed":false}
' "$([ "$result" = healthy ] && echo true || echo false)" "$result" "$NOW" "$finished" "$duration" >"$tmp"
  chmod 600 "$tmp"; mv -f "$tmp" "$STATE"
}
trap 'rc=$?; if [ "$rc" -eq 0 ]; then write_state healthy; else write_state unhealthy; fi' EXIT
check_http(){ local name=$1 url=$2 expected=$3; code=$(curl -skS -m 4 -o /dev/null -w '%{http_code}' "$url" || echo 000); echo "$NOW http name=$name code=$code expected=$expected" >>"$OUT"; [[ "$code" =~ $expected ]] || status=1; }
check_json_health(){
  local name=$1 url=$2
  local body headers code
  body=$(mktemp); headers=$(mktemp)
  code=$(curl -skS -m 5 -D "$headers" -o "$body" -w '%{http_code}' "$url" || echo 000)
  local ok=1
  [ "$code" = 200 ] || ok=0
  grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' "$body" || ok=0
  grep -qi '^Cache-Control: no-store' "$headers" || ok=0
  grep -qi '^X-Content-Type-Options: nosniff' "$headers" || ok=0
  grep -qi '^X-Frame-Options: DENY' "$headers" || ok=0
  echo "$NOW json_health name=$name code=$code secure=$ok" >>"$OUT"
  [ "$ok" -eq 1 ] || status=1
  rm -f "$body" "$headers"
}
check_oneshot_result(){
  local name=$1 unit=$2 max_age=$3
  local result exit_status last_exit now_mono age_sec ok=1
  result=$(systemctl show "$unit" -p Result --value 2>/dev/null || true)
  exit_status=$(systemctl show "$unit" -p ExecMainStatus --value 2>/dev/null || true)
  last_exit=$(systemctl show "$unit" -p ExecMainExitTimestampMonotonic --value 2>/dev/null || echo 0)
  now_mono=$(awk '{printf "%.0f", $1*1000000}' /proc/uptime)
  age_sec=$(( (now_mono - ${last_exit:-0}) / 1000000 ))
  [ "$result" = success ] || ok=0
  [ "${exit_status:-1}" = 0 ] || ok=0
  [ "$age_sec" -le "$max_age" ] || ok=0
  echo "$NOW oneshot name=$name result=$result exit=$exit_status age_sec=$age_sec ok=$ok" >>"$OUT"
  [ "$ok" -eq 1 ] || status=1
}
check_redirect(){
  local name=$1 url=$2
  local headers code location
  headers=$(mktemp)
  code=$(curl -skS -m 6 -D "$headers" -o /dev/null -w '%{http_code}' "$url" || echo 000)
  location=$(awk -F': ' 'tolower($1)=="location"{print $2}' "$headers" | tr -d '
' | head -1)
  local ok=1
  [[ "$code" =~ ^30[12]$ ]] || ok=0
  [[ "$location" == https://* || "$location" == /* ]] || ok=0
  grep -qi '^Cache-Control: no-store' "$headers" || ok=0
  grep -qi '^X-Content-Type-Options: nosniff' "$headers" || ok=0
  echo "$NOW redirect name=$name code=$code https=$ok" >>"$OUT"
  [ "$ok" -eq 1 ] || status=1
  rm -f "$headers"
}
for s in cloudif-admin-portal cloudif-authz-gate cloudif-deploy-panel cloudif-node-metrics cloudif-supabase-launch-api cloudif-supabase-session-broker cloudif-tenant-guard cloudif-input-firewall cloudif-portal-qa; do
  state=$(systemctl is-active "$s.service" 2>/dev/null || true); echo "$NOW service name=$s state=$state" >>"$OUT"; [ "$state" = active ] || status=1
done
check_http portal http://127.0.0.1:18094/cloudif/portal/ '200|302'
check_http staging http://127.0.0.1:18194/cloudif/staging/ '200|302'
check_http qa http://127.0.0.1:18195/cloudif/qa/ '200|302'
check_http metrics http://10.62.92.7:18096/ '200'
check_http router http://10.62.92.7:8099/ '200|301|302|401|404'
check_json_health launch_api http://127.0.0.1:18090/health
check_json_health oidc_broker http://127.0.0.1:18091/health
check_redirect oidc_public_start https://cloudiff.duckdns.org/cloudif/supabase/session/start
check_oneshot_result logrotate_service logrotate.service 129600
check_oneshot_result logrotate_verify cloudif-logrotate-verify.service 129600
for u in cloudif-reconcile-worker.path cloudif-release-dispatch.timer cloudif-machine-controller.service cloudif-machine-harvester.timer cloudif-machine-guardian.timer; do
  unit_state=$(systemctl is-active "$u" 2>/dev/null || true)
  echo "$NOW automation_unit name=$u state=$unit_state" >>"$OUT"
  [ "$unit_state" = active ] || status=1
done
check_oneshot_result release_dispatch cloudif-release-dispatch.service 300
read -r reconcile_stale release_due_stale release_running_stale release_failed_recent queue_markers < <(python3 - <<'PYQ'
import datetime as dt, sqlite3
p='/var/lib/cloudif/portal/cloudif-portal.db'
now=dt.datetime.now(dt.timezone.utc)
def iso(delta): return (now-delta).replace(microsecond=0).isoformat().replace('+00:00','Z')
con=sqlite3.connect(p)
queries=[
 ("select count(*) from reconcile_requests where status in ('queued','running') and created_at<?", (iso(dt.timedelta(minutes=10)),)),
 ("select count(*) from release_jobs where status in ('scheduled','retry') and scheduled_at<?", (iso(dt.timedelta(minutes=10)),)),
 ("select count(*) from release_jobs where status='running' and started_at<>'' and started_at<?", (iso(dt.timedelta(hours=1)),)),
 ("select count(*) from release_jobs where status in ('failed','deployed_unfinalized') and finished_at>=?", (iso(dt.timedelta(minutes=15)),)),
]
vals=[]
for q,args in queries:
 try: vals.append(con.execute(q,args).fetchone()[0])
 except Exception: vals.append(999)
con.close()
from pathlib import Path
vals.append(len(list(Path('/var/lib/cloudif/reconcile-queue/incoming').glob('*.json'))))
print(*vals)
PYQ
)
echo "$NOW release_automation reconcile_stale=$reconcile_stale release_due_stale=$release_due_stale release_running_stale=$release_running_stale release_failed_recent=$release_failed_recent queue_markers=$queue_markers" >>"$OUT"
machine_admin=$(curl -fsS --max-time 5 http://127.0.0.1:18110/health 2>/dev/null || true)
echo "$NOW machine_admin health=$machine_admin" >>"$OUT"
echo "$machine_admin" | grep -q '"ok": true' || status=1
machine_inventory_age=$(python3 - <<'PYQ'
from pathlib import Path
import time
p=Path('/var/lib/cloudif-machine-agent/last-inventory.json')
print(int(time.time()-p.stat().st_mtime) if p.exists() else 999999)
PYQ
)
echo "$NOW machine_admin inventory_age=$machine_inventory_age" >>"$OUT"
[ "$machine_inventory_age" -le 600 ] || status=1
certificate_health=$(python3 - <<'PYQ'
import json
from pathlib import Path
p=Path('/var/lib/cloudif-machine-agent/current-inventory.json')
if not p.exists():
    print('0 0 0 0 0 0 1')
else:
    inv=json.loads(p.read_text())
    certs=[x for x in inv.get('components',[]) if x.get('kind')=='certificate']
    states=['ok','warning','critical','urgent','expired','error']
    counts={state:sum(1 for x in certs if x.get('state')==state) for state in states}
    print(len(certs),*(counts[state] for state in states))
PYQ
)
read -r cert_total cert_ok cert_warning cert_critical cert_urgent cert_expired cert_error <<EOF
$certificate_health
EOF
echo "$NOW certificates total=$cert_total ok=$cert_ok warning=$cert_warning critical=$cert_critical urgent=$cert_urgent expired=$cert_expired error=$cert_error" >>"$OUT"
[ "${cert_urgent:-1}" -eq 0 ] || status=1
[ "${cert_expired:-1}" -eq 0 ] || status=1
[ "${cert_error:-1}" -eq 0 ] || status=1
[ "$reconcile_stale" -eq 0 ] || status=1
[ "$release_due_stale" -eq 0 ] || status=1
[ "$release_running_stale" -eq 0 ] || status=1
[ "$release_failed_recent" -eq 0 ] || status=1
[ "$queue_markers" -lt 50 ] || status=1
# Machine administration production checks.
for u in cloudif-certificate-alert-dispatcher.timer cloudif-machine-admin-db-backup.timer cloudif-agent-pki-crl-refresh.timer cloudif-controller-certificate-renew.timer cloudif-machine-admin-dr-backup.timer cloudif-machine-admin-dr-restore-test.timer cloudif-control-plane-integrity.timer; do
  unit_state=$(systemctl is-active "$u" 2>/dev/null || true)
  echo "$NOW machine_admin_unit name=$u state=$unit_state" >>"$OUT"
  [ "$unit_state" = active ] || status=1
done
pg_health=$(docker inspect cloudif-machine-admin-db --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)
echo "$NOW machine_admin_postgres health=$pg_health" >>"$OUT"
[ "$pg_health" = healthy ] || status=1
if [ -f /etc/cloudif/machine-controller-db.env ]; then
  set -a; . /etc/cloudif/machine-controller-db.env; set +a
  pg_query=$(python3 - <<'PYQ'
try:
 from cloudif_machine_db import connect
 c=connect(); row=c.execute('select count(*) as n from machines').fetchone(); c.close(); print(row['n'])
except Exception: print(-1)
PYQ
)
else pg_query=-1; fi
echo "$NOW machine_admin_postgres machines=$pg_query" >>"$OUT"
[ "$pg_query" -ge 3 ] 2>/dev/null || status=1
dr_archive=$(find /srv/cloudif/managed-backups/machine-admin-dr -maxdepth 1 -type f -name '*.tar.zst' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
dr_restore_marker=/srv/cloudif/managed-backups/machine-admin-dr/last-restore-validation.json
if [ -n "$dr_archive" ] && [ -f "$dr_archive.sha256" ]; then
  sha256sum -c "$dr_archive.sha256" >/dev/null 2>&1 || status=1
  dr_age=$(( $(date +%s) - $(stat -c %Y "$dr_archive") ))
  [ "$dr_age" -le 129600 ] || status=1
else
  status=1
fi
if [ -f "$dr_restore_marker" ]; then
  dr_restore_check=$(python3 - "$dr_restore_marker" "$dr_archive" <<'PYDR'
import json,sys,datetime as dt
marker,archive=sys.argv[1:]
try:
 d=json.load(open(marker))
 when=dt.datetime.fromisoformat(d['validated_at'].replace('Z','+00:00'))
 age=(dt.datetime.now(dt.timezone.utc)-when).total_seconds()
 ok=d.get('result')=='ok' and bool(d.get('archive')) and age<=691200
 print('ok' if ok else 'invalid')
except Exception:
 print('invalid')
PYDR
)
  [ "$dr_restore_check" = ok ] || status=1
else
  status=1
fi
dr_ok=0; dr_age=999999999; dr_pg_ref=0
if [ -n "$dr_archive" ] && [ -f "$dr_archive.sha256" ]; then
  dr_ts=$(stat -c %Y "$dr_archive" 2>/dev/null || echo 0); dr_age=$(( $(date +%s)-dr_ts ))
  if sha256sum -c "$dr_archive.sha256" >/dev/null 2>&1; then
    manifest="${dr_archive%.tar.zst}.manifest.json"
    if [ -f "$manifest" ]; then
      dr_pg_ref=$(python3 - "$manifest" <<'PYQ'
import json,os,sys
try:
 d=json.load(open(sys.argv[1])); p=d.get('latest_postgres_backup') or ''; h=d.get('latest_postgres_sha256') or ''
 print(1 if p and h and os.path.isfile(p) and os.path.isfile(p+'.sha256') else 0)
except Exception: print(0)
PYQ
)
      [ "$dr_age" -lt 129600 ] && [ "$dr_pg_ref" -eq 1 ] && dr_ok=1
    fi
  fi
fi
echo "$NOW machine_admin_dr_backup ok=$dr_ok age_seconds=$dr_age postgres_reference=$dr_pg_ref" >>"$OUT"
[ "$dr_ok" -eq 1 ] || status=1
admin_db_backup=$(find /srv/cloudif/managed-backups/machine-admin-postgres/daily -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f1)
admin_db_backup_ts=${admin_db_backup%.*}; admin_db_backup_ts=${admin_db_backup_ts:-0}
admin_db_backup_age=$(( $(date +%s)-admin_db_backup_ts ))
echo "$NOW machine_admin_backup age_seconds=$admin_db_backup_age" >>"$OUT"
[ "$admin_db_backup_ts" -gt 0 ] && [ "$admin_db_backup_age" -lt 129600 ] || status=1
PKI=/var/lib/cloudif-agent-pki
mtls_code=$(curl -sS --max-time 8 --cacert "$PKI/issuing/certs/ca-chain.pem" --cert "$PKI/issued/hospedagem.pem" --key "$PKI/issued/hospedagem.key" -o /tmp/cloudif-mtls-health.$$ -w '%{http_code}' https://10.62.92.7:18111/health 2>/dev/null || echo 000)
mtls_ok=0; [ "$mtls_code" = 200 ] && grep -q '"ok"[[:space:]]*:[[:space:]]*true' /tmp/cloudif-mtls-health.$$ && mtls_ok=1
rm -f /tmp/cloudif-mtls-health.$$
echo "$NOW machine_admin_mtls code=$mtls_code ok=$mtls_ok" >>"$OUT"
[ "$mtls_ok" -eq 1 ] || status=1
admin_integrity=$(python3 - <<'PYQ'
import base64,datetime as dt,json,os
from pathlib import Path
try:
 from cloudif_machine_db import connect
 from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
 c=connect(); rows=c.execute('select machine_id,hostname,state,last_seen,policy_version,policy_json,inventory_json from machines order by hostname').fetchall(); c.close()
 now=dt.datetime.now(dt.timezone.utc); stale=[]; invalid=[]; missing_renewal_timer=[]
 pub_path=os.environ.get('CLOUDIF_MACHINE_POLICY_PUBLIC_KEY','/etc/cloudif/machine-policy-signing.pub')
 pub=base64.b64decode(Path(pub_path).read_text().strip()); key=Ed25519PublicKey.from_public_bytes(pub)
 for r in rows:
  seen=dt.datetime.fromisoformat(str(r['last_seen']).replace('Z','+00:00'))
  if (now-seen).total_seconds()>600: stale.append(r['hostname'])
  inv=json.loads(r.get('inventory_json') or '{}') if 'inventory_json' in r.keys() else {}
  if r['hostname'] in ('forja','mauricio'):
   timers=[x for x in inv.get('components',[]) if x.get('id')=='timer:cloudif-machine-certificate-renew.service' and x.get('state')=='configured']
   if not timers: missing_renewal_timer.append(r['hostname'])
  if int(r['policy_version'] or 0)>0:
   try:
    env=json.loads(r['policy_json']); payload=env['payload']; raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(); key.verify(base64.b64decode(env['signature_b64']),raw)
    assert payload['machine_id']==r['machine_id'] and int(payload['version'])==int(r['policy_version'])
    assert payload['executor_actions_enabled'] is False and payload['auto_recovery_enabled'] is False
   except Exception: invalid.append(r['hostname'])
 print(json.dumps({'count':len(rows),'stale':stale,'invalid_policy':invalid,'missing_renewal_timer':missing_renewal_timer},separators=(',',':')))
except Exception as e: print(json.dumps({'count':-1,'error':type(e).__name__},separators=(',',':')))
PYQ
)
echo "$NOW machine_admin_integrity $admin_integrity" >>"$OUT"
echo "$admin_integrity" | grep -q '"count":3' || status=1
echo "$admin_integrity" | grep -q '"stale":\[\]' || status=1
echo "$admin_integrity" | grep -q '"invalid_policy":\[\]' || status=1
echo "$admin_integrity" | grep -q '"missing_renewal_timer":\[\]' || status=1
pki_ok=1
for cert in "$PKI/root/certs/root-ca.pem" "$PKI/issuing/certs/issuing-ca.pem" "$PKI/issued/controller-server.pem" "$PKI/issued/hospedagem.pem" "$PKI/issued/forja.pem" "$PKI/issued/mauricio.pem"; do
  openssl x509 -checkend 2592000 -noout -in "$cert" >/dev/null 2>&1 || pki_ok=0
done
for crl in "$PKI/root/certs/root-ca.crl.pem" "$PKI/issuing/certs/issuing-ca.crl.pem"; do
  next=$(openssl crl -in "$crl" -noout -nextupdate 2>/dev/null | cut -d= -f2-)
  [ -n "$next" ] || { pki_ok=0; continue; }
  next_epoch=$(date -d "$next" +%s 2>/dev/null || echo 0)
  [ $((next_epoch-$(date +%s))) -gt 604800 ] || pki_ok=0
done
echo "$NOW machine_admin_pki ok=$pki_ok" >>"$OUT"
[ "$pki_ok" -eq 1 ] || status=1
/usr/local/sbin/cloudif-machine-executor.py >/tmp/cloudif-executor-health.$$ 2>&1
executor_rc=$?
rm -f /tmp/cloudif-executor-health.$$
echo "$NOW machine_admin_executor rc=$executor_rc" >>"$OUT"
[ "$executor_rc" -eq 77 ] || status=1
unhealthy=$(docker ps --filter health=unhealthy -q | wc -l); stopped=$(docker ps -a --filter status=exited -q | wc -l)
functions_created=$(docker ps -a --filter name=cloudif_iff1742962-functions-1 --filter status=created -q | wc -l)
echo "$NOW docker unhealthy=$unhealthy exited=$stopped functions_created=$functions_created" >>"$OUT"
[ "$functions_created" -eq 0 ] || status=1
[ "$unhealthy" -eq 0 ] || status=1
use=$(df --output=pcent / | tail -1 | tr -dc '0-9'); echo "$NOW disk root_percent=$use" >>"$OUT"; [ "$use" -lt 85 ] || status=1
for p in 53 389 636 3268; do timeout 2 bash -c "</dev/tcp/10.68.128.252/$p" >/dev/null 2>&1; rc=$?; echo "$NOW ad host=10.68.128.252 port=$p rc=$rc" >>"$OUT"; [ "$rc" -eq 0 ] || status=1; done
# Backup freshness: configuration <= 36h, tenant databases <= 36h.
now_epoch=$(date +%s)
latest_config=$(find /srv/cloudif/managed-backups/config -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f1)
latest_db=$(find /srv/cloudif/managed-backups/databases-v2 -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f1)
for kind in config db; do
  var="latest_${kind}"
  ts=${!var:-0}; ts=${ts%.*}
  age=$((now_epoch-ts))
  echo "$NOW backup kind=$kind age_seconds=$age" >>"$OUT"
  [ "$ts" -gt 0 ] && [ "$age" -lt 129600 ] || status=1
done
# Monthly restore-test freshness: <= 40 days.
restore_log=/var/log/cloudif-restore-test.log
restore_marker=/srv/cloudif/managed-backups/machine-admin-dr/last-restore-validation.json
if [ -s "$restore_log" ]; then
  restore_ts=$(stat -c %Y "$restore_log")
elif [ -s "$restore_marker" ]; then
  restore_ts=$(stat -c %Y "$restore_marker")
else
  restore_ts=0
fi
restore_test_age=$((now_epoch-restore_ts))
echo "$NOW restore_test_age=$restore_test_age" >>"$OUT"
[ "$restore_test_age" -lt 3456000 ] || status=1
# UI smoke test status.
ui_smoke_prod=$(systemctl show cloudif-prod-ui-smoke.service -p ExecMainStatus --value 2>/dev/null || echo 1)
ui_smoke_qa=$(systemctl show cloudif-qa-ui-smoke.service -p ExecMainStatus --value 2>/dev/null || echo 1)
echo "$NOW ui_smoke_prod=$ui_smoke_prod ui_smoke_qa=$ui_smoke_qa" >>"$OUT"
[ "$ui_smoke_prod" = "0" ] && [ "$ui_smoke_qa" = "0" ] || status=1

integrity_result=/var/lib/cloudif-machine-admin/control-plane-integrity-result.json
integrity_ok=0; integrity_age=999999999; integrity_changed=-1; integrity_missing=-1; integrity_permissions=-1
if [ -f "$integrity_result" ]; then
  integrity_data=$(python3 - "$integrity_result" <<'PYQ'
import datetime as dt,json,sys
try:
 d=json.load(open(sys.argv[1])); t=dt.datetime.fromisoformat(str(d.get('checked_at') or '').replace('Z','+00:00')); age=int((dt.datetime.now(dt.timezone.utc)-t).total_seconds())
 print(f"{1 if d.get('result')=='ok' else 0} {age} {len(d.get('changed') or [])} {len(d.get('missing') or [])} {len(d.get('permission_violations') or [])}")
except Exception: print('0 999999999 -1 -1 -1')
PYQ
  )
  read -r integrity_ok integrity_age integrity_changed integrity_missing integrity_permissions <<<"$integrity_data"
fi
echo "$NOW control_plane_integrity ok=$integrity_ok age_seconds=$integrity_age changed=$integrity_changed missing=$integrity_missing permission_violations=$integrity_permissions" >>"$OUT"
[ "$integrity_ok" -eq 1 ] && [ "$integrity_age" -lt 172800 ] && [ "$integrity_changed" -eq 0 ] && [ "$integrity_missing" -eq 0 ] && [ "$integrity_permissions" -eq 0 ] || status=1

exit "$status"
