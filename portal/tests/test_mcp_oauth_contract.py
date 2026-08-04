from pathlib import Path
import unittest

class MCPOAuthContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path("components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py").read_text()
    def test_discovery_and_oauth_endpoints(self):
        for value in ("oauth-authorization-server","oauth-protected-resource","/cloudiff/mcp/oauth/authorize","/cloudiff/mcp/oauth/token","/cloudiff/mcp/oauth/revoke"):
            self.assertIn(value,self.source)
    def test_confidential_client_and_pkce(self):
        for value in ("client_secret_post","client_secret_basic","code_challenge_methods_supported","_pkce_ok","refresh_token"):
            self.assertIn(value,self.source)
    def test_callback_allowlist(self):
        for value in ("claude.ai","chatgpt.com","127.0.0.1","localhost"):
            self.assertIn(value,self.source)
    def test_oauth_reuses_agent_authorization(self):
        self.assertIn("AGENT_URL+'/v1/authorize'",self.source)
        self.assertIn("project:read",self.source)

if __name__=="__main__":unittest.main()
