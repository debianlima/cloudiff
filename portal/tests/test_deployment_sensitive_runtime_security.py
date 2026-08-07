from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
BROKER=ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py'
EXECUTOR=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-deployment-broker.service'
KOMODO=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
KOMODO_UNIT=ROOT/'components/runtime/etc/systemd/system/cloudif-komodo-agent.service'
RECONCILER=ROOT/'components/control-plane/current-apps/project-runtime-reconciler-current/cloudif-project-runtime-reconciler.py'


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);return module


class DeploymentSecretInjectionSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker=load(BROKER,'deployment_secret_broker_test');cls.executor=load(EXECUTOR,'deployment_secret_executor_test')

    def test_internal_resolver_requires_second_token_and_exact_scope(self):
        refs={'api':{'DATABASE_URL':'cloudiff-secret://demo/homologation/api/DATABASE_URL/v1'}}
        old=self.broker.SECRET_RESOLVER_TOKEN;self.broker.SECRET_RESOLVER_TOKEN='resolver-token';captured={}
        def fake_urlopen(request,timeout=30):
            captured['headers']={k.lower():v for k,v in request.header_items()};captured['body']=json.loads(request.data)
            return io.BytesIO(json.dumps({'ok':True,'internal':True,'resolvedSecrets':{'api':{'DATABASE_URL':'runtime-only-secret'}},'count':1,'secretValuesIncluded':True}).encode())
        try:
            with patch.object(self.broker.urllib.request,'urlopen',side_effect=fake_urlopen):result=self.broker._resolve_runtime_secrets('demo','homologation',refs)
        finally:self.broker.SECRET_RESOLVER_TOKEN=old
        self.assertEqual(result['api']['DATABASE_URL'],'runtime-only-secret')
        self.assertEqual(captured['body']['references'],refs);self.assertEqual(captured['body']['environment'],'homologation')
        self.assertEqual(captured['headers'].get('x-cloudif-secret-resolver-token'),'resolver-token')
        self.assertIn('authorization',captured['headers'])

    def test_resolver_fails_closed_without_second_token(self):
        old=self.broker.SECRET_RESOLVER_TOKEN;self.broker.SECRET_RESOLVER_TOKEN=''
        try:
            with self.assertRaisesRegex(RuntimeError,'secret_resolver_unavailable'):
                self.broker._resolve_runtime_secrets('demo','production',{'api':{'JWT_SECRET':'cloudiff-secret://demo/production/api/JWT_SECRET/v1'}})
        finally:self.broker.SECRET_RESOLVER_TOKEN=old

    def test_docker_secret_value_is_removed_from_argv_before_subprocess(self):
        captured={}
        class Completed:
            returncode=0;stdout='ok';stderr=''
        def fake_run(command,*args,**kwargs):
            captured['command']=list(command);captured['env']=dict(kwargs.get('env') or {});return Completed()
        command=['docker','run','--rm','--env','DATABASE_URL=runtime-only-secret','--env','LOG_LEVEL=info','image:test']
        with patch.object(self.executor.subprocess,'run',side_effect=fake_run):self.executor.run(command,timeout=2)
        rendered=json.dumps(captured['command'])
        self.assertNotIn('runtime-only-secret',rendered);self.assertNotIn('LOG_LEVEL=info',rendered)
        self.assertIn('DATABASE_URL',captured['command']);self.assertIn('LOG_LEVEL',captured['command'])
        self.assertEqual(captured['env']['DATABASE_URL'],'runtime-only-secret');self.assertEqual(captured['env']['LOG_LEVEL'],'info')
        self.assertNotIn('runtime-only-secret',json.dumps(command))

    def test_executor_does_not_persist_runtime_configuration_payload(self):
        source=EXECUTOR.read_text();start=source.index('def create_deployment(');end=source.index('\ndef ',start+5);block=source[start:end]
        self.assertNotIn('json.dumps(payload)',block);self.assertNotIn('payload_json',block);self.assertNotIn('runtimeConfiguration',block)

    def test_mcp_has_no_internal_resolver_and_raw_read_is_controlled(self):
        source=GATEWAY.read_text();self.assertNotIn("'name':'project.environment.secret.resolve",source);self.assertNotIn("'name':'project.environment.secret.read','description'",source)
        for name in ('project.environment.secret.read.plan','approval.request-secret-read','project.environment.secret.read.execute'):self.assertIn("'name':'"+name+"'",source)

    def test_deployment_service_loads_protected_resolver_environment(self):
        unit=UNIT.read_text();self.assertIn('EnvironmentFile=/etc/cloudif/project-config-controller.env',unit)

    def test_cross_segment_executor_gateway_is_narrow_and_token_bound(self):
        source=KOMODO.read_text();unit=KOMODO_UNIT.read_text();broker=BROKER.read_text();reconciler=RECONCILER.read_text()
        self.assertIn("_EXECUTOR_PROXY_PREFIX='/cloudif/executor'",source)
        self.assertIn("re.fullmatch(r'/cloudif/executor/v1/deployments/(dep_[a-f0-9]{24})'",source)
        self.assertIn("re.fullmatch(r'/cloudif/executor/v1/projects/([a-z0-9][a-z0-9-]{0,62})/runtime-state'",source)
        self.assertIn("path==_EXECUTOR_PROXY_PREFIX+'/v1/deployments'",source)
        self.assertIn("hmac.compare_digest(expected,supplied)",source)
        self.assertIn("CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN",source)
        self.assertIn("executor_proxy_secret_contract_invalid",source)
        self.assertIn('EnvironmentFile=/etc/cloudif/multiservice-deployment-executor.env',unit)
        self.assertIn('http://10.62.91.2:18098/cloudif/executor',broker)
        self.assertIn('http://10.62.91.2:18098/cloudif/executor',reconciler)


if __name__=='__main__':unittest.main()
