from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RECONCILER=ROOT/'components/control-plane/current-apps/project-runtime-reconciler-current/cloudif-project-runtime-reconciler.py'
EXECUTOR=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-project-runtime-reconciler.service'


def load_module(root:Path):
    os.environ['CLOUDIF_RUNTIME_RECONCILER_DB']=str(root/'state.db')
    os.environ['CLOUDIF_RUNTIME_RECONCILER_TOKEN']='test-token'
    spec=importlib.util.spec_from_file_location('runtime_reconciler_test_'+root.name.replace('-','_'),RECONCILER)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);module.STATE_DB=root/'state.db';module.init_db();return module


_OBSERVED_UNSET=object()

class ProjectRuntimeReconcilerStateTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.module=load_module(self.root)
    def tearDown(self):self.temp.cleanup()

    def desired(self,**updates):
        base={'ok':True,'configRevision':2,'configDigest':'c'*64,'toolchainDigest':'t'*64,'buildEnvironmentDigest':'b'*64,'runtimeEnvironmentDigest':'r'*64,'environmentDigest':'e'*64,'missingVariables':[],'missingCheckOk':True,'latestBuildJobId':'build_'+'1'*24,'latestBuildAvailable':True}
        base.update(updates);return base

    def observed(self,**updates):
        base={'status':'running','configRevision':2,'configDigest':'c'*64,'toolchainDigest':'t'*64,'buildEnvironmentDigest':'b'*64,'runtimeEnvironmentDigest':'r'*64,'environmentDigest':'e'*64,'buildJobId':'build_'+'1'*24}
        base.update(updates);return base

    def assert_state(self,status,desired=None,observed=_OBSERVED_UNSET,environment='homologation',pending=None):
        runtime_observed=self.observed() if observed is _OBSERVED_UNSET else observed
        result=self.module.evaluate(desired or self.desired(),runtime_observed,environment);self.assertEqual(result['status'],status,result)
        if pending is not None:self.assertEqual(result['pendingAction'],pending)
        self.assertFalse(result['effectsExecuted']);self.assertFalse(result['productionAutoRepairAllowed']);return result

    def test_synchronized(self):self.assert_state('synchronized')
    def test_missing_variable_precedes_runtime_drift(self):self.assert_state('missing-variable',self.desired(missingVariables=[{'service':'api','name':'DATABASE_URL','secret':True}]),self.observed(toolchainDigest='x'*64),'production','configure')
    def test_missing_deployment_is_blocked(self):self.assert_state('blocked',self.desired(),None,'homologation','deploy')
    def test_unhealthy_runtime(self):self.assert_state('unhealthy',observed=self.observed(status='unhealthy'),pending='restart')
    def test_toolchain_or_build_environment_change_requires_rebuild(self):
        self.assert_state('pending-rebuild',observed=self.observed(toolchainDigest='x'*64),pending='rebuild')
        self.assert_state('pending-rebuild',observed=self.observed(buildEnvironmentDigest='x'*64),pending='rebuild')
    def test_runtime_environment_change_requires_restart(self):
        result=self.assert_state('pending-restart',observed=self.observed(runtimeEnvironmentDigest='x'*64),environment='development',pending='restart');self.assertTrue(result['autoRepairAllowed'])
        prod=self.assert_state('pending-restart',observed=self.observed(runtimeEnvironmentDigest='x'*64),environment='production',pending='restart');self.assertFalse(prod['autoRepairAllowed'])
    def test_new_completed_build_is_image_outdated(self):self.assert_state('image-outdated',observed=self.observed(buildJobId='build_'+'2'*24),pending='redeploy')
    def test_remaining_digest_mismatch_is_configuration_drift(self):self.assert_state('configuration-drift',observed=self.observed(configDigest='d'*64),pending='redeploy')
    def test_desired_state_failure_is_blocked(self):self.assert_state('blocked',self.desired(ok=False),self.observed(),pending='none')

    def test_reconcile_one_persists_only_sanitized_state(self):
        self.module.desired_state=lambda slug,environment:self.desired()
        self.module._runtime=lambda slug,environment:self.observed()
        result=self.module.reconcile_one('demo','preview');self.assertEqual(result['status'],'synchronized')
        saved=self.module.saved_state('demo','preview');self.assertEqual(saved['states'][0]['status'],'synchronized');self.assertFalse(saved['secretValuesIncluded']);self.assertFalse(saved['secretReferencesIncluded'])

    def test_runtime_executor_snapshot_stores_names_not_values_or_references(self):
        source=EXECUTOR.read_text();start=source.index('def _runtime_state_record(');end=source.index('def project_runtime_state',start);block=source[start:end]
        self.assertIn("sorted(str(name) for name in values)",block)
        self.assertNotIn('secretRuntimeReferences',block)
        self.assertNotIn("values.items()",block)
        public=source[source.index('def project_runtime_state('):source.index('def _runtime_state_authorized',source.index('def project_runtime_state('))]
        self.assertIn("'secretValuesIncluded':False",public);self.assertIn("'secretReferencesIncluded':False",public)

    def test_runtime_status_endpoint_is_authenticated_and_no_store(self):
        source=EXECUTOR.read_text();self.assertIn('def _runtime_state_authorized',source);self.assertIn("hmac.compare_digest(presented,expected)",source);self.assertIn("'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/runtime-state'",source);self.assertIn("self.send_header('Cache-Control','no-store')",source)

    def test_catalog_and_build_sqlite_are_opened_read_only(self):
        source=RECONCILER.read_text()
        self.assertIn("f'file:{CONTROL_DB}?mode=ro'",source)
        self.assertIn("f'file:{BUILD_DB}?mode=ro'",source)
        self.assertNotIn('sqlite3.connect(CONTROL_DB)',source)
        self.assertNotIn('sqlite3.connect(BUILD_DB)',source)

    def test_service_is_isolated_and_production_network_is_explicit(self):
        unit=UNIT.read_text();self.assertIn('ProtectSystem=strict',unit);self.assertIn('ReadWritePaths=/var/lib/cloudif/runtime-reconciler /var/lib/cloudif/control-plane /var/lib/cloudif/build-broker',unit);self.assertIn('IPAddressAllow=127.0.0.0/8',unit);self.assertIn('IPAddressAllow=10.62.91.2/32',unit);self.assertIn('IPAddressDeny=any',unit)


if __name__=='__main__':unittest.main()
