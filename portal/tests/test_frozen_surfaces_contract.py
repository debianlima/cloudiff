from pathlib import Path
import unittest


class FrozenSurfacesContractTests(unittest.TestCase):
    def test_overview_publications_and_projects_remain_frozen(self):
        coexist = Path("components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py").read_text()
        views = Path("portal/modules/overview/views.py").read_text()
        self.assertIn('tab in {"resumo", "visao-geral", "visão-geral"}', coexist)
        self.assertIn('body = overview_views.overview_body(data)', coexist)
        self.assertIn('tab == "publicacao" and not (query.get("project")', coexist)
        self.assertIn('tab=publicacao&project=', views)
        self.assertIn('Meus sites', views)
        self.assertIn('Meus bancos', views)
        self.assertIn('Saúde da plataforma', views)

    def test_bank_adjustments_do_not_patch_frozen_renderers(self):
        launcher = Path("components/control-plane/current-apps/portal-current/cloudif-admin-portal.py").read_text()
        self.assertIn('db96-compact-tools', launcher)
        self.assertIn('data-tenant-permissions', launcher)
        self.assertNotIn('publication', launcher.lower().split('_tenant_details_new',1)[1].split('def _replace_all',1)[0])


if __name__ == "__main__":
    unittest.main()
