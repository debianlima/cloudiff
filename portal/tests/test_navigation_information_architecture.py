from pathlib import Path
import unittest

from portal.ui import shell


class NavigationInformationArchitectureTest(unittest.TestCase):
    def test_main_navigation_is_consolidated(self):
        self.assertEqual(tuple(shell._TAB_GROUPS), ("Painel geral", "Administração", "Ajuda"))
        self.assertEqual(
            shell._TAB_GROUPS["Painel geral"],
            (
                ("resumo", "Visão geral"),
                ("publicacao", "Publicações"),
                ("projetos", "Projetos"),
                ("bancos", "Bancos e tenants"),
                ("backup", "Backup"),
                ("agentes", "Conectores"),
            ),
        )
        self.assertNotIn("Projetos", tuple(shell._TAB_GROUPS))
        self.assertNotIn("Dados", tuple(shell._TAB_GROUPS))
        self.assertNotIn("Ferramentas", tuple(shell._TAB_GROUPS))

    def test_empty_tool_sections_are_removed(self):
        all_tabs = {tab for entries in shell._TAB_GROUPS.values() for tab, _label in entries}
        self.assertNotIn("gestao-agentes", all_tabs)
        self.assertNotIn("documentacao-mcp", all_tabs)
        self.assertNotIn("monitor-saude", all_tabs)

    def test_administration_contains_only_operational_entries(self):
        administration = dict(shell._TAB_GROUPS["Administração"])
        self.assertEqual(administration["admin"], "Administração do AD")
        self.assertEqual(administration["admin-manutencao"], "Serviços globais")
        self.assertEqual(administration["admin-excluir-projeto"], "Excluir projeto")
        self.assertEqual(len(administration), 3)

    def test_database_details_are_visible_sections_and_ad_shortcut_is_removed(self):
        source = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text(encoding='utf-8')
        self.assertIn('db96-services', source)
        self.assertIn('db96-permissions', source)
        self.assertIn('Serviços detectados', source)
        self.assertIn('Permissões do banco', source)
        self.assertIn("_ADMIN_LOOKUP_BOX, ''", source)
        self.assertNotIn('togglePanel(\'{acl_id}\')', source)

    def test_tenant_deletion_is_separate_and_protected(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text(encoding='utf-8')
        self.assertIn('EXCLUIR BANCO', source)
        self.assertIn('protected_platform_tenant', source)
        self.assertIn('linked_projects', source)
        self.assertIn('database-final.sql.gz', source)
        self.assertIn('docker", "compose"', source)


if __name__ == '__main__':
    unittest.main()
