from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
UNIT=ROOT/'components/runtime/etc/systemd/system/cloudif-multiservice-deployment-executor.service'


def load_module():
    spec=importlib.util.spec_from_file_location('multiservice_deployment_executor_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module);return module


class MultiserviceDeploymentExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.module=load_module();self.module.DB_PATH=root/'deployments.db';self.module.RUN_DIR=root/'run';self.module.init_db()

    def tearDown(self):self.temp.cleanup()

    def payload(self):
        variables={'web':{'PUBLIC_MODE':'school'},'api':{'DATABASE_URL':'postgres://internal'}}
        return {
            'deployment_id':'dep_'+'a'*24,'project_slug':'demo','environment':'homologation',
            'build_job_id':'build_'+'b'*24,'deployment_plan_digest':'d'*64,
            'build_plan_digest':'e'*64,'config_revision':2,'config_digest':'c'*64,
            'toolchain_digest':'a'*64,'archive_sha256':'f'*64,
            'applications':[
                {'service':'web','image_id':'sha256:'+'1'*64,'application_digest':'2'*64,'port':8080,'healthcheck':'/__cloudif_health'},
                {'service':'api','image_id':'sha256:'+'3'*64,'application_digest':'4'*64,'port':3000,'healthcheck':'/health'},
            ],
            'routes':[{'pathPrefix':'/api','service':'api','stripPrefix':False},{'pathPrefix':'/','service':'web','stripPrefix':False}],
            'variables':variables,
            'variables_digest':hashlib.sha256(self.module.canonical(variables)).hexdigest(),
        }

    def image(self,service,digest,image_id):
        return {'Id':image_id,'Config':{'User':'65532:65532','Labels':{
            'org.cloudiff.kind':'application','org.cloudiff.project':'demo','org.cloudiff.service':service,
            'org.cloudiff.config-revision':'2','org.cloudiff.config-digest':'c'*64,
            'org.cloudiff.toolchain-digest':'a'*64,'org.cloudiff.archive-sha256':'f'*64,'org.cloudiff.application-digest':digest,
        }}}

    def test_normalization_binds_variable_values_by_digest(self):
        normalized=self.module.normalize_payload(self.payload())
        self.assertEqual(normalized['variables']['api']['DATABASE_URL'],'postgres://internal')
        changed=self.payload();changed['variables']['api']['DATABASE_URL']='changed'
        with self.assertRaisesRegex(self.module.DeploymentError,'variables_digest_mismatch'):
            self.module.normalize_payload(changed)

    def test_newline_and_invalid_variable_name_are_rejected(self):
        for name,value in [('BAD-NAME','x'),('GOOD_NAME','a\nb')]:
            payload=self.payload();payload['variables']['api']={name:value};payload['variables_digest']=hashlib.sha256(self.module.canonical(payload['variables'])).hexdigest()
            with self.subTest(name=name):
                with self.assertRaises(self.module.DeploymentError):self.module.normalize_payload(payload)

    def test_create_uses_hardened_containers_and_does_not_persist_values(self):
        calls=[]
        images={
            'sha256:'+'1'*64:self.image('web','2'*64,'sha256:'+'1'*64),
            'sha256:'+'3'*64:self.image('api','4'*64,'sha256:'+'3'*64),
        }
        ports={'web':41001,'api':41002}
        def fake_docker(*args,timeout=90,check=True):
            calls.append(args)
            if args[:2]==('image','inspect'):
                return subprocess.CompletedProcess(args,0,json.dumps([images[args[2]]]),'')
            if args and args[0]=='run':
                service='web' if args[-1]=='sha256:'+'1'*64 else 'api'
                return subprocess.CompletedProcess(args,0,'container-'+service+'\n','')
            if args and args[0]=='inspect':
                service='web' if args[1].endswith('-web') else 'api';port=8080 if service=='web' else 3000
                data=[{'NetworkSettings':{'Ports':{f'{port}/tcp':[{'HostIp':'127.0.0.1','HostPort':str(ports[service])}]}}}]
                return subprocess.CompletedProcess(args,0,json.dumps(data),'')
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(self.module,'docker',side_effect=fake_docker),patch.object(self.module,'probe',return_value={'ok':True,'status':200}):
            result=self.module.create_deployment(self.payload())
        self.assertTrue(result['ok']);self.assertEqual(result['status'],'running')
        self.assertFalse(result['variable_values_returned']);self.assertFalse(result['secrets_persisted'])
        rendered=json.dumps(result)
        self.assertNotIn('postgres://internal',rendered);self.assertNotIn('school',rendered)
        run_calls=[list(call) for call in calls if call and call[0]=='run']
        self.assertEqual(len(run_calls),2)
        for command in run_calls:
            for marker in ('--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','unless-stopped','--env-file'):
                self.assertIn(marker,command)
            self.assertTrue(any(str(x).startswith('127.0.0.1::') for x in command))
        con=self.module.db();row=con.execute('select services_json,error_json from deployments').fetchone();con.close()
        persisted=' '.join(row)
        self.assertNotIn('postgres://internal',persisted);self.assertNotIn('school',persisted)
        self.assertEqual(list(self.module.RUN_DIR.glob('*.env')),[])

    def test_image_toolchain_digest_mismatch_is_blocked(self):
        payload=self.module.normalize_payload(self.payload())
        image=self.image('web','2'*64,'sha256:'+'1'*64)
        image['Config']['Labels']['org.cloudiff.toolchain-digest']='9'*64
        with patch.object(self.module,'inspect_image',return_value=image):
            with self.assertRaisesRegex(self.module.DeploymentError,'image_label_mismatch'):
                self.module.validate_image_labels(payload,payload['applications'][0])

    def test_image_config_digest_mismatch_is_blocked(self):
        payload=self.module.normalize_payload(self.payload())
        image=self.image('web','2'*64,'sha256:'+'1'*64)
        image['Config']['Labels']['org.cloudiff.config-digest']='x'*64
        with patch.object(self.module,'inspect_image',return_value=image):
            with self.assertRaisesRegex(self.module.DeploymentError,'image_label_mismatch'):
                self.module.validate_image_labels(payload,payload['applications'][0])

    def test_status_never_returns_environment_values(self):
        con=self.module.db();con.execute('insert into deployments values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            'dep_'+'a'*24,'demo','homologation','build_'+'b'*24,'d'*64,'e'*64,2,'c'*64,'t'*64,'f'*64,'a'*64,
            'failed','[]','[]','{}',1,1));con.commit();con.close()
        status=self.module.status_deployment('dep_'+'a'*24)
        self.assertFalse(status['variable_values_returned']);self.assertFalse(status['secrets_persisted'])
        self.assertNotIn('variables',status)

    def test_service_unit_is_local_restricted_and_docker_hardened(self):
        unit=UNIT.read_text()
        for marker in ('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_HOST=10.62.91.2','CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_PORT=18230','ReadWritePaths=/var/lib/cloudif/multiservice-deployment-executor /run/cloudif-multiservice-deployment /var/run/docker.sock','IPAddressAllow=10.62.92.7/32','IPAddressAllow=10.62.91.2/32','IPAddressDeny=any','NoNewPrivileges=true','CapabilityBoundingSet='):
            self.assertIn(marker,unit)


if __name__=='__main__':unittest.main()
