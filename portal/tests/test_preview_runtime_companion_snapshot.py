from pathlib import Path
import ast,os,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()

class FakeDeploymentError(Exception):
    def __init__(self,*args): super().__init__(*args)

class PreviewRuntimeCompanionSnapshotTests(unittest.TestCase):
    def bind_helper(self):
        tree=ast.parse(EXEC);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_preview_runtime_bind_ref')
        source=ast.get_source_segment(EXEC,node)
        ns={'Path':Path,'os':os,'DeploymentError':FakeDeploymentError}
        exec(source,ns)
        return ns['_preview_runtime_bind_ref']

    def test_source_linked_preview_discovers_only_project_preview_companions(self):
        block=EXEC[EXEC.index('def _preview_runtime_services'):EXEC.index('def _preview_runtime_bind_ref',EXEC.index('def _preview_runtime_services'))]
        self.assertIn("prefix=f'cloudif-{slug}-preview-'",block)
        self.assertIn("project_label!=slug",block)
        self.assertIn("stage_label not in {'preview','restored-candidate'}",block)
        self.assertIn("preview_runtime_companion_not_running",block)
        self.assertIn("len(rows)>MAX_SERVICES",block)

    def test_source_linked_binds_are_confined_to_managed_roots(self):
        block=EXEC[EXEC.index('def _preview_runtime_bind_ref'):EXEC.index('def _preview_runtime_edge_port',EXEC.index('def _preview_runtime_bind_ref'))]
        self.assertIn("project_root:Path|None=None",block)
        self.assertIn("CLOUDIF_PREVIEW_DATA_ROOT",block)
        self.assertIn("f'p{int(public_number)}'/f'w{int(generation)}'",block)
        self.assertIn("return 'preview-data/'",block)
        self.assertIn("return 'project-runtime/'",block)
        self.assertIn("preview_runtime_bind_outside_allowed_roots",block)

    def test_managed_preview_data_root_is_project_and_generation_scoped(self):
        block=EXEC[EXEC.index('def _preview_runtime_bind_ref'):EXEC.index('def _preview_runtime_edge_port',EXEC.index('def _preview_runtime_bind_ref'))]
        self.assertNotIn("relative_to(preview_data_base)",block)
        self.assertIn("source.relative_to(preview_data_root)",block)
        self.assertIn("source=source.resolve()",block)

    def test_managed_preview_data_classification_rejects_other_project_and_symlink_escape(self):
        fn=self.bind_helper()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);checkout=root/'checkout';checkout.mkdir()
            managed=root/'preview-data';good=managed/'p1022'/'w1'/'data';good.mkdir(parents=True)
            other=managed/'p1023'/'w1'/'data';other.mkdir(parents=True)
            outside=root/'outside';outside.mkdir()
            escape=managed/'p1022'/'w1'/'escape';escape.symlink_to(outside,target_is_directory=True)
            old=os.environ.get('CLOUDIF_PREVIEW_DATA_ROOT');os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=str(managed)
            try:
                self.assertEqual(fn(good,checkout,1022,1),'preview-data/data')
                with self.assertRaises(FakeDeploymentError):fn(other,checkout,1022,1)
                with self.assertRaises(FakeDeploymentError):fn(escape,checkout,1022,1)
            finally:
                if old is None:os.environ.pop('CLOUDIF_PREVIEW_DATA_ROOT',None)
                else:os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=old

    def test_snapshot_preserves_all_services_and_network_aliases(self):
        source=EXEC[EXEC.index('def preview_runtime_source_state'):EXEC.index('def create_preview_runtime_snapshot',EXEC.index('def preview_runtime_source_state'))]
        snap=EXEC[EXEC.index('def create_preview_runtime_snapshot'):EXEC.index('def _snapshot_safe_status',EXEC.index('def create_preview_runtime_snapshot'))]
        self.assertIn("services=_preview_runtime_services",source)
        self.assertIn("'network_aliases':aliases",source)
        self.assertIn("'service_count':len(safe)",source)
        self.assertIn("for service,name,row,aliases in services",snap)
        self.assertIn("'source_container':name",snap)
        self.assertIn("'network_aliases':aliases",snap)
        self.assertIn("for name in reversed(paused)",snap)

    def test_restore_recreates_source_network_aliases_inside_isolated_deployment(self):
        block=EXEC[EXEC.index('def deploy_compose_snapshot'):EXEC.index('def assigned_port',EXEC.index('def deploy_compose_snapshot'))]
        self.assertIn("spec.get('network_aliases')",block)
        self.assertIn("command.extend(['--network-alias',alias])",block)
        self.assertIn("--network-alias',service",block)

if __name__=='__main__':unittest.main()
