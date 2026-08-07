from pathlib import Path
import ast
import unittest

SOURCE = Path('components/control-plane/current-apps/project-capabilities-current/cloudif-project-capabilities.py').read_text()
TREE = ast.parse(SOURCE)
WANTED = {'assignment_nodes', 'safe_value', 'assigned'}
NODES = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
MODULE = ast.Module(body=NODES, type_ignores=[])
ast.fix_missing_locations(MODULE)
NS = {'ast': ast}
exec(compile(MODULE, '<capability-catalog-parser>', 'exec'), NS)
ASSIGNED = NS['assigned']


class ProjectCapabilitiesCatalogParserTests(unittest.TestCase):
    def test_literal_assignments_remain_supported(self):
        tree = ast.parse("TOOLS=[{'name':'project.get'}]\nSCOPE={'project.get':'project:read'}")
        self.assertEqual(ASSIGNED(tree, 'TOOLS'), [{'name': 'project.get'}])
        self.assertEqual(ASSIGNED(tree, 'SCOPE'), {'project.get': 'project:read'})

    def test_named_list_concatenation_is_resolved_recursively(self):
        tree = ast.parse("BASIC=['a']\nADMIN=['b']\nALL=BASIC+ADMIN\nPROJECT=['root']+ALL")
        self.assertEqual(ASSIGNED(tree, 'PROJECT'), ['root', 'a', 'b'])

    def test_current_mcp_tools_with_named_schema_fragments_are_resolvable(self):
        gateway = ast.parse(Path('components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text())
        tools = ASSIGNED(gateway, 'TOOLS')
        self.assertGreaterEqual(len(tools), 130)
        self.assertTrue(all(isinstance(item, dict) and item.get('name') for item in tools))
        self.assertIn('project.toolchain.validate', {item['name'] for item in tools})

    def test_calls_and_attributes_are_rejected(self):
        for source in ("X=list(['a'])", "X=os.environ", "X=[x for x in []]"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, 'catalog_expression_not_allowed'):
                    ASSIGNED(ast.parse(source), 'X')

    def test_unknown_names_and_cycles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'catalog_name_not_assigned'):
            ASSIGNED(ast.parse('X=UNKNOWN'), 'X')
        with self.assertRaisesRegex(ValueError, 'catalog_assignment_cycle'):
            ASSIGNED(ast.parse('A=B\nB=A'), 'A')

    def test_current_agent_registry_admin_scopes_are_resolvable(self):
        registry = ast.parse(Path('components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py').read_text())
        scopes = ASSIGNED(registry, 'PROJECT_ADMIN_SCOPES')
        self.assertIsInstance(scopes, list)
        self.assertIn('project:read', scopes)
        self.assertIn('supabase:database-read', scopes)
        self.assertIn('supabase:change-execute', scopes)
        self.assertEqual(len(scopes), len(set(scopes)))


if __name__ == '__main__':
    unittest.main()
