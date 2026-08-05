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
        cls.navigation = Path(
            "components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py"
        ).read_text()
        cls.manual = Path("docs/manual-tecnico/13-ACESSO-EXTERNO.md").read_text()

    def test_help_lists_supported_https_connections(self):
        for marker in (
            "guia-conexoes",
            "Conectar aplicações e ferramentas",
            "supabase-js",
            "Git CLI",
            "Komodo por HTTPS",
            "MCP por HTTPS",
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
        self.assertIn("MCP por HTTPS", self.canonical)
        self.assertIn("MCP por HTTPS", self.focused)
        self.assertNotIn("--client-id", self.canonical)
        self.assertNotIn("--client-secret", self.focused)
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

    def test_help_excludes_unlisted_connection_methods(self):
        for marker in (
            "127.0.0.1:&lt;porta&gt;",
            "--client-id",
            "--client-secret",
            "PostgreSQL direto",
            "Git SSH",
        ):
            self.assertNotIn(marker, self.canonical)
            self.assertNotIn(marker, self.focused)

    def test_help_navigation_names_only_supported_connections(self):
        self.assertIn("Aplicações, Git, Komodo e MCP", self.navigation)
        self.assertNotIn("ChatGPT, Claude e Llama", self.navigation)

    def test_manual_distinguishes_get_from_post(self):
        self.assertIn("POST", self.manual)
        self.assertIn("GET /cloudiff/mcp", self.manual)
        self.assertIn("401", self.manual)


if __name__ == "__main__":
    unittest.main()
