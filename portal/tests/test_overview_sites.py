import tempfile
import unittest
from unittest import mock
from pathlib import Path
from portal.modules.overview.views import _network_graph, _site_card, sites_body


class OverviewSiteCardTest(unittest.TestCase):
    def test_published_site_keeps_new_tab_and_individual_manage_link(self):
        markup = _site_card({
            "project_slug": "library-test", "name": "Library", "stable_hostname": "library.example",
            "published": True,
        })
        self.assertIn('target="_blank"', markup)
        self.assertIn('tab=publicacao&project=library-test', markup)
        self.assertIn('Publicado', markup)

    def test_unpublished_site_has_manage_action_without_public_link(self):
        markup = _site_card({
            "project_slug": "draft-site", "name": "Draft", "stable_hostname": None,
            "published": False,
        })
        self.assertIn('Ainda não publicado', markup)
        self.assertIn('tab=publicacao&project=draft-site', markup)
        self.assertNotIn('target="_blank"', markup)




    def test_registry_tenants_include_own_and_count_other_academic_databases(self):
        from portal.modules.overview import service
        from types import SimpleNamespace
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            handle.write("tenant,created_at\n")
            handle.write("akadmin,now\n")
            handle.write("iff1742962,now\n")
            handle.write("iff1860746,now\n")
            registry = handle.name
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_handle:
            database = db_handle.name
        import sqlite3
        con = sqlite3.connect(database)
        con.executescript("""
            CREATE TABLE projects (slug TEXT, name TEXT, owner TEXT, status TEXT, tenant TEXT);
            CREATE TABLE project_acl (slug TEXT, subject_type TEXT, subject TEXT);
            CREATE TABLE project_publications (project_slug TEXT, stable_hostname TEXT, version_hostname TEXT, status TEXT, published_at TEXT, is_active INTEGER, id INTEGER);
            CREATE TABLE project_publication_aliases (project_slug TEXT, alias TEXT);
            CREATE TABLE project_tenants (project TEXT, tenant TEXT, is_primary INTEGER);
            CREATE TABLE tenant_acl (tenant TEXT, subject_type TEXT, subject TEXT);
        """)
        con.commit(); con.close()
        identity = SimpleNamespace(username="iff1742962", groups=("CloudIF-Tenants-Admin",))
        with mock.patch.object(service, "_DB", database), mock.patch.object(service, "_TENANTS_REGISTRY", registry):
            resources = service.academic_resources(identity)
        self.assertEqual([item["tenant"] for item in resources["databases"]], ["iff1742962"])
        self.assertEqual(resources["other_databases"], 1)

    def test_sites_page_uses_canonical_empty_state(self):
        markup = sites_body({"resources": {"sites": []}})
        self.assertIn("Meus sites", markup)
        self.assertIn("Você ainda não publicou um site", markup)
        self.assertIn("Ver meus projetos", markup)

    def test_network_graph_explains_direction_and_uses_comparative_bars(self):
        markup = _network_graph({
            "network_rx_bps": 2000,
            "network_tx_bps": 1000,
            "network_rx_label": "2.0 KB/s",
            "network_tx_label": "1.0 KB/s",
        })
        self.assertIn("Tráfego de rede", markup)
        self.assertIn("Taxa atual recebida e enviada pelo servidor", markup)
        self.assertIn("Recebimento", markup)
        self.assertIn("Envio", markup)
        self.assertIn('width:100%', markup)
        self.assertIn('width:50%', markup)


    def test_publication_submit_preserves_operation_before_disabling_button(self):
        source = (Path(__file__).resolve().parents[1] / "design" / "app.js").read_text()
        self.assertIn("event.submitter", source)
        self.assertIn("operation.name=button.name", source)
        self.assertIn("operation.value=button.value", source)
        self.assertLess(source.index("operation.value=button.value"), source.index("button.disabled=true"))


if __name__ == "__main__":
    unittest.main()
