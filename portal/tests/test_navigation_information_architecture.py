from pathlib import Path
import unittest

from portal.ui import shell


class NavigationInformationArchitectureTest(unittest.TestCase):
    def test_main_navigation_has_no_duplicate_projects_or_data_sections(self):
        self.assertEqual(tuple(shell._TAB_GROUPS), ("Painel", "Ferramentas", "Administração", "Ajuda"))
        self.assertEqual(
            shell._TAB_GROUPS["Painel"],
            (("resumo", "Visão geral"), ("projetos", "Projetos"), ("bancos", "Bancos e tenants")),
        )
        self.assertNotIn("Projetos", tuple(shell._TAB_GROUPS))
        self.assertNotIn("Dados", tuple(shell._TAB_GROUPS))

    def test_tools_are_promoted_to_the_main_navigation(self):
        tools = dict(shell._TAB_GROUPS["Ferramentas"])
        self.assertEqual(tools["opcoes-projeto"], "Projeto")
        self.assertEqual(tools["agentes"], "Conectores")
        self.assertEqual(tools["gestao-agentes"], "Agentes AGIA")
        self.assertEqual(tools["documentacao-mcp"], "Gerenciamento MCP")
        project_tabs = {tab for entries in shell._PROJECT_NAV.values() for tab, _label in entries}
        self.assertTrue(set(tools).isdisjoint(project_tabs))

    def test_ad_and_platform_health_are_administration_entries(self):
        administration = dict(shell._TAB_GROUPS["Administração"])
        self.assertEqual(administration["admin"], "Administração do AD")
        self.assertEqual(administration["monitor-saude"], "Saúde da plataforma")

    def test_database_details_are_visible_sections_and_ad_shortcut_is_removed(self):
        source = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text(encoding='utf-8')
        self.assertIn('db96-services', source)
        self.assertIn('db96-permissions', source)
        self.assertIn('Serviços detectados', source)
        self.assertIn('Permissões do banco', source)
        self.assertIn("_ADMIN_LOOKUP_BOX, ''", source)
        self.assertNotIn('togglePanel(\'{acl_id}\')', source)


if __name__ == '__main__':
    unittest.main()
