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


if __name__=='__main__':
    unittest.main()
