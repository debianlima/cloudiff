from pathlib import Path
import ast
import unittest


class MCPOAuthContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway_path = Path("components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py")
        cls.gateway = cls.gateway_path.read_text()
        cls.registry = Path("components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py").read_text()
        cls.router = Path("components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh").read_text()

    def test_discovery_and_oauth_endpoints(self):
        for value in ("oauth-authorization-server", "oauth-protected-resource", "/cloudiff/mcp/oauth/authorize", "/cloudiff/mcp/oauth/token", "/cloudiff/mcp/oauth/revoke"):
            self.assertIn(value, self.gateway)

    def test_public_client_pkce_and_confidential_compatibility(self):
        for value in ("'none'", "client_secret_post", "client_secret_basic", "code_challenge_methods_supported", "method!='S256'", "_pkce_ok", "refresh_token"):
            self.assertIn(value, self.gateway)
        self.assertIn("row if row.get('public_client')", self.gateway)
        self.assertIn("saved) if saved and saved.get('client_id')", self.gateway)

    def test_authorization_is_bound_to_authentik_and_project_acl(self):
        for value in ("X-authentik-username", "X-authentik-groups", "_public_oauth_client", "project.get('owner')", "subject_type", "project_denied"):
            self.assertIn(value, self.gateway)
        self.assertIn("auth_request /cloudiff/portal-auth", self.router)
        self.assertIn("location = /cloudiff/mcp/oauth/authorize", self.router)
        self.assertIn("proxy_set_header X-authentik-username", self.router)

    def test_public_oauth_never_requires_or_reconstructs_project_secret(self):
        self.assertIn("if not oauth.get('public_client')", self.gateway)
        self.assertIn("path='/v1/authorize-public'", self.gateway)
        self.assertIn("if p=='/v1/authorize-public'", self.registry)
        public_block = self.registry[self.registry.index("if p=='/v1/authorize-public'"):self.registry.index("if p=='/v1/authorize':")]
        self.assertNotIn("token_hash", public_block)
        self.assertIn("authorized_user", public_block)
        self.assertIn("project_slugs", public_block)

    def test_callback_allowlist(self):
        for value in ("claude.ai", "chatgpt.com", "127.0.0.1", "localhost"):
            self.assertIn(value, self.gateway)

    def test_tools_have_conservative_mcp_annotations(self):
        tree = ast.parse(self.gateway)
        self.assertIn("READ_ONLY_TOOLS", self.gateway)
        self.assertIn("DESTRUCTIVE_TOOLS", self.gateway)
        for value in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            self.assertIn(value, self.gateway)
        read_block = self.gateway[self.gateway.index("READ_ONLY_TOOLS="):self.gateway.index("DESTRUCTIVE_TOOLS=")]
        self.assertIn("'project.get'", read_block)
        self.assertNotIn("'forgejo.proposal.merge'", read_block)
        destructive = self.gateway[self.gateway.index("DESTRUCTIVE_TOOLS="):self.gateway.index("OPEN_WORLD_PREFIXES=")]
        self.assertIn("'forgejo.proposal.delete-branch'", destructive)
        self.assertIn("'deployment.rollback-test'", destructive)
        self.assertIsNotNone(tree)

    def test_resources_and_prompts_are_bound_to_the_requested_project(self):
        self.assertIn("if method=='resources/read'", self.gateway)
        self.assertIn("resource_uri.startswith('cloudiff://guide/project/')", self.gateway)
        self.assertIn("elif method=='prompts/get'", self.gateway)
        self.assertIn("slug=str((params.get('arguments') or {}).get('slug') or '')", self.gateway)

    def test_actions_schema_is_project_specific_and_conservative(self):
        for marker in (
            "def _action_schema(client_id):",
            "'/cloudiff/mcp/actions/v1/project'",
            "'/cloudiff/mcp/actions/v1/read'",
            "'/cloudiff/mcp/actions/v1/write'",
            "'x-openai-isConsequential':False",
            "'x-openai-isConsequential':True",
            "'/cloudiff/mcp/privacy'",
            "openapi':'3.1.0",
        ):
            self.assertIn(marker, self.gateway)
        schema_block = self.gateway[self.gateway.index('def _action_schema'):self.gateway.index('def _privacy_html')]
        self.assertIn("read_tools=[x for x in available if x in READ_ONLY_TOOLS]", schema_block)
        self.assertIn("write_tools=[x for x in available if x not in READ_ONLY_TOOLS]", schema_block)
        self.assertNotIn("'x-openai-isConsequential':False", schema_block[schema_block.index("base+'/write'"):])

    def test_actions_bridge_forces_project_slug_and_separates_read_from_write(self):
        for marker in (
            "if 'slug' in props:clean['slug']=identity['project_slug']",
            "write_tool_not_allowed_on_read_endpoint",
            "read_tool_not_allowed_on_write_endpoint",
            "project_identity_invalid",
            "tool_denied",
        ):
            self.assertIn(marker, self.gateway)

    def test_project_list_is_filtered_by_agent_projects(self):
        self.assertIn("allowed=set(authz.get('project_slugs') or [])", self.gateway)
        self.assertIn("x.get('slug') in allowed", self.gateway)


if __name__ == "__main__":
    unittest.main()
