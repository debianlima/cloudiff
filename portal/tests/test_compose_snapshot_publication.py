from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
BROKER=ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py'
EXECUTOR=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
PORTAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py'


def load_executor():
    spec=importlib.util.spec_from_file_location('compose_snapshot_executor_test',EXECUTOR)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


def load_broker():
    fake=types.ModuleType('cloudif_release_manager')
    fake.project_setting=lambda slug:{'tenant':'tenant-'+slug}
    sys.modules['cloudif_release_manager']=fake
    spec=importlib.util.spec_from_file_location('compose_snapshot_broker_test',BROKER)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


class ComposeSnapshotPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker=load_broker()

    def config(self):
        return {
            'ok':True,'configured':True,'currentRevision':3,'configDigest':'c'*64,'toolchainDigest':'d'*64,
            'configuration':{
                'project':{'type':'multi-service','primaryService':'app'},
                'services':{'app':{'runtime':'compose','compose':'docker-compose.yml'}},
                'environment':{'variables':{},'required':{}},
            },
        }

    def state(self):
        return {'ok':True,'status':'ready','configRevision':3,'membershipRevision':4,'aclDigest':'e'*64}

    def runtime(self,environment):
        return {
            'ok':True,'valid':True,'environment':environment,'configurationRevision':3,'environmentRevision':7,
            'publicRuntimeEnvironment':{},'secretRuntimeReferences':{},
            'runtimeEnvironmentDigest':'1'*64,'environmentDigest':'2'*64,'secretValuesIncluded':False,
        }

    def source(self):
        return {
            'ok':True,'source_kind':'linked-compose','project_slug':'demo','source_digest':'a'*64,'source_commit':'b'*40,
            'edge_service':'gateway','edge_port':8080,
            'services':[
                {'service':'app','image_id':'sha256:'+'3'*64,'service_digest':'4'*64,'port':3000},
                {'service':'gateway','image_id':'sha256:'+'5'*64,'service_digest':'6'*64,'port':8080},
            ],
            'secretValuesIncluded':False,
        }

    def snapshot(self):
        value=self.source().copy()
        value.update({'snapshot_id':'snap_'+'7'*24,'snapshot_digest':'8'*64,'status':'ready'})
        return value

    def plan(self,environment='homologation',snapshot_id=''):
        def executor(method,path,payload=None,timeout=0):
            if path.startswith('/v1/compose-snapshots/'):
                return 200,self.snapshot()
            if path.startswith('/v1/compose-sources/'):
                return 200,self.source()
            raise AssertionError(path)
        with patch.object(self.broker,'_multiservice_configuration',return_value=self.config()), \
             patch.object(self.broker,'_multiservice_reconciliation',return_value=self.state()), \
             patch.object(self.broker,'_effective_environment_internal',side_effect=lambda slug,env:self.runtime(env)), \
             patch.object(self.broker,'_deployment_executor_call',side_effect=executor):
            payload={'project_slug':'demo','environment':environment,'trace_id':'trace-compose','source_kind':'linked-compose'}
            if snapshot_id:payload['snapshot_id']=snapshot_id
            return self.broker._compose_publication_plan(payload)

    def test_homologation_plan_does_not_require_build_job(self):
        plan=self.plan('homologation')
        self.assertTrue(plan['execution_allowed'],plan['blockers'])
        self.assertNotIn('build-job-required',plan['blockers'])
        self.assertEqual(plan['operation']['source_kind'],'linked-compose')
        self.assertEqual(plan['operation']['source_digest'],'a'*64)
        self.assertEqual(plan['operation']['source_commit'],'b'*40)
        self.assertEqual(plan['summary']['edgeService'],'gateway')
        self.assertEqual(plan['summary']['edgePort'],8080)
        self.assertFalse(plan['secretValuesIncluded'])

    def test_production_requires_existing_snapshot(self):
        plan=self.plan('production')
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('compose-snapshot-required-for-production',plan['blockers'])

    def test_production_reuses_same_snapshot_identity(self):
        sid='snap_'+'7'*24
        plan=self.plan('production',sid)
        self.assertTrue(plan['execution_allowed'],plan['blockers'])
        self.assertEqual(plan['operation']['snapshot_id'],sid)
        self.assertEqual(plan['operation']['snapshot_digest'],'8'*64)
        self.assertEqual(plan['artifactImageId'],'sha256:'+'8'*64)

    def test_linked_preview_helper_refreshes_current_stack_without_reclone(self):
        source=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py').read_text()
        start=source.index('def v133_komodo_deploy_linked_current(')
        end=source.index('def v133_komodo_stack_action(',start)
        block=source[start:end]
        self.assertIn('"force_reclone": False',block)
        self.assertIn('"force_clone": False',block)
        self.assertIn('base + "/komodo/project/deploy-full"',block)

    def test_portal_compose_detection_is_generic_not_tuleap_allowlist(self):
        source=PORTAL.read_text()
        self.assertNotIn("LINKED_COMPOSE_PROJECTS={'tuleap-laboratorio-de-hardware'}",source)
        self.assertIn('def _is_linked_compose_project(slug):',source)
        self.assertIn("str(service.get('runtime') or '')=='compose'",source)
        self.assertIn('_create_linked_compose_homologation_candidate',source)
        self.assertIn('_publish_linked_compose_homologated_candidate',source)

    def test_mount_parent_paths_are_not_treated_as_rootfs_drift(self):
        executor=load_executor()
        completed=types.SimpleNamespace(returncode=0,stdout='A /usr\nA /usr/share\nA /usr/share/nginx\nA /usr/share/nginx/html\nA /var\nA /var/lib\n',stderr='')
        with patch.object(executor,'docker',return_value=completed):
            roots=executor._compose_overlay_roots('container',['/usr/share/nginx/html/cloudiff','/var/lib/mysql'])
        self.assertEqual(roots,[])

    def test_ephemeral_parent_paths_are_not_treated_as_rootfs_drift(self):
        executor=load_executor()
        completed=types.SimpleNamespace(returncode=0,stdout='A /var\nA /run\nA /tmp\n',stderr='')
        with patch.object(executor,'docker',return_value=completed):
            roots=executor._compose_overlay_roots('container',[])
        self.assertEqual(roots,[])

    def test_real_rootfs_drift_remains_blocked(self):
        executor=load_executor()
        completed=types.SimpleNamespace(returncode=0,stdout='A /opt/cloudiff-drift\n',stderr='')
        with patch.object(executor,'docker',return_value=completed):
            with self.assertRaises(executor.DeploymentError) as ctx:
                executor._compose_overlay_roots('container',['/var/lib/mysql'])
        self.assertEqual(ctx.exception.code,'compose_rootfs_drift_unsupported')

    def test_rootfs_compression_occurs_after_source_unpause(self):
        source=EXECUTOR.read_text()
        block=source[source.index('def create_compose_snapshot('):source.index('def _restore_volume_archive',source.index('def create_compose_snapshot('))]
        self.assertIn("docker('unpause'",block)
        self.assertIn('_compress_rootfs(raw)',block)
        self.assertLess(block.index("docker('unpause'"),block.index('_compress_rootfs(raw)'))

    def test_executor_exposes_snapshot_source_and_deploy_contracts(self):
        source=EXECUTOR.read_text()
        for marker in (
            'def compose_source_state(',
            'def create_compose_snapshot(',
            'def deploy_compose_snapshot(',
            "r'/v1/compose-sources/",
            "r'/v1/compose-snapshots/",
            "'/v1/compose-snapshots/deploy'",
            'com.docker.compose.project',
            'compose-snapshot',
        ):
            self.assertIn(marker,source)


if __name__=='__main__':unittest.main()
