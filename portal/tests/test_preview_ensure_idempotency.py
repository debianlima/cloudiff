from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import importlib.util
import tempfile
import threading
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'
if str(LIB) not in sys.path: sys.path.insert(0,str(LIB))
BACKEND=LIB/'cloudif_portal_publications.py'


def load_backend(name='preview_ensure_backend'):
    spec=importlib.util.spec_from_file_location(name,BACKEND)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


class FakeConnection:
    row_factory=None
    def close(self): pass


class PreviewEnsureIdempotencyTests(unittest.TestCase):
    def test_lock_reports_real_contention_and_serializes(self):
        module=load_backend('preview_lock_test')
        with tempfile.TemporaryDirectory() as d:
            module.PREVIEW_ENSURE_LOCK_ROOT=Path(d)
            entered=threading.Event();release=threading.Event();results=[]
            def first():
                with module._preview_ensure_lock('projeto-teste') as contended:
                    results.append(('first',contended,time.monotonic()))
                    entered.set();release.wait(2)
            def second():
                entered.wait(2);started=time.monotonic()
                with module._preview_ensure_lock('projeto-teste') as contended:
                    results.append(('second',contended,time.monotonic()-started))
            a=threading.Thread(target=first);b=threading.Thread(target=second)
            a.start();b.start();entered.wait(2);time.sleep(0.12);release.set();a.join(2);b.join(2)
            self.assertEqual(results[0][0:2],('first',False))
            self.assertEqual(results[1][0:2],('second',True))
            self.assertGreaterEqual(results[1][2],0.10)

    def test_contended_healthy_preview_returns_without_redeploy(self):
        module=load_backend('preview_dedupe_test')
        @contextmanager
        def contended(_slug): yield True
        healthy={'ok':True,'configured':True,'healthy':True,'stageCode':'W1'}
        with patch.object(module.sqlite3,'connect',return_value=FakeConnection()), \
             patch.object(module,'_ensure_schema'), \
             patch.object(module,'_project_allowed',return_value={'slug':'demo'}), \
             patch.object(module,'_number',return_value=1011), \
             patch.object(module,'_preview_ensure_lock',contended), \
             patch.object(module,'preview_status',return_value=healthy.copy()), \
             patch.object(module,'_is_linked_compose_project',side_effect=AssertionError('must not redeploy')):
            result=module.ensure_preview('demo',{'username':'tester'})
        self.assertTrue(result['healthy'])
        self.assertTrue(result['deduplicated'])


if __name__=='__main__': unittest.main()
