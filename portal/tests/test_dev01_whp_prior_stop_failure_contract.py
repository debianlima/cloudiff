"""Isolated W1/Hn/Pn promotion contract with fake Docker and fake storage.

Executes only the final (runtime-effective) function definition from AST.
No shell, network, credentials, containers, production DB or live access.
"""
import ast
import json
import re
import sqlite3
import tempfile
import hmac
from pathlib import Path
import types
import unittest

SOURCE = Path(__file__).resolve().parents[2]/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
TREE = ast.parse(SOURCE.read_text())
FUNCTION = [node for node in TREE.body if isinstance(node, ast.FunctionDef)
            and node.name == 'cloudif_publication_release'][-1]
CODE = compile(ast.Module(body=[FUNCTION], type_ignores=[]), str(SOURCE), 'exec')
ACTIVATION_FUNCTION = [node for node in TREE.body if isinstance(node, ast.FunctionDef)
                       and node.name == 'cloudif_publication_release_activate'][-1]
ACTIVATION_CODE = compile(ast.Module(body=[ACTIVATION_FUNCTION], type_ignores=[]), str(SOURCE), 'exec')
HELPER_NAMES=('_cloudif_v144_atomic_updates','_cloudif_v144_retract_initial_alias','_cloudif_v144_recover_previous')
HELPER_NODES=[next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name) for name in HELPER_NAMES]
HELPER_CODE=compile(ast.Module(body=HELPER_NODES,type_ignores=[]),str(SOURCE),'exec')

class _NoopJournalForLegacyTests:
    """Existing Hn/Pn tests cover the default-disabled compatibility mode."""
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def finish(self):return None


class FakeProcess:
    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

class FakeTransactionalDb:
    """Simulates SQLite begin/commit/rollback, never opens a real database."""
    def __init__(self,fixture):
        self.fixture=fixture
        self.pending=[]

    def execute(self,sql,params=()):
        if sql=='BEGIN IMMEDIATE':
            self.pending=[]
            return self
        self.fixture.db_step+=1
        if self.fixture.fail_at_db_step==self.fixture.db_step:
            raise RuntimeError('synthetic_db_write_failed')
        self.pending.append((sql,params))
        return self

    def commit(self):
        self.fixture.db_calls.extend(self.pending)
        self.pending=[]

    def rollback(self):
        self.fixture.db_rollback_count+=1
        self.pending=[]

    def close(self):
        pass

class PromotionFixture:
    def __init__(self, previous_stop_status=0, restore_fails=False, changed_id=False,
                 fail_at_db_step=0, previous_start_status=0, alias_disconnect_fails=False,
                 alias_connect_fails=False):
        self.calls=[]
        self.db_calls=[]
        self.reconnections=[]
        self.previous_stop_status=previous_stop_status
        self.restore_fails=restore_fails
        self.changed_id=changed_id
        self.fail_at_db_step=fail_at_db_step
        self.previous_start_status=previous_start_status
        self.db_step=0
        self.db_rollback_count=0
        self.alias_disconnect_fails=alias_disconnect_fails
        self.alias_connect_fails=alias_connect_fails
        self.network_aliases=['cloudif-p1999-d3-web','cloudif-p1999-active-web','other-safe-alias']
        self.expected_previous='prior-container'
        self.source='cloudif-p1999-d3-web'
        self.payload={
            'project':'synthetic-demo', 'public_number':1999, 'deploy_number':3,
            'candidate_number':3,'publication_number':1,'environment_revision':1,
            'environment_variables':{},'environment_digest':'0'*64,
            'artifact_image_id':'sha256:'+'a'*64,
        }
        self.subprocess=types.SimpleNamespace(run=self.docker_run, PIPE=-1, DEVNULL=-2)
        ns={
            '_cloudif_pub_auth':lambda handler:True,
            '_cloudif_pub_json':lambda handler:self.payload,
            'safe_slug':lambda slug:slug,
            'send':lambda handler, status, body:{'http_status':status, **body},
            '_cloudif_v144_ensure_schema':lambda:None,
            'db_query':self.db_query,
            'subprocess':self.subprocess,
            'hmac':hmac,
            'json':json,
            'sqlite3':sqlite3,
            're':re,
            '_cloudif_stage_write_environment':lambda *args:'/tmp/fake-env-not-created',
            '_cloudif_v144_runtime_env_replace':lambda *args:None,
            '_cloudif_wait_health':lambda *args:{'ok':True},
            '_cloudif_v144_reconnect_active':self.reconnect,
            '_cloudif_v145_operation_gate':lambda *args:_NoopJournalForLegacyTests(),
            'init_db':lambda:None,
            '_db_connect':lambda:FakeTransactionalDb(self),
            'now':lambda:'2026-11-14T00:00:00Z',
            'normalize_resource_id':lambda value:value,
        }
        exec(HELPER_CODE,ns)
        exec(CODE,ns)
        self.release=ns['cloudif_publication_release']
        exec(ACTIVATION_CODE,ns)
        self.activate=ns['cloudif_publication_release_activate']

    def db_query(self, sql, params):
        if 'stage_production_releases' in sql:
            return [{'container':self.source, 'deploy_number':3, 'status':'ready'}]
        return [{'container':self.source, 'stack_name':'cloudif-p1999-d3',
                 'stack_id':'synthetic-stack'}]

    def docker_run(self, args, **kwargs):
        self.calls.append(tuple(args))
        if args[:3]==['docker','inspect',self.source]:
            if 'Aliases' in args[-1]:
                return FakeProcess(stdout=json.dumps(self.network_aliases))
            if '{{.State.Running}}' in args[-1]:
                return FakeProcess(stdout='true')
            if '{{.State.Status}}' in args[-1]:
                return FakeProcess(stdout=f'running|healthy|example/image|sha256:{"a"*64}|same-id-123')
            return FakeProcess(stdout=('different-id' if self.changed_id else 'same-id-123')+'|sha256:'+'a'*64)
        if args[:2]==['docker','restart']:
            return FakeProcess(stdout=self.source)
        if args[:2]==['docker','stop']:
            return FakeProcess(returncode=self.previous_stop_status)
        if args[:2]==['docker','start']:
            return FakeProcess(stdout=args[-1],returncode=self.previous_start_status)
        if args[:3]==['docker','network','disconnect']:
            if self.alias_disconnect_fails:return FakeProcess(returncode=1)
            self.network_aliases=None
            return FakeProcess()
        if args[:3]==['docker','network','connect']:
            if self.alias_connect_fails:return FakeProcess(returncode=1)
            self.network_aliases=[args[i+1] for i,x in enumerate(args) if x=='--alias']
            return FakeProcess()
        raise AssertionError('unexpected Docker operation: '+repr(args))

    def reconnect(self, public_number, target):
        self.reconnections.append(target)
        if target==self.expected_previous:
            if self.restore_fails:raise RuntimeError('synthetic restore failure')
            return self.source
        self.reconnections.append('previous-found')
        return self.expected_previous

class PromotionContractTests(unittest.TestCase):
    def test_success_reuses_same_container_and_stops_previous(self):
        fake=PromotionFixture()
        result=fake.release(object())
        self.assertEqual(result['http_status'],200)
        self.assertEqual(result['containerId'],'same-id-123')
        self.assertFalse(any(call[:2]==('docker','run') for call in fake.calls))
        self.assertIn(('docker','stop','--time','20','prior-container'),fake.calls)
        self.assertTrue(fake.db_calls)

    def test_failed_stop_does_not_claim_success_or_commit_release(self):
        fake=PromotionFixture(previous_stop_status=1)
        result=fake.release(object())
        self.assertNotEqual(result['http_status'],200)
        self.assertEqual(result.get('error'),'previous_production_stop_failed')
        self.assertFalse(fake.db_calls)
        self.assertIn(fake.expected_previous,fake.reconnections)

    def test_failed_alias_rollback_is_reported_and_uncommitted(self):
        fake=PromotionFixture(previous_stop_status=1,restore_fails=True)
        result=fake.release(object())
        self.assertNotEqual(result['http_status'],200)
        self.assertEqual(result.get('error'),'production_activation_rollback_failed')
        self.assertFalse(fake.db_calls)

    def test_manual_reactivation_succeeds_without_new_container(self):
        fake=PromotionFixture()
        result=fake.activate(object())
        self.assertEqual(result['http_status'],200)
        self.assertIn(('docker','stop','--time','20','prior-container'),fake.calls)
        self.assertTrue(fake.db_calls)
        self.assertFalse(any(cmd[:2]==('docker','run') for cmd in fake.calls))

    def test_manual_reactivation_stop_failure_rolls_back(self):
        fake=PromotionFixture(previous_stop_status=1)
        result=fake.activate(object())
        self.assertEqual(result['http_status'],422)
        self.assertEqual(result['error'],'previous_production_stop_failed')
        self.assertFalse(fake.db_calls)
        self.assertIn(fake.expected_previous,fake.reconnections)

    def test_manual_reactivation_rollback_failure_is_not_success(self):
        fake=PromotionFixture(previous_stop_status=1,restore_fails=True)
        result=fake.activate(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_activation_rollback_failed')
        self.assertFalse(fake.db_calls)

    def test_release_db_write_failure_restores_prior_runtime_for_each_step(self):
        for fail_step in (1,2,3,4):
            with self.subTest(write=fail_step):
                fake=PromotionFixture(fail_at_db_step=fail_step)
                result=fake.release(object())
                self.assertEqual(result['http_status'],503)
                self.assertEqual(result['error'],'production_db_commit_failed_rolled_back')
                self.assertEqual(fake.db_calls,[])
                self.assertEqual(fake.db_rollback_count,1)
                self.assertIn(('docker','start','prior-container'),fake.calls)
                self.assertIn('prior-container',fake.reconnections)

    def test_manual_reactivation_db_write_failure_restores_prior_runtime(self):
        for fail_step in (1,2):
            with self.subTest(write=fail_step):
                fake=PromotionFixture(fail_at_db_step=fail_step)
                result=fake.activate(object())
                self.assertEqual(result['http_status'],503)
                self.assertEqual(result['error'],'production_db_commit_failed_rolled_back')
                self.assertEqual(fake.db_calls,[])
                self.assertEqual(fake.db_rollback_count,1)
                self.assertIn(('docker','start','prior-container'),fake.calls)
                self.assertIn('prior-container',fake.reconnections)

    def test_prior_runtime_restart_failure_does_not_claim_recovery(self):
        fake=PromotionFixture(fail_at_db_step=1,previous_start_status=1)
        result=fake.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_recovery_failed')
        self.assertEqual(fake.db_calls,[])
        self.assertNotIn('prior-container',fake.reconnections)

    def test_failed_previous_alias_restore_does_not_claim_recovery(self):
        fake=PromotionFixture(fail_at_db_step=1,restore_fails=True)
        result=fake.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_recovery_failed')
        self.assertEqual(fake.db_calls,[])

    def test_changed_container_id_is_rejected(self):
        fake=PromotionFixture(changed_id=True)
        result=fake.release(object())
        self.assertEqual(result['http_status'],409)
        self.assertEqual(result['error'],'promotion_changed_container_identity')
        self.assertFalse(fake.db_calls)
        self.assertFalse(fake.reconnections, 'identity check must precede alias switch')
        self.assertFalse(any(call[:2]==('docker','stop') for call in fake.calls))


class SqliteAtomicityTests(unittest.TestCase):
    """Real SQLite rollback, in a disposable temporary database."""
    def run_atomic(self,db,statements):
        scope={'init_db':lambda:None,'_db_connect':lambda:sqlite3.connect(db)}
        exec(compile(ast.Module(body=[HELPER_NODES[0]],type_ignores=[]),str(SOURCE),'exec'),scope)
        return scope['_cloudif_v144_atomic_updates'](statements)

    def test_partial_sql_errors_roll_back_all_prior_updates(self):
        for fail_at in (0,1,2,3):
            with self.subTest(fail_at=fail_at),tempfile.TemporaryDirectory() as root:
                db=Path(root)/'state.db'
                with sqlite3.connect(db) as con:
                    con.execute('create table test_atomic_probe_rows (id integer primary key, v text)')
                    con.executemany('insert into test_atomic_probe_rows values (?,?)',[(i,'old') for i in range(1,5)])
                statements=[('update test_atomic_probe_rows set v=? where id=?',('new',i)) for i in range(1,5)]
                statements[fail_at]=('update missing_table set v=? where id=?',('new',fail_at+1))
                with self.assertRaises(sqlite3.OperationalError):
                    self.run_atomic(db,statements)
                with sqlite3.connect(db) as con:
                    self.assertEqual([x[0] for x in con.execute('select v from test_atomic_probe_rows order by id')],['old']*4)

    def test_all_updates_commit_together_if_successful(self):
        with tempfile.TemporaryDirectory() as root:
            db=Path(root)/'state.db'
            with sqlite3.connect(db) as con:
                con.execute('create table test_atomic_probe_rows (id integer primary key, v text)')
                con.executemany('insert into test_atomic_probe_rows values (?,?)',[(i,'old') for i in range(1,5)])
            self.run_atomic(db,[('update test_atomic_probe_rows set v=? where id=?',('new',i)) for i in range(1,5)])
            with sqlite3.connect(db) as con:
                self.assertEqual([x[0] for x in con.execute('select v from test_atomic_probe_rows order by id')],['new']*4)

    def test_initial_release_db_failure_retracts_only_public_alias(self):
        fake=PromotionFixture(fail_at_db_step=1)
        fake.expected_previous=''
        result=fake.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_commit_failed_rolled_back')
        self.assertFalse(fake.db_calls)
        self.assertEqual(fake.db_rollback_count,1)
        self.assertNotIn('cloudif-p1999-active-web',fake.network_aliases)
        self.assertIn('other-safe-alias',fake.network_aliases)
        self.assertIn(fake.source,fake.network_aliases)
        self.assertTrue(any(c[:3]==('docker','network','disconnect') and c[-1]==fake.source for c in fake.calls))
        self.assertFalse(any(c[:2]==('docker','stop') and c[-1]==fake.source for c in fake.calls))
        self.assertFalse(any(c[:3]==('docker','network','disconnect') and c[-1]!=fake.source for c in fake.calls))

    def test_initial_manual_activation_db_failure_retracts_public_alias(self):
        for fail_step in (1,2):
            with self.subTest(write=fail_step):
                fake=PromotionFixture(fail_at_db_step=fail_step)
                fake.expected_previous=''
                result=fake.activate(object())
                self.assertEqual(result['http_status'],503)
                self.assertEqual(result['error'],'production_db_commit_failed_rolled_back')
                self.assertEqual(fake.db_rollback_count,1)
                self.assertEqual(fake.db_calls,[])
                self.assertNotIn('cloudif-p1999-active-web',fake.network_aliases)
                self.assertIn('other-safe-alias',fake.network_aliases)
                self.assertIn(fake.source,fake.network_aliases)
                self.assertFalse(any(cmd[:2]==('docker','stop') and cmd[-1]==fake.source for cmd in fake.calls))
                self.assertFalse(any(cmd[:3]==('docker','network','disconnect')
                                     and cmd[-1]!=fake.source for cmd in fake.calls))

    def test_initial_manual_activation_cleanup_error_never_claims_recovery(self):
        fake=PromotionFixture(fail_at_db_step=2,alias_connect_fails=True)
        fake.expected_previous=''
        result=fake.activate(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_recovery_failed')
        self.assertFalse(fake.db_calls)
        self.assertEqual(fake.db_rollback_count,1)

    def test_initial_release_cleanup_errors_never_claim_success(self):
        for phase in ('disconnect','connect'):
            with self.subTest(phase=phase):
                fake=PromotionFixture(fail_at_db_step=1,
                    alias_disconnect_fails=phase=='disconnect',alias_connect_fails=phase=='connect')
                fake.expected_previous=''
                result=fake.release(object())
                self.assertEqual(result['http_status'],503)
                self.assertEqual(result['error'],'production_db_recovery_failed')
                self.assertFalse(fake.db_calls)

    def test_initial_release_already_unpublished_requires_no_network_change(self):
        fake=PromotionFixture(fail_at_db_step=1)
        fake.expected_previous=''
        fake.network_aliases=['cloudif-p1999-d3-web','other-safe-alias']
        result=fake.release(object())
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_commit_failed_rolled_back')
        self.assertFalse(any(c[:3]==('docker','network','disconnect') for c in fake.calls))

    def test_initial_alias_cleanup_rejects_invalid_target(self):
        fake=PromotionFixture(fail_at_db_step=1)
        fake.expected_previous=''
        fake.source='untrusted-container-name'
        result=fake.release(object())
        # Invalid name never triggers network reconfiguration.
        self.assertEqual(result['http_status'],503)
        self.assertEqual(result['error'],'production_db_recovery_failed')
        self.assertFalse(any(c[:3]==('docker','network','disconnect') for c in fake.calls))

if __name__=='__main__':unittest.main()
