from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from portal.tests.test_project_environment_controller import load_module as load_environment

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_secret_store.py'


def load_secret(root:Path):
    os.environ['CLOUDIF_PROJECT_CONFIG_DB']=str(root/'config.db')
    os.environ['CLOUDIF_ENVIRONMENT_SECRET_KEY_FILE']=str(root/'secret.key')
    environment=load_environment(root)
    sys.modules['cloudif_project_environment']=environment
    name='project_secret_store_test_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,SOURCE);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);module.init_db();return environment,module


class ProjectEnvironmentSecretStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.environment,self.store=load_secret(self.root)

    def tearDown(self):
        sys.modules.pop('cloudif_project_environment',None);self.temp.cleanup()

    def stage(self,value='super-secret-value'):
        return self.store.stage_secret('demo','preview','api','DATABASE_URL',value,'alice',900)

    def rotate(self,stage,revision=0):
        plan=self.store.rotation_plan('demo',stage['stageId'],revision,'alice','Rotacionar banco',{'secret':True,'required':True,'runtime':True,'restartRequired':True},900)
        result=self.store.apply_rotation('demo',plan['planDigest'],stage['stageId'],revision,'alice')
        return plan,result

    def test_stage_encrypts_material_and_creates_restricted_key(self):
        stage=self.stage()
        self.assertTrue(stage['ok']);self.assertFalse(stage['secretValueIncluded']);self.assertFalse(stage['ciphertextIncluded'])
        key=self.root/'secret.key';self.assertTrue(key.exists());self.assertEqual(key.stat().st_mode & 0o777,0o600);self.assertEqual(len(key.read_bytes()),32)
        connection=sqlite3.connect(self.root/'config.db');row=connection.execute('select ciphertext_b64,nonce_b64,aad_json from environment_secret_materials where stage_id=?',(stage['stageId'],)).fetchone();connection.close()
        self.assertIsNotNone(row);serialized='|'.join(row)
        self.assertNotIn('super-secret-value',serialized)
        self.assertNotIn('super-secret-value',(self.root/'config.db').read_bytes().decode('latin1',errors='ignore'))

    def test_rotation_binds_versioned_reference_to_environment(self):
        stage=self.stage();plan,result=self.rotate(stage)
        self.assertTrue(result['ok']);self.assertEqual(result['version'],1)
        self.assertEqual(result['secretReference'],'cloudiff-secret://demo/preview/api/DATABASE_URL/v1')
        self.assertTrue(result['restartRequired']);self.assertFalse(result['rebuildRequired'])
        effective=self.environment.effective_internal('demo','preview','api')
        self.assertEqual(effective['secretRuntimeReferences']['api']['DATABASE_URL'],result['secretReference'])
        listing=self.store.list_secrets('demo','preview','api')
        active=[item for item in listing['secrets'] if item['status']=='active']
        self.assertEqual(len(active),1);self.assertFalse(listing['secretValuesIncluded']);self.assertFalse(listing['ciphertextsIncluded'])
        serialized=json.dumps({'plan':plan,'result':result,'list':listing})
        self.assertNotIn('super-secret-value',serialized);self.assertNotIn('ciphertext_b64',serialized)

    def test_internal_resolution_returns_value_only_for_active_exact_scope(self):
        stage=self.stage('postgres://user:password@db/project');_,result=self.rotate(stage)
        reference=result['secretReference']
        resolved=self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':reference}})
        self.assertTrue(resolved['internal']);self.assertTrue(resolved['secretValuesIncluded'])
        self.assertEqual(resolved['resolvedSecrets']['api']['DATABASE_URL'],'postgres://user:password@db/project')
        with self.assertRaisesRegex(PermissionError,'secret_reference_scope_mismatch'):
            self.store.resolve_internal('demo','production',{'api':{'DATABASE_URL':reference}})
        with self.assertRaisesRegex(PermissionError,'secret_reference_scope_mismatch'):
            self.store.resolve_internal('demo','preview',{'web':{'DATABASE_URL':reference}})

    def test_second_rotation_supersedes_previous_version(self):
        first=self.stage('one');_,first_result=self.rotate(first)
        second=self.stage('two');plan=self.store.rotation_plan('demo',second['stageId'],1,'alice','Rotacionar novamente',{'secret':True,'required':True,'runtime':True},900);second_result=self.store.apply_rotation('demo',plan['planDigest'],second['stageId'],1,'alice')
        self.assertEqual(second_result['version'],2);self.assertTrue(second_result['secretReference'].endswith('/v2'))
        listing=self.store.list_secrets('demo','preview','api');statuses={item['version']:item['status'] for item in listing['secrets']}
        self.assertEqual(statuses[1],'superseded');self.assertEqual(statuses[2],'active')
        with self.assertRaisesRegex(LookupError,'active_secret_not_found'):
            self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':first_result['secretReference']}})
        self.assertEqual(self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':second_result['secretReference']}})['resolvedSecrets']['api']['DATABASE_URL'],'two')

    def test_revocation_is_approved_state_and_blocks_resolution(self):
        stage=self.stage();_,rotated=self.rotate(stage)
        plan=self.store.revocation_plan('demo',rotated['secretReference'],1,'alice','Revogar credencial',900)
        self.assertTrue(plan['approvalRequired']);self.assertTrue(plan['configurationWillBecomeBlocked'])
        revoked=self.store.apply_revocation('demo',plan['planDigest'],rotated['secretReference'],1,'alice')
        self.assertEqual(revoked['status'],'revoked');self.assertTrue(revoked['configurationBlocked'])
        with self.assertRaisesRegex(LookupError,'active_secret_not_found'):
            self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':rotated['secretReference']}})
        again=self.store.apply_revocation('demo',plan['planDigest'],rotated['secretReference'],1,'alice')
        self.assertTrue(again['idempotent'])

    def test_history_and_plans_do_not_expose_secret_material(self):
        stage=self.stage('do-not-expose');plan,result=self.rotate(stage)
        history=self.store.history('demo')
        serialized=json.dumps({'stage':stage,'plan':plan,'result':result,'history':history})
        self.assertNotIn('do-not-expose',serialized);self.assertNotIn('ciphertext_b64',serialized);self.assertNotIn('nonce_b64',serialized)
        self.assertFalse(history['secretValuesIncluded'])

    def test_expired_stage_and_wrong_revision_fail_closed(self):
        stage=self.stage();connection=sqlite3.connect(self.root/'config.db');connection.execute('update environment_secret_materials set expires_at=1 where stage_id=?',(stage['stageId'],));connection.commit();connection.close()
        with self.assertRaisesRegex(ValueError,'secret_stage_expired_or_unavailable'):
            self.store.rotation_plan('demo',stage['stageId'],0,'alice','Rotacionar',{},900)
        fresh=self.stage('fresh')
        with self.assertRaisesRegex(ValueError,'environment_revision_mismatch'):
            self.store.rotation_plan('demo',fresh['stageId'],99,'alice','Rotacionar',{},900)

    def test_promotion_reencrypts_without_exposing_plaintext(self):
        source_stage=self.stage('promotion-secret-value');_,source=self.rotate(source_stage)
        plan=self.store.promotion_plan('demo',source['secretReference'],'homologation',1,'alice','Promover segredo',{'secret':True,'required':True,'runtime':True},900)
        self.assertTrue(plan['sideEffectFree']);self.assertFalse(plan['secretValueIncluded'])
        result=self.store.apply_promotion('demo',plan['planDigest'],source['secretReference'],1,'alice')
        self.assertEqual(result['targetEnvironment'],'homologation');self.assertEqual(result['version'],1)
        self.assertEqual(self.store.resolve_internal('demo','homologation',{'api':{'DATABASE_URL':result['secretReference']}})['resolvedSecrets']['api']['DATABASE_URL'],'promotion-secret-value')
        self.assertEqual(self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':source['secretReference']}})['resolvedSecrets']['api']['DATABASE_URL'],'promotion-secret-value')
        public=json.dumps({'plan':plan,'result':result,'history':self.store.history('demo')})
        self.assertNotIn('promotion-secret-value',public);self.assertNotIn('ciphertext_b64',public)

    def test_active_expiration_blocks_resolution_and_is_visible_as_metadata(self):
        stage=self.stage('expires-soon')
        plan=self.store.rotation_plan('demo',stage['stageId'],0,'alice','Credencial temporária',{'secret':True,'required':True,'runtime':True},900,active_ttl_seconds=60)
        result=self.store.apply_rotation('demo',plan['planDigest'],stage['stageId'],0,'alice')
        self.assertEqual(result['activeExpiresAt'],plan['activeExpiresAt'])
        connection=sqlite3.connect(self.root/'config.db');connection.execute("update environment_secret_materials set expires_at=1 where secret_reference=?",(result['secretReference'],));connection.commit();connection.close()
        listing=self.store.list_secrets('demo','preview','api');item=next(x for x in listing['secrets'] if x['secretReference']==result['secretReference'])
        self.assertEqual(item['status'],'expired');self.assertEqual(item['activeExpiresAt'],1)
        with self.assertRaisesRegex(LookupError,'active_secret_not_found'):
            self.store.resolve_internal('demo','preview',{'api':{'DATABASE_URL':result['secretReference']}})


    def test_key_permissions_fail_closed(self):
        key=self.root/'secret.key';key.write_bytes(os.urandom(32));key.chmod(0o644)
        with self.assertRaisesRegex(PermissionError,'secret_key_permissions_too_open'):
            self.store.stage_secret('demo','preview','api','DATABASE_URL','x','alice',900)


if __name__=='__main__':unittest.main()
