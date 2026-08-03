from __future__ import annotations

import re
import unittest

from portal.core.auth import Identity
from portal.core.legacy_shell import parse_legacy, scope_css, transform
from portal.ui import shell


LEGACY = """<!doctype html><html><head><title>Projetos</title>
<style>:root{--old:#168821}body{background:#fff}.card,.box{padding:10px}@media(max-width:700px){button{width:100%}}</style>
<script>window.keepFunctional=true;</script>
<script id="cloudif-enterprise-navigation-js">window.oldNav=true;</script>
<script id="cloudif-ui142-script">window.oldUi=true;</script>
</head><body><header class="header">old</header><nav class="enterprise-nav">old</nav>
<main id="conteudo-principal"><form method="post" action="/action/project_action"><input name="csrf_token" value="abc"><button>Salvar</button></form><div id="project">conteúdo</div></main>
<footer class="footer">old</footer></body></html>"""


class LegacyShellTest(unittest.TestCase):
    def setUp(self) -> None:
        self.student = Identity("aluno", "a@example.invalid", frozenset({"CloudIF-Aluno"}))
        self.admin = Identity("admin", "a@example.invalid", frozenset({"CloudIF-Tenants-Admin"}))

    def test_parser_preserves_forms_and_functional_script(self):
        page = parse_legacy(LEGACY, "projetos")
        self.assertIn('action="/action/project_action"', page.body)
        self.assertIn('name="csrf_token"', page.body)
        self.assertIn("keepFunctional", page.scripts)
        self.assertNotIn("oldNav", page.scripts)
        self.assertNotIn("oldUi", page.scripts)

    def test_css_is_scoped(self):
        css = scope_css(":root{--x:1}body{margin:0}.card,.box{padding:1px}@media(max-width:2px){button{width:1px}}")
        self.assertIn(".legacy-content{--x:1}", css)
        self.assertIn(".legacy-content{margin:0}", css)
        self.assertIn(".legacy-content .card,.legacy-content .box", css)
        self.assertIn(".legacy-content button", css)

    def test_student_never_receives_admin_navigation(self):
        doc = transform(LEGACY, self.student, "projetos")
        self.assertIn('<nav class="nav"', doc)
        self.assertNotIn("admin-usuarios", doc)
        self.assertNotIn(">Administração<", doc)
        self.assertIn('aria-current="page">Projetos</a>', doc)

    def test_admin_receives_global_entities_only(self):
        doc = transform(LEGACY, self.admin, "admin-usuarios")
        expected = {
            "resumo", "projetos", "bancos", "monitor-saude",
            "admin-usuarios", "admin-politicas", "admin-identidades", "admin-configuracoes",
            "admin-auditoria", "admin-manutencao", "admin-excluir-projeto", "ajuda", "ajuda-token", "ajuda-conectar",
            "ajuda-aprovacoes", "ajuda-ferramentas",
        }
        actual = set(re.findall(r"\?tab=([a-z0-9-]+)", doc))
        self.assertEqual(expected, actual)
        self.assertIn('aria-current="page">Usuários</a>', doc)

    def test_context_route_receives_all_project_tools(self):
        doc = transform(LEGACY, self.admin, "aprovacoes")
        expected = {tab for entries in shell._PROJECT_NAV.values() for tab, _label in entries}
        actual = set(re.findall(r"\?tab=([a-z0-9-]+)", doc))
        self.assertTrue(expected.issubset(actual))
        self.assertIn('aria-label="Navegação do projeto"', doc)


    def test_old_shell_is_not_embedded(self):
        doc = transform(LEGACY, self.admin, "projetos")
        self.assertNotIn("<header class=\"header\">old", doc)
        self.assertNotIn("<nav class=\"enterprise-nav\">old", doc)
        self.assertNotIn("<footer class=\"footer\">old", doc)
        self.assertIn("conteúdo", doc)


if __name__ == "__main__":
    unittest.main()
