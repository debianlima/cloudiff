import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / 'components/control-plane/current-apps/supabase-mcp-broker-current/cloudif-supabase-mcp-broker.py'


def load_broker():
    fake = types.ModuleType('psycopg2')
    fake.sql = types.SimpleNamespace()
    sys.modules.setdefault('psycopg2', fake)
    sys.modules.setdefault('psycopg2.sql', types.ModuleType('psycopg2.sql'))
    sys.modules.setdefault('requests', types.ModuleType('requests'))
    spec = importlib.util.spec_from_file_location('cloudif_supabase_mcp_broker_test', BROKER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class SupabaseMcpExecutionStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.broker = load_broker()
        self.broker.STATE_DB = Path(self.tmp.name) / 'executions.db'
        self.broker.init_state()
        self.ctx = {'slug': 'demo'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_execution_begin_does_not_self_deadlock(self):
        execution_id = 'exec_' + 'a' * 32
        result = self.broker.execution_begin(execution_id, self.ctx, 'records.change', 'b' * 64)
        self.assertIsNone(result)
        con = sqlite3.connect(self.broker.STATE_DB)
        row = con.execute(
            'select status,project_slug,operation,digest from executions where execution_id=?',
            (execution_id,),
        ).fetchone()
        con.close()
        self.assertEqual(row, ('running', 'demo', 'records.change', 'b' * 64))

    def test_successful_execution_is_idempotent_for_non_secret_operation(self):
        execution_id = 'exec_' + 'c' * 32
        self.broker.execution_begin(execution_id, self.ctx, 'records.change', 'd' * 64)
        self.broker.execution_finish(execution_id, {'ok': True, 'operation': 'records.change'}, True)
        result = self.broker.execution_begin(execution_id, self.ctx, 'records.change', 'd' * 64)
        self.assertTrue(result['ok'])
        self.assertEqual(result['operation'], 'records.change')


if __name__ == '__main__':
    unittest.main()
