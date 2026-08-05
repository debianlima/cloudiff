from pathlib import Path
import unittest


class HelpExternalConnectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = Path(
            "components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py"
        ).read_text()
        cls.focused = Path(
            "components/control-plane/current-apps/portal-current/cloudif_unique_pages98.py"
        ).read_text()
        cls.manual = Path("docs/manual-tecnico/13-ACESSO-EXTERNO.md").read_text()

    def test_help_lists_supported_https_connections(self):
        for marker in (
            "guia-conexoes",
            "Supabase para aplicações",
            "Git CLI",
            "Komodo",
            "ChatGPT",
            "Claude Code",
            "verifique com a TI",
        ):
            self.assertIn(marker, self.canonical)
        self.assertNotIn("cloudiff.duckdns.org:2222", self.canonical)
        self.assertNotIn("10.62.92.7:54400", self.canonical)

    def test_help_uses_canonical_mcp_endpoint(self):
        endpoint = "https://cloudiff.duckdns.org/cloudiff/mcp"
        self.assertIn(endpoint, self.canonical)
        self.assertIn(endpoint, self.focused)
        self.assertIn("POST", self.canonical)
        self.assertIn("--client-id", self.canonical)
        self.assertIn("--client-secret", self.focused)
        self.assertNotIn("rotas públicas <code>/mcp</code> ainda não estão publicadas", self.canonical)

    def test_project_connection_example_is_complete_without_secret(self):
        for marker in (
            "cloudif-laboratorio-de-hardware.git",
            "iff1742962-laboratoriodehardware.cloudiff.duckdns.org",
            "https://komodoiff.duckdns.org/",
            "https://cloudiff.duckdns.org/cloudiff/mcp",
        ):
            self.assertIn(marker, self.canonical)
        self.assertNotIn("YOUR-PASSWORD", self.canonical)
        self.assertNotIn("postgres.iff1742962-laboratoriodehardware", self.canonical)

    def test_oauth_loopback_is_explained(self):
        self.assertIn("127.0.0.1:&lt;porta&gt;", self.canonical)
        self.assertIn("não recebem redirecionamento no gateway", self.canonical)
        self.assertIn("não exige NAT no gateway", self.focused)

    def test_manual_distinguishes_get_from_post(self):
        self.assertIn("POST", self.manual)
        self.assertIn("GET /cloudiff/mcp", self.manual)
        self.assertIn("401", self.manual)


if __name__ == "__main__":
    unittest.main()
