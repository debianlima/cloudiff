from __future__ import annotations

import importlib.util
import json
import os
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
    name='toolchain_lifecycle_broker_test_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,BROKER);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);module.init_db();return module


class ToolchainLifecycleBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_broker(Path(self.temp.name));self.lifecycle=self.module.toolchain_lifecycle
        self.module.project_configuration=lambda slug:{
          'ok':True,'projectSlug':slug,'currentRevision':4,'configDigest':'b'*64,'toolchainDigest':'c'*64,
          'configuration':{
            'project':{'type':'multi-service','primaryService':'api'},
            'toolchain':{'architecture':'amd64','systemPackages':['git'],'tools':[{'name':'node','version':'24','installMethod':'catalog'}]},
            'services':{
              'web':{'path':'public','runtime':'static','publish':'.'},
              'api':{'path':'api','runtime':'node','version':'24','start':['node','server.js'],'port':3000},
            },
          },
        }
        self.module.source_detection=lambda slug,ref,trace:{'archiveSha256':'a'*64,'projectType':'multi-service','componentCount':2}
        self.original_artifact=self.lifecycle._artifact

    def tearDown(self):
        self.lifecycle._artifact=self.original_artifact;self.temp.cleanup()

    def payload(self):
        return {'project_slug':'demo','ref':'main','expected_revision':4,'trace_id':'test'}

    def test_plan_is_side_effect_free_and_digest_bound(self):
        plan=self.lifecycle.plan(self.payload())
        self.assertTrue(plan['ok']);self.assertTrue(plan['side_effect_free'])
        self.assertEqual(plan['config_revision'],4);self.assertEqual(plan['archive_sha256'],'a'*64)
        self.assertEqual(len(plan['plan_digest']),64);self.assertEqual(plan['images_created'],0)
        self.assertFalse(plan['containers_changed']);self.assertFalse(plan['secret_values_included'])
        c=self.module.db();self.assertEqual(c.execute('select count(*) from toolchain_jobs').fetchone()[0],0);c.close()

    def test_validate_calls_archive_validator_without_creating_images(self):
        def artifact(path,request,timeout):
            self.assertEqual(path,'/v1/toolchain/validate');self.assertTrue(request['job_id'].startswith('toolchain_'))
            return {'ok':True,'valid':True,'blockers':[],'warnings':[],'imagesCreated':0,'containersChanged':False,'secretValuesIncluded':False}
        self.lifecycle._artifact=artifact
        result=self.lifecycle.validate(self.payload())
        self.assertTrue(result['valid']);self.assertEqual(result['images_created'],0)
        c=self.module.db();self.assertEqual(c.execute('select count(*) from toolchain_images').fetchone()[0],0);c.close()

    def test_build_queue_is_idempotent_and_registers_ready_images(self):
        def artifact(path,request,timeout):
            if path=='/v1/toolchain/validate':return {'ok':True,'valid':True,'blockers':[],'warnings':[],'imagesCreated':0}
            self.assertEqual(path,'/v1/toolchain/build')
            toolchains=[]
            for service in request['services']:
                effective=('1' if service['name']=='api' else '2')*64
                toolchains.append({'service':service['name'],'effectiveToolchainDigest':effective,'image':{'image':f"cloudif-toolchain/demo-{service['name']}:{effective[:16]}",'imageId':'sha256:'+effective},'sbomReady':True,'sbomSha256':'3'*64,'scannerBlocked':False,'scannerCounts':{},'signatureVerified':True,'secretValuesIncluded':False})
            return {'ok':True,'status':'ready','toolchains':toolchains,'secretValuesIncluded':False}
        self.lifecycle._artifact=artifact
        plan=self.lifecycle.plan(self.payload())
        with self.assertRaisesRegex(PermissionError,'approval_required'):
            self.lifecycle.queue({**self.payload(),'plan_digest':plan['plan_digest'],'approved':False})
        first=self.lifecycle.queue({**self.payload(),'plan_digest':plan['plan_digest'],'approved':True})
        deadline=time.time()+5
        while time.time()<deadline:
            status=self.lifecycle.status(first['job_id'])
            if status['status'] in {'succeeded','failed'}:break
            time.sleep(.02)
        self.assertEqual(status['status'],'succeeded',status)
        second=self.lifecycle.queue({**self.payload(),'plan_digest':plan['plan_digest'],'approved':True})
        self.assertTrue(second['idempotent']);self.assertEqual(second['job_id'],first['job_id'])
        images=self.lifecycle.images('demo')
        self.assertEqual(images['count'],2)
        self.assertTrue(all(item['status']=='ready' for item in images['images']))
        self.assertFalse(images['secret_values_included'])

    def _seed_succeeded_job(self):
        c=self.module.db();timestamp=int(time.time());job_id='toolchain_'+'1'*24
        records=[]
        for service,digit in [('api','1'*64),('web','2'*64)]:
            record='img_'+hashlib_sha(service)[:24]
            result={'service':service,'effectiveToolchainDigest':digit,'image':{'image':f'cloudif-toolchain/demo-{service}:{digit[:16]}','imageId':'sha256:'+digit},'sbomReady':True,'scannerBlocked':False,'signatureVerified':True}
            c.execute('insert into toolchain_images values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(record,'demo',service,digit,result['image']['image'],result['image']['imageId'],4,'b'*64,'a'*64,'d'*64,'ready',json.dumps(result),timestamp,timestamp));records.append({'image_record_id':record,'service':service,'toolchain_digest':digit,'image_ref':result['image']['image'],'image_id':result['image']['imageId'],'status':'ready'})
        result={'ok':True,'images':records}
        c.execute('insert into toolchain_jobs(job_id,idempotency_key,project_slug,ref,config_revision,config_digest,toolchain_digest,archive_sha256,plan_digest,status,payload_json,result_json,log_text,created_at,updated_at,attempts,last_error) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,'k','demo','main',4,'b'*64,'c'*64,'a'*64,'d'*64,'succeeded','{}',json.dumps(result),'done\n',timestamp,timestamp,1,''));c.commit();c.close();return job_id

    def test_activation_is_revisioned_and_does_not_change_containers(self):
        job_id=self._seed_succeeded_job()
        plan=self.lifecycle.activation_plan({'project_slug':'demo','environment':'preview','job_id':job_id,'expected_revision':0})
        self.assertTrue(plan['approval_required']);self.assertTrue(plan['pending_rebuild']);self.assertFalse(plan['containers_changed'])
        with self.assertRaisesRegex(PermissionError,'approval_required'):
            self.lifecycle.activation_apply({**plan,'approved':False,'approval_id':'apr_'+'1'*20,'actor':'alice'})
        applied=self.lifecycle.activation_apply({'project_slug':'demo','environment':'preview','job_id':job_id,'expected_revision':0,'plan_digest':plan['plan_digest'],'approved':True,'approval_id':'apr_'+'1'*20,'actor':'alice'})
        self.assertEqual(applied['revision'],1);self.assertTrue(applied['pending_rebuild']);self.assertFalse(applied['containers_changed'])
        state=self.lifecycle.activation_state('demo','preview');self.assertEqual(state['revision'],1);self.assertEqual(len(state['images']),2)
        with self.assertRaisesRegex(ValueError,'activation_revision_mismatch'):
            self.lifecycle.activation_plan({'project_slug':'demo','environment':'preview','job_id':job_id,'expected_revision':0})

    def test_logs_and_image_details_are_sanitized(self):
        c=self.module.db();timestamp=int(time.time());job='toolchain_'+'2'*24
        c.execute('insert into toolchain_jobs(job_id,idempotency_key,project_slug,ref,config_revision,config_digest,toolchain_digest,archive_sha256,plan_digest,status,payload_json,result_json,log_text,created_at,updated_at,attempts,last_error) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(job,'k2','demo','main',4,'b'*64,'c'*64,'a'*64,'d'*64,'failed','{}','{}','token=abc123456789\n',timestamp,timestamp,1,'password=badvalue'));c.commit();c.close()
        logs=self.lifecycle.logs(job);serialized=json.dumps(logs)
        self.assertNotIn('abc123456789',serialized);self.assertNotIn('badvalue',serialized)
        self.assertIn('[redacted]',serialized)


def hashlib_sha(value:str)->str:
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


if __name__=='__main__':unittest.main()
