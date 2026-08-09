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
        for value in ("oauth-authorization-server", "oauth-protected-resource", "/cloudiff/mcp/oauth/authorize", "/cloudiff/mcp/oauth/resume", "/cloudiff/mcp/oauth/token", "/cloudiff/mcp/oauth/revoke", "RESOURCE_METADATA_URL"):
            self.assertIn(value, self.gateway)
        self.assertIn("location = /.well-known/oauth-protected-resource", self.router)
        self.assertIn("proxy_pass http://127.0.0.1:18198/.well-known/oauth-protected-resource", self.router)

    def test_mcp_tools_advertise_oauth_and_runtime_emits_standard_challenge(self):
        for marker in ("_tool['securitySchemes']=[{'type':'oauth2','scopes':['mcp']}]", "mcp/www_authenticate", "WWW-Authenticate", "resource_metadata=", "send_mcp_auth_required", "send_oauth_unauthorized"):
            self.assertIn(marker,self.gateway)
        self.assertIn("if not authenticated and method=='initialize'",self.gateway)
        self.assertIn("if not authenticated and method=='tools/list'",self.gateway)
        self.assertEqual(self.gateway.count("'serverInfo':{'name':'cloudif-mcp-gateway','version':'1.0.0'}"),2)
        self.assertIn("if not authenticated:return self.send_mcp_auth_required(rid)",self.gateway)

    def test_oauth_resource_indicator_is_bound_to_code_and_token(self):
        for marker in ("resource=(query.get('resource') or [MCP_RESOURCE])[0]", "resource!=MCP_RESOURCE", "'resource':request['resource']", "resource=(form.get('resource') or [''])[0]", "resource!=row.get('resource')", "resource==saved.get('resource')"):
            self.assertIn(marker,self.gateway)

    def test_public_client_pkce_and_confidential_compatibility(self):
        for value in ("'none'", "client_secret_post", "client_secret_basic", "code_challenge_methods_supported", "pkce_valid=flow=='pkce'", "_pkce_ok", "refresh_token"):
            self.assertIn(value, self.gateway)
        self.assertIn("row if row.get('public_client')", self.gateway)
        self.assertIn("if _callback_mode(redirect)!='chatgpt_actions' or not secret", self.gateway)
        self.assertIn("client={**row,**validated} if validated else None", self.gateway)
        self.assertIn("saved) if saved and saved.get('client_id')", self.gateway)

    def test_authorization_uses_nonce_before_authentik_and_acl_after_resume(self):
        for value in ("X-authentik-username", "X-authentik-groups", "_public_oauth_client", "project.get('owner')", "subject_type", "project_denied", "OAUTH_LOGIN_REQUESTS", "OAUTH_LOGIN_TTL=300", "_oauth_authorize_preflight"):
            self.assertIn(value, self.gateway)
        self.assertIn("location = /cloudiff/mcp/oauth/authorize", self.router)
        self.assertIn("location = /cloudiff/mcp/oauth/resume", self.router)
        authorize=self.router[self.router.index("location = /cloudiff/mcp/oauth/authorize"):self.router.index("location = /cloudiff/mcp/oauth/resume")]
        self.assertNotIn("auth_request /cloudiff/portal-auth",authorize)
        resume=self.router[self.router.index("location = /cloudiff/mcp/oauth/resume"):self.router.index("location = /cloudiff/mcp {",self.router.index("location = /cloudiff/mcp/oauth/resume"))]
        self.assertIn("auth_request /cloudiff/portal-auth",resume)
        self.assertIn("error_page 401 = @cloudif_authentik_signin_v244",resume)
        self.assertIn("proxy_set_header X-authentik-username",resume)

    def test_public_oauth_never_requires_or_reconstructs_project_secret(self):
        self.assertIn("if not oauth.get('public_client')", self.gateway)
        self.assertIn("path='/v1/authorize-public'", self.gateway)
        self.assertIn("if p=='/v1/authorize-public'", self.registry)
        public_block = self.registry[self.registry.index("if p=='/v1/authorize-public'"):self.registry.index("if p=='/v1/authorize':")]
        self.assertNotIn("token_hash", public_block)
        self.assertIn("authorized_user", public_block)
        self.assertIn("project_slugs", public_block)

    def test_callback_allowlist(self):
        for value in ("claude.ai", "chatgpt.com", "chat.openai.com", "127.0.0.1", "localhost"):
            self.assertIn(value, self.gateway)

    def test_chatgpt_actions_callback_has_isolated_non_pkce_flow(self):
        for marker in (
            "return 'chatgpt_actions'",
            "flow=='chatgpt_actions' and not challenge and not method",
            "ttl=180 if request['oauth_flow']=='chatgpt_actions' else 300",
            "_callback_mode(redirect)!='chatgpt_actions'",
        ):
            self.assertIn(marker, self.gateway)
        callback_block = self.gateway[self.gateway.index('def _callback_mode'):self.gateway.index('def _validate_client_secret')]
        self.assertIn("u.netloc in {'chat.openai.com','chatgpt.com'}", callback_block)
        self.assertIn("/aip/g-", callback_block)

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

    def test_chatgpt_file_picker_bridge_is_registered_as_mcp_app(self):
        for marker in (
            "ARTIFACT_UPLOAD_WIDGET_URI='ui://cloudiff/artifact-upload-v1.html'",
            "'mimeType':'text/html;profile=mcp-app'",
            "'ui':{'resourceUri':ARTIFACT_UPLOAD_WIDGET_URI,'visibility':['model','app']}",
            "'name':'workspace.artifact.upload.file.select'",
            "'name':'workspace.artifact.upload.file.resolve'",
            "'ui':{'visibility':['app']}",
            "selectFiles",
            "getFileDownloadUrl",
            "callTool('workspace.artifact.upload.file.resolve'",
        ):
            self.assertIn(marker,self.gateway)

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
        self.assertIn("action_available=_action_visible_tool_names(available)", schema_block)
        self.assertIn("read_tools=[x for x in action_available if x in READ_ONLY_TOOLS]", schema_block)
        self.assertIn("write_tools=[x for x in action_available if x not in READ_ONLY_TOOLS]", schema_block)
        self.assertNotIn("base+'/artifact/import'", schema_block)
        self.assertNotIn("'operationId':'importCloudIFFArtifact'", schema_block)
        self.assertNotIn("'openaiFileIdRefs'", schema_block)
        self.assertNotIn("'x-openai-isConsequential':False", schema_block[schema_block.index("base+'/write'"):])

    def test_actions_components_define_object_properties(self):
        block = self.gateway[self.gateway.index('def _action_schema'):self.gateway.index('def _privacy_html')]
        self.assertIn("'schemas':schemas", block)
        self.assertIn("'properties':{}", block)
        self.assertIn("'properties':{", block)
        self.assertIn("'#/components/schemas/ActionResponse'", block)
        self.assertIn("'#/components/schemas/ReadToolRequest'", block)
        self.assertIn("'#/components/schemas/WriteToolRequest'", block)

    def test_actions_bridge_forces_project_slug_and_separates_read_from_write(self):
        for marker in (
            "if 'slug' in props:clean['slug']=identity['project_slug']",
            "write_tool_not_allowed_on_read_endpoint",
            "read_tool_not_allowed_on_write_endpoint",
            "project_identity_invalid",
            "tool_denied",
        ):
            self.assertIn(marker, self.gateway)

    def test_file_tools_are_first_class_mcp_and_never_actions_dispatched(self):
        for marker in (
            "MCP_ONLY_TOOLS={'workspace.artifact.import','workspace.artifact.upload.file','workspace.artifact.upload.file.select','workspace.artifact.upload.file.resolve'}",
            "'openai/fileParams':['file']",
            "'title':'Importar arquivo da conversa'",
            "'file':{'type':'object'",
            "'schema_mode':'inline_openai_file_object'",
            "'name':'workspace.artifact.upload.file'",
            "'requires_portal_cookie':False",
            "if tool in MCP_ONLY_TOOLS:raise PermissionError('mcp_only_tool_requires_direct_connection')",
            "'mcp_call_shape':'top_level_arguments'",
            "'actions_dispatcher_allowed':False",
            "'reason':'first_class_mcp_file_tool'",
        ):
            self.assertIn(marker,self.gateway)
        schema_block=self.gateway[self.gateway.index('def _action_schema'):self.gateway.index('def _privacy_html')]
        self.assertIn("'version':'1.5.0'",schema_block)
        self.assertNotIn("base+'/artifact/import'",schema_block)
        self.assertNotIn("'operationId':'importCloudIFFArtifact'",schema_block)
        self.assertIn("workspace.artifact.import e workspace.artifact.upload.file são ferramentas MCP de primeira classe",schema_block)
        self.assertNotIn("path=='/cloudiff/mcp/actions/v1/artifact/import'",self.gateway)
        self.assertNotIn("_action_rpc(identity,'workspace.artifact.import',args)",self.gateway)
        self.assertIn("result=_project_tool_catalog(identity['tools'])",self.gateway)

    def test_project_list_is_filtered_by_agent_projects(self):
        self.assertIn("allowed=set(authz.get('project_slugs') or [])", self.gateway)
        self.assertIn("x.get('slug') in allowed", self.gateway)


if __name__ == "__main__":
    unittest.main()
