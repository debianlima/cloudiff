import unittest
from pathlib import Path


class ProjectResourceReorganizationTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[2]
        source=self.root/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py'
        if not source.exists():
            source=self.root/'portal/legacy/cloudif-admin-portal.py'
        self.source=source.read_text()

    def test_project_tabs_are_focused_and_mcp_is_embedded(self):
        self.assertIn("{'Serviços':services,'Containers':containers,'Publicação':pubs,'Backups':backups,'Agente IA e MCP':agent}",self.source)
        project_block=self.source[self.source.index("const identityCards"):self.source.index("const bankMarker")]
        self.assertNotIn("{'Visão geral':overview",project_block,msg='A aba Visão geral não pode voltar aos projetos')
        self.assertIn("#project-identities article.project-card",project_block)
        self.assertIn("identityBySlug.get(slug)",project_block)
        identity_path=self.root/'components/control-plane/current-apps/portal-current/cloudif_project_identity_panel.py'
        if not identity_path.exists():
            identity_path=self.root/'portal/legacy/cloudif_project_identity_panel.py'
        identity=identity_path.read_text()
        self.assertIn("Rotacionar e exibir uma vez",identity)

    def test_backups_are_limited_and_expandable(self):
        self.assertIn("items.slice(0,5)",self.source)
        self.assertIn("Ver todos os backups",self.source)

    def test_containers_are_categorized_in_two_columns(self):
        for label in ('Banco de dados','Publicação ativa','Publicações inativas','Sistema'):
            self.assertIn(label,self.source)
        self.assertIn('grid-template-columns:repeat(2,minmax(0,1fr))',self.source)

    def test_global_resources_moved_to_maintenance(self):
        self.assertIn("if tab=='admin-manutencao': body=_admin_resources139_panel(user)+body",self.source)
        self.assertIn('Repositórios</a>',self.source)
        self.assertNotIn("if tab=='projetos': body=_admin_resources139_panel(user)+body",self.source)

    def test_framework_install_is_not_faked(self):
        self.assertIn('Ver framework detectado',self.source)
        self.assertNotIn('install_framework',self.source)



    def test_project_cards_are_compact_and_single_open(self):
        self.assertIn("card.classList.add('cpx-ready')",self.source)
        self.assertIn("projectCards.forEach(x=>{x.classList.remove('is-open')",self.source)
        self.assertIn("hint.setAttribute('aria-expanded','false')",self.source)
        self.assertIn("identityBySlug.get(slug)",self.source)
        self.assertIn("#project-identities{display:none}",self.source)

    def test_services_are_rebuilt_as_project_specific_cards(self):
        for label in ('Banco','Repositório','Komodo Publicação','Abrir site'):
            self.assertIn(label,self.source)
        self.assertIn('project-service-card',self.source)
        self.assertIn('A instalação automática ainda não está habilitada',self.source)


if __name__=='__main__':unittest.main()
