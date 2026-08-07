from pathlib import Path
import unittest


class FrozenSurfacesContractTests(unittest.TestCase):
    def test_overview_publications_and_projects_remain_frozen(self):
        coexist = Path("components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py").read_text()
        views = Path("portal/modules/overview/views.py").read_text()
        self.assertIn('tab in {"resumo", "visao-geral", "visão-geral"}', coexist)
        self.assertNotIn('tab == "publicacao" and not (query.get("project")', coexist)
        self.assertIn('resource_scope = (query.get("scope")', coexist)
        self.assertIn('tab=publicacao&project=', views)
        self.assertIn('tab=publicacao&amp;scope=others#other-user-sites', views)
        self.assertIn('Meus sites', views)
        self.assertIn('Meus bancos', views)
        self.assertIn('Saúde da plataforma', views)


    def test_banks_and_tenants_surface_remains_frozen(self):
        launcher = Path("components/control-plane/current-apps/portal-current/cloudif-admin-portal.py").read_text()
        base = Path("components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py").read_text()
        app_js = Path("portal/design/app.js").read_text()
        css = Path("portal/design/components.css").read_text()

        # Estrutura visual homologada.
        self.assertIn('db96-compact-tools', launcher)
        self.assertIn('<details class="db96-compact db96-services">', launcher)
        self.assertIn('data-tenant-permissions', launcher)
        self.assertIn('Serviços detectados', launcher)
        self.assertIn('Permissões do banco', launcher)
        self.assertIn('.db96-compact-tools', css)
        self.assertIn('.db96-service-list', css)

        # O agrupador moderno precisa vencer o details{background:white} legado.
        self.assertIn('.legacy-content .owner-resource-group{background:var(--surface)', css)
        self.assertIn('.legacy-content .owner-resource-group>summary{', css)
        self.assertIn('.legacy-content .owner-resource-items{display:grid;gap:var(--s3);padding:var(--s4);background:var(--surface);color:var(--ink)}', css)
        self.assertNotIn('\n.owner-resource-group{background:var(--surface)', css)

        # Agrupamento e identidade do proprietário.
        self.assertIn("owner===current?'Meus bancos'", app_js)
        self.assertIn('tenant-owner-row', base)
        self.assertIn('Dono do banco', base)
        self.assertIn('Protegido', base)
        self.assertIn('tenant_acl_remove_owner_blocked', base)

        # Autocomplete e validação obrigatória no provedor de identidade.
        self.assertIn('enableTenantPermissionAutocomplete', app_js)
        self.assertIn('identity_verified', app_js)
        self.assertIn('não encontrado no provedor de identidade', app_js)
        self.assertIn("input.setAttribute('aria-invalid','true')", app_js)
        self.assertIn('name="identity_verified"', base)
        self.assertIn('cloudif_ad_directory_module', base)
        self.assertIn('tenant_acl_add_rejected', base)
        self.assertIn('Selecione um usuário ou grupo retornado pelo provedor de identidade', base)

    def test_bank_adjustments_do_not_patch_frozen_renderers(self):
        launcher = Path("components/control-plane/current-apps/portal-current/cloudif-admin-portal.py").read_text()
        self.assertIn('db96-compact-tools', launcher)
        self.assertIn('data-tenant-permissions', launcher)
        self.assertNotIn('publication', launcher.lower().split('_tenant_details_new',1)[1].split('def _replace_all',1)[0])


if __name__ == "__main__":
    unittest.main()
