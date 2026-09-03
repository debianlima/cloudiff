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


if __name__=='__main__':
    unittest.main()
