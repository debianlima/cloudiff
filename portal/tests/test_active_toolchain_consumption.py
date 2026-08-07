from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LIFECYCLE=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif_toolchain_lifecycle.py'
BROKER=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'
ARTIFACT=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);return module


class ActiveToolchainConsumptionTests(unittest.TestCase):
    def test_compatible_activation_is_resolved_by_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path=Path(temporary)/'builds.db';connection=sqlite3.connect(db_path);connection.row_factory=sqlite3.Row
            connection.executescript('''
              create table toolchain_images(image_record_id text primary key,project_slug text,service text,toolchain_digest text,image_ref text,image_id text,config_revision integer,config_digest text,archive_sha256 text,plan_digest text,status text,result_json text,created_at integer,updated_at integer);
              create table toolchain_activations(project_slug text,environment text,service text,image_record_id text,toolchain_digest text,activation_revision integer,approval_id text,activated_by text,activated_at integer,primary key(project_slug,environment,service));
            ''')
            details={'validatedToolchainDigest':'v'*64,'signatureVerified':True,'scannerBlocked':False,'scannerCounts':{},'sbomReady':True,'sbomSha256':'s'*64,'script':{},'hooks':[]}
            connection.execute('insert into toolchain_images values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('img_'+'1'*24,'demo','api','e'*64,'cloudif-toolchain/demo-api:active','sha256:'+'2'*64,4,'c'*64,'a'*64,'p'*64,'active',json.dumps(details),1,1))
            connection.execute('insert into toolchain_activations values(?,?,?,?,?,?,?,?,?)',('demo','preview','api','img_'+'1'*24,'e'*64,3,'apr_'+'3'*20,'alice',1));connection.commit();connection.close()
            fake=types.SimpleNamespace(db=lambda: sqlite_connection(db_path))
            lifecycle=load(LIFECYCLE,'active_lifecycle_test');lifecycle.configure(fake)
            result=lifecycle.compatible_activations('demo','preview',[{'service':'api','toolchainDigest':'v'*64}],'a'*64,'c'*64)
            self.assertEqual(result['activeCount'],1);self.assertFalse(result['blocked'])
            active=result['images']['api'];self.assertEqual(active['imageRecordId'],'img_'+'1'*24)
            self.assertTrue(active['signatureVerified']);self.assertFalse(active['scannerBlocked'])
            self.assertEqual(result['states'][0]['status'],'synchronized')

    def test_incompatible_activation_blocks_application_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path=Path(temporary)/'builds.db';connection=sqlite3.connect(db_path);connection.row_factory=sqlite3.Row
            connection.executescript('''
              create table toolchain_images(image_record_id text primary key,project_slug text,service text,toolchain_digest text,image_ref text,image_id text,config_revision integer,config_digest text,archive_sha256 text,plan_digest text,status text,result_json text,created_at integer,updated_at integer);
              create table toolchain_activations(project_slug text,environment text,service text,image_record_id text,toolchain_digest text,activation_revision integer,approval_id text,activated_by text,activated_at integer,primary key(project_slug,environment,service));
            ''')
            details={'validatedToolchainDigest':'old','signatureVerified':False,'scannerBlocked':False,'script':{'path':'scripts/provision.sh'},'hooks':[]}
            connection.execute('insert into toolchain_images values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('img_'+'1'*24,'demo','api','e'*64,'image','sha256:'+'2'*64,3,'old','old','p','active',json.dumps(details),1,1))
            connection.execute('insert into toolchain_activations values(?,?,?,?,?,?,?,?,?)',('demo','production','api','img_'+'1'*24,'e'*64,1,'apr_'+'3'*20,'alice',1));connection.commit();connection.close()
            lifecycle=load(LIFECYCLE,'outdated_lifecycle_test');lifecycle.configure(types.SimpleNamespace(db=lambda: sqlite_connection(db_path)))
            result=lifecycle.compatible_activations('demo','production',[{'service':'api','toolchainDigest':'v'*64}],'a'*64,'c'*64)
            self.assertFalse(result['images']);self.assertEqual(result['blocked'][0]['code'],'image-outdated')
            reasons=set(result['blocked'][0]['reasons'])
            self.assertTrue({'config-digest-mismatch','toolchain-digest-mismatch','source-archive-mismatch','signature-not-verified'}<=reasons)

    def test_executor_reuses_only_exact_verified_image(self):
        artifact=load(ARTIFACT,'active_artifact_test')
        validation={'ok':True,'buildable':True,'toolchainDigest':'v'*64,'catalogVersion':1,'architecture':'amd64','base':{},'systemPackages':[],'tools':[],'script':{}}
        artifact.validate_toolchain=lambda *args,**kwargs:validation
        labels={'org.cloudiff.kind':'toolchain','org.cloudiff.project':'demo','org.cloudiff.service':'api','org.cloudiff.toolchain-digest':'e'*64,'org.cloudiff.validated-toolchain-digest':'v'*64,'org.cloudiff.config-digest':'c'*64}
        artifact.inspect_image=lambda ref:{'image':ref,'imageId':'sha256:'+'2'*64,'labels':labels}
        request={'project_slug':'demo','config_digest':'c'*64,'archive_sha256':'a'*64,'toolchain':{},'environment':'preview'}
        service={'name':'api','runtime':'node','version':'24'}
        active={'imageRecordId':'img_'+'1'*24,'imageRef':'cloudif-toolchain/demo-api:active','imageId':'sha256:'+'2'*64,'effectiveToolchainDigest':'e'*64,'validatedToolchainDigest':'v'*64,'activationRevision':3,'archiveSha256':'a'*64,'sourceArchiveBound':False,'signatureVerified':True,'scannerBlocked':False}
        result=artifact.reuse_active_toolchain(request,service,Path('.'),active)
        self.assertTrue(result['active']);self.assertTrue(result['reused']);self.assertFalse(result['built'])
        self.assertEqual(result['activationEnvironment'],'preview');self.assertEqual(result['activationRevision'],3)
        active['imageId']='sha256:'+'9'*64
        with self.assertRaises(artifact.ArtifactError) as captured:
            artifact.reuse_active_toolchain(request,service,Path('.'),active)
        self.assertEqual(captured.exception.code,'active_toolchain_verification_failed')
        self.assertIn('imagem ativa diverge',captured.exception.message)

    def test_build_plan_and_executor_bind_environment_and_active_images(self):
        broker=BROKER.read_text();artifact=ARTIFACT.read_text();gateway=GATEWAY.read_text()
        for marker in (
          "environment=str(payload.get('environment') or 'development')",
          'compatible_activations(slug,environment',
          "'active_toolchain_images':activation.get('images') or {}",
          "'activeToolchainImages':plan.get('active_toolchain_images') or {}",
        ):self.assertIn(marker,broker)
        self.assertIn("active_images=request.get('activeToolchainImages') or {}",artifact)
        self.assertIn('reuse_active_toolchain(request,service,source,active)',artifact)
        self.assertIn("'environment':request['environment']",artifact)
        self.assertIn("'environment':ENVIRONMENT_NAME_SCHEMA",gateway[gateway.index("{'name':'build.multiservice.plan'"):gateway.index("{'name':'approval.request-multiservice-build'")])


def sqlite_connection(path:Path):
    connection=sqlite3.connect(path);connection.row_factory=sqlite3.Row;return connection


if __name__=='__main__':unittest.main()
