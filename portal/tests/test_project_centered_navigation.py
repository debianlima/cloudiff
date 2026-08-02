import unittest

from portal.core.auth import Identity
from portal.ui import shell


class ProjectCenteredNavigationTest(unittest.TestCase):
    def setUp(self):
        self.identity = Identity(
            username="tester",
            email="tester@example.invalid",
            groups=frozenset({"CloudIF-Tenants"}),
        )

    def test_project_capabilities_live_under_projects(self):
        project_tabs = dict(shell._TAB_GROUPS["Projetos"])
        expected = {
            "projetos",
            "opcoes-projeto",
            "capacidades",
            "aprovacoes",
            "publicacao",
            "git",
            "monitor-promocoes",
            "operacao-producao",
            "monitor-transacoes",
            "monitor-filas",
            "monitor-telemetria",
            "reconciliacao",
            "agentes",
            "gestao-agentes",
            "documentacao-mcp",
        }
        self.assertEqual(set(project_tabs), expected)
        self.assertEqual(project_tabs["projetos"], "Todos os projetos")
        self.assertEqual(project_tabs["capacidades"], "Ferramentas do projeto")

    def test_only_database_and_platform_health_remain_separate(self):
        self.assertEqual(shell._TAB_GROUPS["Dados"], (("bancos", "Bancos e tenants"),))
        self.assertEqual(
            shell._TAB_GROUPS["Ferramentas"],
            (("monitor-saude", "Saúde da plataforma"),),
        )
        self.assertNotIn("Entrega", shell._TAB_GROUPS)
        self.assertNotIn("Operação", shell._TAB_GROUPS)
        self.assertNotIn("IA e automação", shell._TAB_GROUPS)

    def test_navigation_keeps_routes_and_opens_active_project_group(self):
        markup = shell._navigation(self.identity, "aprovacoes")
        self.assertIn('<summary class="nav-group-label">Projetos</summary>', markup)
        self.assertIn('href="/cloudiff/portal/?tab=aprovacoes" aria-current="page"', markup)
        project_group = markup.split('<summary class="nav-group-label">Projetos</summary>', 1)[0]
        self.assertTrue(project_group.endswith('<details class="nav-group" open>'))


if __name__ == "__main__":
    unittest.main()
