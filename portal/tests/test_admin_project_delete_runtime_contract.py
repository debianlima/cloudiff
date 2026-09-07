from pathlib import Path
import unittest


class AdminProjectDeleteRuntimeContractTest(unittest.TestCase):
    def test_publisher_supports_unpublish(self):
        source=Path('components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text(encoding='utf-8')
        self.assertIn("def unpublish(payload):",source)
        self.assertIn("self.path=='/unpublish'",source)
        self.assertIn("removed_aliases",source)

    def test_runtime_is_destroyed_before_local_rollback(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        execute=source[source.index('def execute('):]
        self.assertLess(execute.index('publication = _unpublish'),execute.index('runtime = _destroy_runtime'))
        self.assertLess(execute.index('runtime = _destroy_runtime'),execute.index('remote = forja_rollback'))
        self.assertIn("/komodo/stack/destroy",source)

    def test_admin_delete_does_not_request_second_komodo_rollback(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        execute=source[source.index('def execute('):]
        self.assertIn('remote = forja_rollback(slug, execute=True, include_komodo=False)',execute)
        client=Path('components/control-plane/srv/cloudif/lib/cloudif_delete_git_komodo_action.py').read_text(encoding='utf-8')
        self.assertIn('def forja_rollback(slug, execute=False, include_komodo=True):',client)
        self.assertIn('\"skip_komodo\": not bool(include_komodo)',client)
        cleanup=source[source.index('def _cleanup_already_deleted'):source.index('def execute(')]
        self.assertIn('forja_rollback(slug,execute=True,include_komodo=False)',cleanup.replace(' ',''))

    def test_runtime_missing_integration_is_idempotent_but_ambiguous_absence_is_not(self):
        import importlib.util,sys
        lib=Path('components/control-plane/srv/cloudif/lib').resolve()
        sys.path.insert(0,str(lib))
        try:
            spec=importlib.util.spec_from_file_location('u21_admin_delete_contract',lib/'cloudif_admin_project_delete.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        finally:
            sys.path.pop(0)
        explicit_missing={'ok':False,'status':422,'data':{'ok':False,'message':'Projeto não integrado no Komodo.'}}
        ambiguous_missing={'ok':False,'status':422,'data':{'ok':False,'message':'Ação não concluída ou ausência da stack não confirmada.'}}
        disconnected={'ok':False,'status':0,'error':'RemoteDisconnected','detail':'Remote end closed connection without response'}
        self.assertTrue(mod._runtime_destroy_satisfied(explicit_missing))
        self.assertFalse(mod._runtime_destroy_satisfied(ambiguous_missing))
        self.assertFalse(mod._runtime_destroy_satisfied(disconnected))

    def test_remote_delete_accepts_confirmed_forgejo_204_after_runtime_destroy(self):
        import importlib.util,sys
        lib=Path('components/control-plane/srv/cloudif/lib').resolve()
        sys.path.insert(0,str(lib))
        try:
            spec=importlib.util.spec_from_file_location('u21_admin_delete_remote_contract',lib/'cloudif_admin_project_delete.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        finally:
            sys.path.pop(0)
        legacy={'ok':False,'status':500,'data':{'ok':False,'forgejo':{'status':204,'deleted':True},'komodo':{'status':0}}}
        unconfirmed={'ok':False,'status':500,'data':{'ok':False,'forgejo':{'status':500,'deleted':False}}}
        self.assertTrue(mod._remote_delete_satisfied(legacy))
        self.assertFalse(mod._remote_delete_satisfied(unconfirmed))


if __name__=='__main__':
    unittest.main()
