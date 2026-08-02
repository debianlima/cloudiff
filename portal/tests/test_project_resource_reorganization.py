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
        self.assertIn('Inspecionar ambiente',self.source)
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
        self.assertIn('Instalação, troca ou remoção exigem proposta no Forgejo',self.source)



    def test_projects_are_grouped_by_owner(self):
        self.assertIn('project-owner-group',self.source)
        self.assertIn("owner===current?'Meus projetos':'Projetos de '+owner",self.source)
        self.assertIn('data-project-owner',self.source)

    def test_runtime_inspection_uses_real_backend(self):
        self.assertIn('/api/project-runtime-inspection?slug=',self.source)
        self.assertIn('/komodo/project/runtime-inspect',self.source)
        for label in ('Repositório de código','Último commit','Servidor web externo','Servidor web interno','Containers inspecionados'):
            self.assertIn(label,self.source)
        self.assertIn('Instalação, troca ou remoção exigem proposta no Forgejo',self.source)



class ActiveProjectRendererContractTest(unittest.TestCase):
    def setUp(self):
        self.source=(Path(__file__).resolve().parents[2]/"components/control-plane/current-apps/portal-current/cloudif-admin-portal.py").read_text()

    def test_active_renderer_contains_owner_metadata_and_neutral_tenant_copy(self):
        source=(Path(__file__).resolve().parents[2]/"components/control-plane/current-apps/portal-current/cloudif-admin-portal.py").read_text()
        list_pos=source.find('<div id="cloudif-project-list"')
        start=source.rfind('def render_projects(user):',0,list_pos)
        end=source.find('def render_bancos(user):',list_pos)
        block=source[start:end]
        self.assertIn('data-project-owner=',block)
        self.assertIn('data-current-user=',block)
        self.assertIn('Nenhum tenant vinculado',block)
        self.assertNotIn('Sem banco: somente Git/Komodo',block)



    def test_repository_and_servers_are_explicit(self):
        for label in ('Repositório de código','Forgejo · encontrado','Abrir repositório','Último commit','Servidor web externo','Servidor web interno','Tecnologia web'):
            self.assertIn(label,self.source)
        self.assertIn('data-runtime-template',self.source)
        self.assertIn('Gerar plano',self.source)
        self.assertIn('/api/project-runtime-plan?slug=',self.source)
        self.assertIn("'side_effect_free':True",self.source)
        self.assertIn('Nenhuma alteração foi aplicada. Próxima etapa: proposta no Forgejo.',self.source)

    def test_owner_rule_matches_publication_grouping(self):
        self.assertIn('def _project_effective_owner',self.source)
        self.assertIn('project.get("owner") or project.get("created_by")',self.source)
        self.assertIn('FROM project_publications WHERE project_slug=? AND is_active=1',self.source)
        self.assertIn('data-project-owner=',self.source)

    def test_project_heading_is_management(self):
        self.assertIn('<h2>Gestão de projetos</h2>',self.source)


if __name__=='__main__':unittest.main()
