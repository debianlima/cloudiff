from __future__ import annotations

import importlib.util
import os
import ssl
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'

def load_module():
    fake=types.ModuleType('cloudif_publication_permissions')
    fake.is_admin=lambda user:False
    fake.is_professor=lambda user:False
    fake.ensure_schema=lambda con:None
    previous=sys.modules.get('cloudif_publication_permissions')
    sys.modules['cloudif_publication_permissions']=fake
    try:
        spec=importlib.util.spec_from_file_location('publication_https_retry_test',MODULE)
        module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:sys.modules.pop('cloudif_publication_permissions',None)
        else:sys.modules['cloudif_publication_permissions']=previous

class Response:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n=-1):return b'healthy'

class PublicationHttpsReadinessRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.module=load_module()

    def test_transient_tls_failure_retries_with_strict_default_context(self):
        m=self.module
        failure=m.urllib.error.URLError(ssl.SSLCertVerificationError(1,'hostname mismatch'))
        sentinel=object()
        with mock.patch.dict(os.environ,{'CLOUDIF_PUBLICATION_HTTPS_READY_ATTEMPTS':'2','CLOUDIF_PUBLICATION_HTTPS_READY_INTERVAL':'0'}), \
             mock.patch.object(m.ssl,'create_default_context',return_value=sentinel) as context, \
             mock.patch.object(m.urllib.request,'urlopen',side_effect=[failure,Response()]) as urlopen, \
             mock.patch.object(m.time,'sleep') as sleep:
            self.assertTrue(m._external_ok('1001-h12-homologation.cloudiff.duckdns.org'))
        self.assertEqual(urlopen.call_count,2)
        self.assertEqual(context.call_count,2)
        self.assertTrue(all(call.kwargs.get('context') is sentinel for call in urlopen.call_args_list))
        sleep.assert_not_called()

    def test_exhaustion_returns_false_without_insecure_tls(self):
        m=self.module
        failure=m.urllib.error.URLError(ssl.SSLCertVerificationError(1,'hostname mismatch'))
        with mock.patch.dict(os.environ,{'CLOUDIF_PUBLICATION_HTTPS_READY_ATTEMPTS':'2','CLOUDIF_PUBLICATION_HTTPS_READY_INTERVAL':'0'}), \
             mock.patch.object(m.urllib.request,'urlopen',side_effect=[failure,failure]), \
             mock.patch.object(m.ssl,'create_default_context',wraps=ssl.create_default_context):
            self.assertFalse(m._external_ok('example.invalid'))
        source=MODULE.read_text()
        self.assertNotIn('CERT_NONE',source)
        self.assertNotIn('check_hostname=False',source)
        self.assertIn("CLOUDIF_PUBLICATION_HTTPS_READY_ATTEMPTS",source)

if __name__=='__main__':unittest.main()
