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

    def test_global_navigation_contains_entities_only(self):
        self.assertEqual(shell._TAB_GROUPS["Projetos"], (("projetos", "Projetos"),))
        self.assertEqual(shell._TAB_GROUPS["Dados"], (("bancos", "Bancos e tenants"),))
        self.assertEqual(shell._TAB_GROUPS["Ferramentas"], (("monitor-saude", "Saúde da plataforma"),))
        global_tabs={tab for entries in shell._TAB_GROUPS.values() for tab,_ in entries}
        self.assertNotIn("aprovacoes",global_tabs)
        self.assertNotIn("documentacao-mcp",global_tabs)
        self.assertNotIn("monitor-telemetria",global_tabs)

    def test_project_navigation_is_grouped_by_user_goal(self):
        self.assertEqual(tuple(shell._PROJECT_NAV), ("Construir","Entregar","Operar","Automatizar"))
        project_tabs={tab for entries in shell._PROJECT_NAV.values() for tab,_ in entries}
        self.assertIn("git",project_tabs)
        self.assertIn("publicacao",project_tabs)
        self.assertIn("aprovacoes",project_tabs)
        self.assertIn("documentacao-mcp",project_tabs)

    def test_context_navigation_marks_active_route(self):
        markup=shell._project_navigation("aprovacoes")
        self.assertIn('aria-label="Navegação do projeto"',markup)
        self.assertIn('href="/cloudiff/portal/?tab=aprovacoes" aria-current="page"',markup)
        self.assertIn("Construir",markup)
        self.assertIn("Automatizar",markup)

    def test_frozen_publication_does_not_receive_context_navigation(self):
        doc=shell.render_legacy(self.identity,"publicacao","Publicação","<p>conteúdo</p>","","")
        self.assertNotIn('aria-label="Navegação do projeto"',doc)
        self.assertIn('data-legacy-tab="publicacao"',doc)


if __name__ == "__main__":
    unittest.main()
