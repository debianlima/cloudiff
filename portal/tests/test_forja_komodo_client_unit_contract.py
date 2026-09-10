from pathlib import Path
import importlib.util
import time
import unittest


class ForjaKomodoClientUnitContractTest(unittest.TestCase):
    def test_forja_service_uses_dedicated_komodo_client_environment(self):
        source=Path('components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/komodo-client.conf').read_text(encoding='utf-8')
        self.assertIn('EnvironmentFile=-/etc/cloudif/forja-komodo-client.env',source)
        self.assertNotIn('TOKEN=',source)

    def test_portal_integration_status_probes_run_in_parallel(self):
        path=Path('components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py')
        spec=importlib.util.spec_from_file_location('cloudif_git_komodo_parallel_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.agent_urls=lambda:{
            'forja_url':'http://forja.invalid','forja_token':'',
            'komodo_url':'http://komodo.invalid','komodo_token':'',
        }
        calls=[]
        def fake_http(url,method='GET',payload=None,token='',timeout=7):
            calls.append((url,timeout));time.sleep(.12);return {'ok':False,'status':0,'data':{}}
        module.http_json=fake_http
        started=time.perf_counter()
        snapshot=module.integration_status_snapshot()
        elapsed=time.perf_counter()-started
        self.assertLess(elapsed,.30)
        self.assertEqual(len(calls),4)
        self.assertEqual(set(snapshot),{'forja_health','forja_status','komodo_health','komodo_status'})


if __name__=='__main__':
    unittest.main()
