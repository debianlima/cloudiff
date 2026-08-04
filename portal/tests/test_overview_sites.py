import unittest
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
