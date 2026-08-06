from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BROKER=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'


def load_broker(root:Path):
    os.environ['CLOUDIF_BUILD_DB']=str(root/'builds.db')
    os.environ['CLOUDIF_TOOLCHAIN_CATALOG']=str(ROOT/'components/control-plane/etc/cloudif/toolchain-catalog-v1.json')
    name='runtime_config_contract_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,BROKER);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);module.init_db();return module


class MultiserviceRuntimeConfigContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_broker(Path(self.temp.name));self.job='build_'+'1'*24
        payload={
          'job_id':self.job,'project_slug':'demo','environment':'preview','config_revision':4,'config_digest':'c'*64,
          'toolchain_digest':'t'*64,'archive_sha256':'a'*64,'plan_digest':'p'*64,
          'services':[{'name':'api'},{'name':'web'}],
          'activeToolchainImages':{'api':{'imageRecordId':'img_'+'2'*24}},
          'effectiveEnvironment':{
            'projectSlug':'demo','environment':'preview','revision':4,
            'publicBuildEnvironment':{'api':{'PUBLIC_VERSION':'42'},'web':{}},
            'publicRuntimeEnvironment':{'api':{'LOG_LEVEL':'info'},'web':{'PUBLIC_API_URL':'https://api.example.test'}},
            'secretBuildReferences':{'api':{},'web':{}},
            'secretRuntimeReferences':{'api':{'DATABASE_URL':'vault://project/demo/database-preview'},'web':{}},
            'missingRequired':[],'buildEnvironmentDigest':'1'*64,'runtimeEnvironmentDigest':'2'*64,'environmentDigest':'3'*64,
            'secretValuesIncluded':False,
          },
        }
        result={'ok':True,'services':[{'service':'api','image':{'image':'cloudif-app/demo-api:1','imageId':'sha256:'+'4'*64}},{'service':'web','image':{'image':'cloudif-app/demo-web:1','imageId':'sha256:'+'5'*64}}]}
        timestamp=int(time.time());c=self.module.db()
        c.execute('insert into multiservice_jobs(job_id,idempotency_key,project_slug,ref,config_revision,config_digest,toolchain_digest,archive_sha256,plan_digest,status,payload_json,result_json,log_text,created_at,updated_at,attempts,last_error) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(self.job,'key','demo','main',4,'c'*64,'t'*64,'a'*64,'p'*64,'succeeded',json.dumps(payload),json.dumps(result),'done\n',timestamp,timestamp,1,''));c.commit();c.close()

    def tearDown(self):self.temp.cleanup()

    def test_runtime_config_is_bound_to_completed_build(self):
        result=self.module.multiservice_runtime_config(self.job)
        self.assertTrue(result['ok']);self.assertTrue(result['internal'])
        self.assertEqual(result['project_slug'],'demo');self.assertEqual(result['environment'],'preview')
        self.assertEqual(result['config_revision'],4);self.assertEqual(result['environmentDigest'],'3'*64)
        self.assertEqual(result['publicRuntimeEnvironment']['api']['LOG_LEVEL'],'info')
        self.assertEqual(result['secretRuntimeReferences']['api']['DATABASE_URL'],'vault://project/demo/database-preview')
        self.assertEqual(len(result['serviceArtifacts']),2)
        self.assertFalse(result['secretValuesIncluded']);self.assertTrue(result['secretReferencesIncluded'])
        self.assertFalse(result['containersChanged'])

    def test_public_response_does_not_include_build_values_or_raw_payload(self):
        result=self.module.multiservice_runtime_config(self.job)
        serialized=json.dumps(result)
        self.assertNotIn('PUBLIC_VERSION',serialized)
        self.assertNotIn('publicBuildEnvironment',serialized)
        self.assertNotIn('payload_json',serialized)
        self.assertNotIn('password',serialized.lower())

    def test_non_succeeded_and_invalid_jobs_are_rejected(self):
        c=self.module.db();c.execute("update multiservice_jobs set status='running' where job_id=?",(self.job,));c.commit();c.close()
        with self.assertRaisesRegex(ValueError,'multiservice_build_not_ready'):
            self.module.multiservice_runtime_config(self.job)
        with self.assertRaisesRegex(ValueError,'invalid_build_job_id'):
            self.module.multiservice_runtime_config('bad')

    def test_secret_contract_and_reference_format_fail_closed(self):
        c=self.module.db();row=c.execute('select payload_json from multiservice_jobs where job_id=?',(self.job,)).fetchone();payload=json.loads(row[0]);payload['effectiveEnvironment']['secretValuesIncluded']=True;c.execute("update multiservice_jobs set status='succeeded',payload_json=? where job_id=?",(json.dumps(payload),self.job));c.commit();c.close()
        with self.assertRaisesRegex(ValueError,'effective_environment_secret_contract_invalid'):
            self.module.multiservice_runtime_config(self.job)

    def test_route_is_internal_and_not_published_as_mcp_tool(self):
        source=BROKER.read_text();self.assertIn('/runtime-config',source)
        gateway=(ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
        self.assertNotIn('runtime-config',gateway)


if __name__=='__main__':unittest.main()
