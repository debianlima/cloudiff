import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'components/control-plane/current-apps/reconcile-worker-current'
CLIENT_PATH=APP/'cloudif_reconcile_client.py'
WORKER_PATH=APP/'cloudif-reconcile-worker.py'


def load_modules(tmp):
    spec=importlib.util.spec_from_file_location('cloudif_reconcile_client',CLIENT_PATH)
    client=importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
    client.DB=Path(tmp)/'reconcile.db'; client.QUEUE=Path(tmp)/'queue'
    sys.modules['cloudif_reconcile_client']=client
    config_events=types.ModuleType('cloudif_project_config_events')
    config_events.notify=lambda *a,**k:{'ok':True,'test_stub':True}
    sys.modules['cloudif_project_config_events']=config_events
    spec=importlib.util.spec_from_file_location('cloudif_reconcile_worker_t033',WORKER_PATH)
    worker=importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
    worker.QUEUE=client.QUEUE
    return client,worker


class ReconcileDeadletterObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.client,self.worker=load_modules(self.t.name)
        self.client.ensure_schema()

    def tearDown(self):
        sys.modules.pop('cloudif_reconcile_client',None)
        sys.modules.pop('cloudif_project_config_events',None)
        self.t.cleanup()

    def row(self,attempt=1,maximum=5):
        result=self.client.enqueue('project.updated',actor='test',project='t033-project',payload={'source':'synthetic-test'},dedupe_seconds=0)
        rid=result['request_id']
        con=self.client.connect()
        con.execute('update reconcile_requests set attempt_count=?,max_attempts=? where request_id=?',(attempt,maximum,rid));con.commit()
        row=dict(con.execute('select * from reconcile_requests where request_id=?',(rid,)).fetchone());con.close()
        return row

    def test_schema_migrates_diagnostic_columns(self):
        con=sqlite3.connect(Path(self.t.name)/'legacy.db')
        con.execute("""create table reconcile_requests(
          request_id text primary key, created_at text not null, started_at text default '', finished_at text default '',
          event_type text not null, actor text default '', username text default '', project text default '', tenant text default '',
          status text not null, message text default '', payload_json text default '{}', result_json text default '{}',
          attempt_count integer not null default 0, max_attempts integer not null default 5,
          next_attempt_at text not null default '', lease_owner text not null default '', lease_expires_at text not null default '',
          heartbeat_at text not null default '', partition_key text not null default '', coalesce_key text not null default '',
          dead_lettered_at text not null default '', last_error_type text not null default '')""")
        con.commit();con.close()
        self.client.DB=Path(self.t.name)/'legacy.db'
        self.client.ensure_schema()
        con=self.client.connect();cols={r[1] for r in con.execute('pragma table_info(reconcile_requests)')};con.close()
        self.assertTrue({'last_error_type','last_error_stage','last_error_upstream','last_error_status','last_error_code','last_error_detail'} <= cols)

    def test_retry_persists_sanitized_context_without_changing_retry_policy(self):
        row=self.row(attempt=1,maximum=5)
        exc=self.worker.ReconcileFailure(
            'project_membership_reconcile_failed','membership.forgejo','forja-agent',502,
            'Authorization: Bearer SYNTHETIC_TOKEN password=SYNTHETIC_PASSWORD ' + 'https://' + 'alice:secret' + '@example.invalid upstream_reset')
        self.worker.random.randint=lambda a,b:0
        self.worker.fail_or_retry(row,exc)
        saved=self.client.status(row['request_id'])
        self.assertEqual(saved['status'],'waiting_retry')
        self.assertEqual(saved['last_error_type'],'ReconcileFailure')
        self.assertEqual(saved['last_error_stage'],'membership.forgejo')
        self.assertEqual(saved['last_error_upstream'],'forja-agent')
        self.assertEqual(saved['last_error_status'],502)
        self.assertEqual(saved['last_error_code'],'project_membership_reconcile_failed')
        self.assertIn('<redacted>',saved['last_error_detail'])
        for forbidden in ('SYNTHETIC_TOKEN','SYNTHETIC_PASSWORD','alice:secret'):
            self.assertNotIn(forbidden,saved['last_error_detail'])
        self.assertIn('nova tentativa em 5s',saved['message'])
        self.assertEqual(saved['attempt_count'],1)
        self.assertEqual(saved['max_attempts'],5)

    def test_deadletter_preserves_legacy_core_and_adds_sanitized_diagnostic(self):
        row=self.row(attempt=5,maximum=5)
        exc=self.worker.ReconcileFailure('project_runtime_reconcile_failed','runtime.reconcile','runtime-reconciler',503,'token=NEVER_PERSIST service_unavailable')
        self.worker.fail_or_retry(row,exc)
        saved=self.client.status(row['request_id']); result=json.loads(saved['result_json'])
        self.assertEqual(saved['status'],'dead_letter')
        self.assertTrue(saved['dead_lettered_at'])
        self.assertEqual(result['error_type'],'ReconcileFailure')
        self.assertIs(result['secrets_exposed'],False)
        self.assertEqual(result['diagnostic']['stage'],'runtime.reconcile')
        self.assertEqual(result['diagnostic']['upstream'],'runtime-reconciler')
        self.assertEqual(result['diagnostic']['status'],503)
        self.assertEqual(result['diagnostic']['code'],'project_runtime_reconcile_failed')
        self.assertNotIn('NEVER_PERSIST',json.dumps(result))
        self.assertIn('<redacted>',result['diagnostic']['detail'])

    def test_generic_exception_never_persists_raw_message(self):
        row=self.row(attempt=5,maximum=5)
        self.worker.fail_or_retry(row,RuntimeError('BARE_SYNTHETIC_SECRET_VALUE'))
        saved=self.client.status(row['request_id']); result=json.loads(saved['result_json'])
        serialized=json.dumps(result)
        self.assertNotIn('BARE_SYNTHETIC_SECRET_VALUE',serialized)
        self.assertEqual(saved['last_error_code'],'RuntimeError')
        self.assertEqual(saved['last_error_detail'],'RuntimeError')
        self.assertEqual(result['diagnostic']['detail'],'RuntimeError')

    def test_success_clears_previous_error_context(self):
        row=self.row(attempt=1,maximum=5)
        self.worker.random.randint=lambda a,b:0
        self.worker.fail_or_retry(row,self.worker.ReconcileFailure('temporary','membership.komodo','komodo-agent',503,'secret=OLD'))
        self.worker.update_request(row['request_id'],'ready','ok',{'ok':True})
        saved=self.client.status(row['request_id'])
        self.assertEqual(saved['status'],'ready')
        self.assertEqual(saved['last_error_type'],'')
        self.assertEqual(saved['last_error_stage'],'')
        self.assertEqual(saved['last_error_upstream'],'')
        self.assertEqual(saved['last_error_status'],0)
        self.assertEqual(saved['last_error_code'],'')
        self.assertEqual(saved['last_error_detail'],'')

    def test_membership_failure_identifies_the_failed_upstream(self):
        self.assertIn("'membership.forgejo','forja-agent'",WORKER_PATH.read_text())
        self.assertIn("'membership.komodo','komodo-agent'",WORKER_PATH.read_text())
        self.assertIn("'runtime.reconcile','runtime-reconciler'",WORKER_PATH.read_text())

    def test_historical_deadletter_core_remains_in_source(self):
        source=WORKER_PATH.read_text()
        self.assertIn("{'error_type':etype,'secrets_exposed':False}",source)
        self.assertIn("result['diagnostic']=ctx",source)

if __name__=='__main__': unittest.main()
