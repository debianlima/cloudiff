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

    def test_identity_only_current_config_uses_snapshot_preserved_environment(self):
        current={'ok':True,'configured':False,'currentRevision':0,'configDigest':None,'toolchainDigest':None,'project':{'slug':'demo','status':'published'}}
        def executor(method,path,payload=None,timeout=0):
            if path.startswith('/v1/compose-sources/'):return 200,self.source()
            raise AssertionError(path)
        with patch.object(self.broker,'_multiservice_configuration',return_value=current), \
             patch.object(self.broker,'_multiservice_reconciliation',return_value=None), \
             patch.object(self.broker,'_deployment_executor_call',side_effect=executor):
            plan=self.broker._compose_publication_plan({'project_slug':'demo','environment':'homologation','trace_id':'trace-current','source_kind':'linked-compose'})
        self.assertTrue(plan['execution_allowed'],plan['blockers'])
        self.assertEqual(plan['operation']['config_revision'],1)
        self.assertRegex(plan['operation']['config_digest'],r'^[a-f0-9]{64}$')
        self.assertRegex(plan['operation']['toolchain_digest'],r'^[a-f0-9]{64}$')
        self.assertEqual(plan['summary']['runtimeEnvironment']['variableNames'],{})

    def test_compose_source_proxy_requires_canonical_project_but_forwards_executor_status(self):
        with patch.object(self.broker,'_multiservice_configuration',return_value={'ok':True,'project':{'slug':'demo'}}), \
             patch.object(self.broker,'_deployment_executor_call',return_value=(409,{'ok':False,'error':{'code':'compose_source_not_running'}})) as call:
            code,data=self.broker._compose_source_proxy('demo')
        self.assertEqual(code,409);self.assertEqual(data['error']['code'],'compose_source_not_running')
        call.assert_called_once()

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

    def test_linked_binding_prefers_live_komodo_ids_over_stale_database_ids(self):
        source=PORTAL.read_text()
        block=source[source.index('def _linked_compose_binding(con,slug):'):source.index('def _linked_compose_status',source.index('def _linked_compose_binding(con,slug):'))]
        self.assertIn('v133_komodo_project_status(slug,timeout=45)',block)
        self.assertIn("live_repo_id=str(data.get('repo_id')",block)
        self.assertIn("live_stack_id=str(data.get('stack_id')",block)
        self.assertNotIn("return {'repoId':repo_id,'stackId':stack_id",block)

    def test_next_candidate_advances_past_failed_homologation_jobs(self):
        source=PORTAL.read_text()
        start=source.index('def _next_candidate(con,slug):')
        end=source.index('def _create_multiservice_homologation_candidate',start)
        block=source[start:end]
        self.assertIn("operation='homologation_candidate'",block)
        self.assertIn('return max(a,b,c)+1',block)

    def test_homologation_uses_full_compose_source_commit_not_short_preview_head(self):
        source=PORTAL.read_text()
        start=source.index('def _create_linked_compose_homologation_candidate(')
        end=source.index('def _publish_linked_compose_homologated_candidate(',start)
        block=source[start:end]
        self.assertIn("probe=_compose_source_probe(slug);source_state=probe.get('source') or {}",block)
        self.assertIn("source_commit=str(source_state.get('source_commit') or '')",block)
        self.assertIn("source_commit.startswith(preview_head)",block)
        self.assertNotIn("source_commit=str((source.get('git') or {}).get('head') or '')",block)

    def test_portal_prepares_source_preview_bridge_before_external_validation(self):
        source=PORTAL.read_text()
        self.assertIn('def _compose_source_preview_bridge(slug,num,generation=1):',source)
        block=source[source.index('def _ensure_linked_compose_preview('):source.index('def _compose_source_preview_bridge(',source.index('def _ensure_linked_compose_preview('))]
        self.assertIn('bridge=_compose_source_preview_bridge(slug,num,1)',block)
        self.assertLess(block.index('bridge=_compose_source_preview_bridge'),block.index("_external_ok(result['hostname'])"))

    def test_portal_compose_detection_is_generic_not_tuleap_allowlist(self):
        source=PORTAL.read_text()
        self.assertNotIn("LINKED_COMPOSE_PROJECTS={'tuleap-laboratorio-de-hardware'}",source)
        self.assertIn('def _is_linked_compose_project(slug):',source)
        self.assertIn('def _compose_source_probe(slug):',source)
        self.assertIn("'/v1/compose-source?'",source)
        self.assertIn("code.startswith('compose_')",source)
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

    def test_compose_healthcheck_supports_cmd_without_shell_expansion(self):
        source=EXECUTOR.read_text()
        start=source.index('def _health_options(health:dict)->list[str]:')
        end=source.index('def _compose_container_ready',start)
        block=source[start:end]
        self.assertIn("test[0] not in {'CMD-SHELL','CMD'}",block)
        self.assertIn("health_cmd='exec '+shlex.join",block)
        self.assertIn("if test[0]=='CMD-SHELL':health_cmd=str(test[1])",block)
        self.assertIn('import shlex',source)

    def test_bind_restore_uses_isolated_docker_helper_under_executor_sandbox(self):
        source=EXECUTOR.read_text()
        start=source.index('def _extract_tar(archive:Path,target:Path)->None:')
        end=source.index('def _compose_overlay_roots',start)
        block=source[start:end]
        self.assertIn("'--network','none'",block)
        self.assertIn("'--read-only'",block)
        self.assertIn("'--cap-drop','ALL'",block)
        self.assertIn("'--cap-add','CHOWN'",block)
        self.assertIn("'--cap-add','DAC_OVERRIDE'",block)
        self.assertIn("'--cap-add','FOWNER'",block)
        self.assertIn("'--security-opt','no-new-privileges'",block)
        self.assertIn("f'type=bind,src={target_path},dst=/restore'",block)
        self.assertIn("f'type=bind,src={archive_path},dst=/snapshot.tar,readonly'",block)
        self.assertNotIn("subprocess.run(['tar'",block)

    def test_named_volumes_are_archived_through_paused_container_docker_cp(self):
        source=EXECUTOR.read_text()
        self.assertIn('def _tar_container_path(container:str,source_path:str,target:Path)->None:',source)
        helper=source[source.index('def _tar_container_path(container:str,source_path:str,target:Path)->None:'):source.index('def _tar_path(',source.index('def _tar_container_path(container:str,source_path:str,target:Path)->None:'))]
        self.assertIn("command=['docker','cp',f'{container}:{source_path}/.','-']",helper)
        self.assertIn("with target.open('wb') as output",helper)
        self.assertNotIn('/var/lib/docker/volumes',helper)
        snap=source[source.index('def create_compose_snapshot('):source.index('def _restore_volume_archive',source.index('def create_compose_snapshot('))]
        self.assertIn("if kind=='volume':",snap)
        self.assertIn('_tar_container_path(name,dest,archive)',snap)
        self.assertIn('total+=archive.stat().st_size',snap)
        self.assertIn('shutil.rmtree(tmp,ignore_errors=True)',snap)


    def test_compose_source_digest_sorts_mounts_before_hashing(self):
        source=EXECUTOR.read_text()
        start=source.index('def compose_source_state(')
        end=source.index('def _snapshot_safe_status',start)
        block=source[start:end]
        self.assertIn("mounts=sorted(mounts,key=lambda item:(item['destination'],item['type'],item['sourceRef'],bool(item['rw'])))",block)
        self.assertLess(block.index('mounts=sorted('),block.index("material={'service':service"))

    def test_compose_source_can_select_single_http80_edge_without_publication_network(self):
        source=EXECUTOR.read_text()
        block=source[source.index('def compose_source_state('):source.index('def _snapshot_safe_status',source.index('def compose_source_state('))]
        self.assertIn("elif 80 in ports:fallback_edges.append((service,80))",block)
        self.assertIn('if publication_edges:',block)
        self.assertIn("org.cloudiff.public-port",block)

    def test_source_preview_bridge_migrates_only_same_project_legacy_preview_with_rollback(self):
        source=EXECUTOR.read_text();block=source[source.index('def ensure_source_preview_bridge(payload:Any)->dict:'):source.index('def activate_publication_bridge',source.index('def ensure_source_preview_bridge(payload:Any)->dict:'))]
        self.assertIn("legacy=current.get('cloudif.project')==slug",block)
        self.assertIn("raise DeploymentError('source_preview_bridge_conflict'",block)
        self.assertIn("backup=name+'-rollback-'",block)
        self.assertIn("docker('rename',backup,name",block)
        self.assertIn("'migratedLegacyPreview':bool(legacy)",block)

    def test_compose_source_preview_bridge_uses_private_compose_network_and_cloudif_alias(self):
        source=EXECUTOR.read_text()
        self.assertIn('def ensure_source_preview_bridge(payload:Any)->dict:',source)
        block=source[source.index('def ensure_source_preview_bridge(payload:Any)->dict:'):source.index('def activate_publication_bridge',source.index('def ensure_source_preview_bridge(payload:Any)->dict:'))]
        self.assertIn("com.docker.compose.project",block)
        self.assertIn("PUBLICATION_NETWORK,name",block)
        self.assertIn("source_preview_bridge_health_failed",block)
        self.assertIn("f'cloudif-p{public_number}-w{generation}-preview-web'",block)
        self.assertIn("'/v1/compose-source-preview-bridge'",source)

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
