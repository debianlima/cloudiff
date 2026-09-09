import unittest
from pathlib import Path


class ProjectResourceReorganizationTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[2]
        source=self.root/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
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

    def test_professor_can_read_global_services_without_admin_backup_mutation(self):
        root=self.root
        coexist=(root/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        legacy=(root/'portal/legacy/cloudif-admin-portal-base.py').read_text()
        for source in (self.source,legacy):
            focus=source[source.index('def _focus98_render'):source.index("if 'Portal' in globals()",source.index('def _focus98_render'))]
            self.assertIn("professor_global_services = tab == 'admin-manutencao' and 'CloudIF-Professor' in groups",focus)
        route=coexist[coexist.index('if path in PORTAL_PATHS and tab == "admin-manutencao"'):]
        route=route[:route.index('if path in PORTAL_PATHS and tab == "backup"')]
        self.assertIn('"cloudif-professor"',route)
        backup=coexist[coexist.index('def _backup_remote_admin_card'):coexist.index('def global_services_body')]
        self.assertIn("if not user.get('admin')",backup)

    def test_framework_install_is_not_faked(self):
        self.assertIn('Inspecionar ambiente',self.source)
        self.assertNotIn('install_framework',self.source)



    def test_project_cards_are_compact_and_single_open(self):
        self.assertIn('<details class="project-entry"',self.source)
        self.assertIn('project-entry-summary',self.source)
        self.assertIn("document.querySelectorAll('.project-entry[open]')",self.source)
        self.assertIn("if(x!==entry)x.open=false",self.source)
        self.assertIn("entry.open&&runtimePanel",self.source)
        self.assertIn("identityBySlug.get(slug)",self.source)
        self.assertIn("#project-identities{display:none}",self.source)

    def test_services_are_rebuilt_as_project_specific_cards(self):
        for label in ('Banco vinculado','Repositório Forge','Komodo Publicação SSH','Acessar SSH','Abrir site'):
            self.assertIn(label,self.source)
        self.assertIn('project-service-card',self.source)
        self.assertIn('Instalação, troca ou remoção exigem proposta no Forgejo',self.source)



    def test_projects_are_grouped_by_owner(self):
        self.assertIn('project-owner-group',self.source)
        self.assertIn("label='Meus projetos' if owner==user['username'] else f'Projetos de {owner}'",self.source)
        self.assertIn('data-project-owner',self.source)

    def test_runtime_inspection_uses_real_backend(self):
        self.assertIn('/api/project-runtime-inspection?slug=',self.source)
        self.assertIn('/komodo/project/runtime-inspect',self.source)
        for label in ('Repositório Forge','Abrir repositório','Último commit','Servidor web externo','Servidor web interno','Containers inspecionados'):
            self.assertIn(label,self.source)
        self.assertIn('Instalação, troca ou remoção exigem proposta no Forgejo',self.source)



class ActiveProjectRendererContractTest(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2]
        source=root/"components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py"
        if not source.exists():
            source=root/"portal/legacy/cloudif-admin-portal.py"
        self.source=source.read_text()

    def test_active_renderer_contains_owner_metadata_and_neutral_tenant_copy(self):
        source=self.source
        list_pos=source.find('<div id="cloudif-project-list"')
        start=source.rfind('def render_projects(user):',0,list_pos)
        end=source.find('def render_bancos(user):',list_pos)
        block=source[start:end]
        self.assertIn('data-project-owner=',block)
        self.assertIn('data-current-user=',block)
        self.assertIn('Nenhum tenant vinculado',block)
        self.assertNotIn('Sem banco: somente Git/Komodo',block)



    def test_repository_and_servers_are_explicit(self):
        for label in ('Repositório Forge','Abrir repositório','Último commit','Servidor web externo','Servidor web interno','Tecnologia web'):
            self.assertIn(label,self.source)
        self.assertIn('data-runtime-template',self.source)
        self.assertIn('Gerar plano',self.source)
        self.assertIn('/api/project-runtime-plan?slug=',self.source)
        self.assertIn("'side_effect_free':True",self.source)
        self.assertIn('Nenhuma alteração foi aplicada. Próxima etapa: proposta no Forgejo.',self.source)

    def test_owner_rule_matches_publication_grouping(self):
        self.assertIn('def _project_effective_owner',self.source)
        self.assertIn('value("owner") or value("created_by")',self.source)
        self.assertIn('FROM project_publications WHERE project_slug=? AND is_active=1',self.source)
        self.assertIn('data-project-owner=',self.source)

    def test_project_heading_is_management(self):
        self.assertIn('<h2>Projetos por usuário</h2>',self.source)



    def test_effective_owner_accepts_sqlite_row(self):
        self.assertIn('return project[key]',self.source)
        self.assertIn('return project.get(key)',self.source)
        self.assertIn('data-project-owner="{h(_project_effective_owner(p))}"',self.source)



    def test_project_services_reuse_publication_pattern(self):
        self.assertIn('publication-information project-service-grid',self.source)
        self.assertIn("service('Banco vinculado'",self.source)
        self.assertIn("service('Repositório Forge'",self.source)
        self.assertIn("service('Komodo Publicação SSH'",self.source)
        self.assertIn("'Acessar SSH'",self.source)
        self.assertNotIn('Ver catálogo homologado',self.source)

    def test_owner_groups_are_server_rendered(self):
        self.assertIn('grouped_projects_html',self.source)
        self.assertIn('<details class="project-owner-group"',self.source)
        self.assertNotIn('const groups=new Map()',self.source)

    def test_runtime_plan_uses_structured_wizard(self):
        for marker in ('technology-wizard','technology-wizard-steps','openTechnologyWizard','renderTechnologyPlan'):
            self.assertIn(marker,self.source)
        self.assertIn('progress max="4"',self.source)
        self.assertIn('Nenhuma alteração foi aplicada. Próxima etapa: proposta no Forgejo.',self.source)



class DefinitiveProjectManagementRendererTest(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2]
        source=root/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
        if not source.exists():
            source=root/'portal/legacy/cloudif-admin-portal.py'
        self.source=source.read_text()

    def test_final_renderer_replaces_legacy_project_line(self):
        start=self.source.rfind('# CloudIF definitive project management renderer BEGIN')
        self.assertGreaterEqual(start,0)
        block=self.source[start:]
        self.assertIn('render_projects=_pm197_render',block)
        self.assertNotIn('class="project-line"',block)
        self.assertIn('class="project-overview-strip"',block)
        self.assertIn('class="project-resource-list"',block)

    def test_u21_projects_use_selector_and_one_active_workspace(self):
        block=self.source[self.source.rfind('# CloudIF definitive project management renderer BEGIN'):]
        self.assertIn("def _pm197_render(user,selected='')",block)
        self.assertIn('class="project-workspace"',block)
        self.assertIn('class="project-index"',block)
        self.assertIn('data-project-filter',block)
        self.assertIn('class="project-row',block)
        self.assertIn('data-active-project=',block)
        self.assertIn('class="project-workspace-detail"',block)
        self.assertNotIn('<details class="project-final"',block)
        self.assertNotIn('class="project-owner-final"',block)

    def test_u21_project_query_selects_server_rendered_detail(self):
        block=self.source[self.source.rfind('# CloudIF definitive project management renderer BEGIN'):]
        self.assertIn("selected=(query.get('project') or [''])[0].strip()",block)
        self.assertIn('_pm197_render(user,selected=selected)',block)

    def test_final_renderer_keeps_project_actions(self):
        block=self.source[self.source.rfind('# CloudIF definitive project management renderer BEGIN'):]
        for label in ('Abrir Studio','Abrir repositório','Abrir terminal','Checar estado','Permissões','Publicar','Código'):
            self.assertIn(label,block)
        for removed in ('Sincronizar','Integrar','Editar projeto:'):
            self.assertNotIn(removed,block)
        self.assertIn('project_acl_module.render_acl_modal',block)
        self.assertIn('csrf_token',block)

    def test_final_renderer_is_collapsible_and_grouped(self):
        block=self.source[self.source.rfind('# CloudIF definitive project management renderer BEGIN'):]
        self.assertIn('class="project-workspace-detail"',block)
        self.assertIn('class="project-workspace-more"',block)
        self.assertIn("selected not in valid_slugs",block)
        self.assertIn("item['owner']==user['username']",block)


    def test_public_directory_and_acl_paths_are_supported(self):
        self.assertIn('/cloudiff/portal/api/ad-search',self.source)
        self.assertIn('/cloudiff/portal/action/project_acl',self.source)
        self.assertIn('project_acl_module.render_acl_modal',self.source)


if __name__=='__main__':unittest.main()
