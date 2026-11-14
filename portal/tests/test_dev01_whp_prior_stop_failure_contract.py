"""Isolated W1/Hn/Pn promotion contract with fake Docker and fake storage.

Executes only the final (runtime-effective) function definition from AST.
No shell, network, credentials, containers, production DB or live access.
"""
import ast
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

class FakeProcess:
    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

class PromotionFixture:
    def __init__(self, previous_stop_status=0, restore_fails=False, changed_id=False):
        self.calls=[]
        self.db_calls=[]
        self.reconnections=[]
        self.previous_stop_status=previous_stop_status
        self.restore_fails=restore_fails
        self.changed_id=changed_id
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
            '_cloudif_stage_write_environment':lambda *args:'/tmp/fake-env-not-created',
            '_cloudif_v144_runtime_env_replace':lambda *args:None,
            '_cloudif_wait_health':lambda *args:{'ok':True},
            '_cloudif_v144_reconnect_active':self.reconnect,
            'db_exec':lambda *args:self.db_calls.append(args),
            'now':lambda:'2026-11-14T00:00:00Z',
            'normalize_resource_id':lambda value:value,
        }
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
            if '{{.State.Running}}' in args[-1]:
                return FakeProcess(stdout='true')
            if '{{.State.Status}}' in args[-1]:
                return FakeProcess(stdout=f'running|healthy|example/image|sha256:{"a"*64}|same-id-123')
            return FakeProcess(stdout=('different-id' if self.changed_id else 'same-id-123')+'|sha256:'+'a'*64)
        if args[:2]==['docker','restart']:
            return FakeProcess(stdout=self.source)
        if args[:2]==['docker','stop']:
            return FakeProcess(returncode=self.previous_stop_status)
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

    def test_changed_container_id_is_rejected(self):
        fake=PromotionFixture(changed_id=True)
        result=fake.release(object())
        self.assertEqual(result['http_status'],409)
        self.assertEqual(result['error'],'promotion_changed_container_identity')
        self.assertFalse(fake.db_calls)
        self.assertFalse(fake.reconnections, 'identity check must precede alias switch')
        self.assertFalse(any(call[:2]==('docker','stop') for call in fake.calls))

if __name__=='__main__':unittest.main()
