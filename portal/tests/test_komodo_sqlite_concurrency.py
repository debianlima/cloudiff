import ast
import concurrent.futures
import pathlib
import tempfile
import threading
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
KOMODO=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'


def load_db_namespace(tmpdir):
    source=KOMODO.read_text()
    prefix=source[:source.index('def load_env():')]
    prefix=prefix.replace('BASE_STATE = pathlib.Path("/var/lib/cloudif/komodo-agent")', f'BASE_STATE = pathlib.Path({str(tmpdir)!r})')
    ns={'__name__':'cloudif_komodo_concurrency_test'}
    exec(compile(prefix,str(KOMODO),'exec'),ns)
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_cloudif_v143_ensure_schema')
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(KOMODO),'exec'),ns)
    return ns


class KomodoSqliteConcurrencyTests(unittest.TestCase):
    def test_contract_uses_wal_busy_timeout_and_process_schema_lock(self):
        source=KOMODO.read_text()
        self.assertIn('_DB_SCHEMA_LOCK = threading.RLock()',source)
        self.assertIn('sqlite3.connect(DB_PATH, timeout=30.0)',source)
        self.assertIn('pragma busy_timeout=30000',source)
        self.assertIn('pragma journal_mode=WAL',source)
        self.assertIn('if _DB_SCHEMA_READY:',source)
        self.assertIn('if _V143_SCHEMA_READY:',source)

    def test_parallel_reads_writes_and_schema_initialization_do_not_lock(self):
        with tempfile.TemporaryDirectory() as td:
            ns=load_db_namespace(pathlib.Path(td))
            barrier=threading.Barrier(16)
            errors=[]
            def worker(i):
                try:
                    barrier.wait(timeout=10)
                    ns['_cloudif_v143_ensure_schema']()
                    for j in range(15):
                        ns['db_exec'](
                            'insert into deployments(created_at,project,tenant,actor,action,status,message) values(?,?,?,?,?,?,?)',
                            (f't{i}-{j}',f'p{i}',f'tenant{i}',f'u{i}','qa','ok','concurrency'),
                        )
                        rows=ns['db_query']('select count(*) as n from deployments')
                        self.assertGreaterEqual(rows[0]['n'],1)
                except Exception as exc:
                    errors.append(exc)
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
                list(ex.map(worker,range(16)))
            if errors:
                self.fail(f'parallel sqlite operations failed: {errors!r}')
            rows=ns['db_query']('select count(*) as n from deployments')
            self.assertEqual(rows[0]['n'],16*15)


if __name__=='__main__': unittest.main()
