from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / 'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
BROKER = ROOT / 'components/control-plane/current-apps/supabase-mcp-broker-current/cloudif-supabase-mcp-broker.py'
REGISTRY = ROOT / 'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING = ROOT / 'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
GATEWAY_UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service'
BROKER_UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-supabase-mcp-broker.service'
GUIDE = ROOT / 'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
GUIDE_LEGACY = ROOT / 'portal/legacy/cloudif_ai_agents_guide.py'
APPROVAL_PANEL = ROOT / 'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
APPROVAL_PANEL_LEGACY = ROOT / 'portal/legacy/cloudif_approval_panel.py'

READ_TOOLS = {
    'supabase.tables.list', 'supabase.records.select', 'supabase.sql.query',
    'supabase.auth.users.list', 'supabase.storage.buckets.list',
    'supabase.storage.objects.list', 'supabase.storage.object.read',
    'supabase.secrets.list', 'supabase.rls.inspect', 'supabase.schema.inspect',
    'supabase.logs.read', 'supabase.admin.config.read',
}
PLAN_TOOLS = {
    'supabase.records.change.plan', 'supabase.sql.change.plan',
    'supabase.rls.change.plan', 'supabase.schema.change.plan',
    'supabase.secrets.read.plan',
}
WRITE_TOOLS = {'approval.request-supabase-operation', 'supabase.operation.execute'}


class SupabaseMCPDatabaseConnectorContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway = GATEWAY.read_text()
        cls.broker = BROKER.read_text()
        cls.registry = REGISTRY.read_text()
        cls.onboarding = ONBOARDING.read_text()
        cls.guide = GUIDE.read_text()
        cls.approval = APPROVAL_PANEL.read_text()

    def test_existing_public_mcp_and_oauth_are_reused(self):
        self.assertIn("MCP_RESOURCE=PUBLIC_ORIGIN+'/cloudiff/mcp'", self.gateway)
        self.assertIn("'/cloudiff/mcp/oauth/authorize'", self.gateway)
        self.assertIn("'/cloudiff/mcp/oauth/token'", self.gateway)
        self.assertNotIn('/cloudiff/database-mcp/oauth', self.gateway)
        self.assertIn("'same_mcp_endpoint':True", self.onboarding)
        self.assertIn("'additional_authentication':False", self.onboarding)
        self.assertIn('As ferramentas de banco usam o mesmo OAuth e Client ID do projeto', self.guide)

    def test_requested_database_tools_are_in_the_existing_catalog(self):
        for name in sorted(READ_TOOLS | PLAN_TOOLS | WRITE_TOOLS):
            self.assertIn("'name':'" + name + "'", self.gateway, name)
        ast.parse(self.gateway)

    def test_only_queries_and_plans_are_read_only(self):
        read_block = self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        for name in READ_TOOLS | PLAN_TOOLS:
            self.assertIn("'" + name + "'", read_block, name)
        for name in WRITE_TOOLS:
            self.assertNotIn("'" + name + "'", read_block, name)
        destructive = self.gateway[self.gateway.index('DESTRUCTIVE_TOOLS='):self.gateway.index('OPEN_WORLD_PREFIXES=')]
        self.assertIn("'supabase.operation.execute'", destructive)

    def test_tools_use_project_scopes_and_existing_registry_identity(self):
        for scope in (
            'supabase:database-read', 'supabase:auth-read', 'supabase:storage-read',
            'supabase:admin-read', 'supabase:change-plan',
            'approval:request-supabase', 'supabase:change-execute',
        ):
            self.assertIn(scope, self.registry)
            self.assertIn(scope, self.gateway)
        self.assertIn("for role,scopes in ROLE_SCOPES.items()", self.registry)
        self.assertIn("update clients set scopes_json=?,environment=? where role_profile=?", self.registry)
        reconcile = self.registry[self.registry.index("if p.startswith('/v1/clients/') and p.endswith('/reconcile')"):]
        self.assertIn('token_hash_preserved', reconcile)
        self.assertIn('created_at_preserved', reconcile)
        self.assertIn('token_returned', reconcile)

    def test_oauth_session_carries_user_group_and_project_role(self):
        block = self.gateway[self.gateway.index('def _public_oauth_client'):self.gateway.index('def _callback_mode')]
        for marker in ('authorized_groups', 'project_role', 'PROJECT_ROLE_RANK', "kind=='group'", "kind=='user'"):
            self.assertIn(marker, block)
        authz = self.gateway[self.gateway.index('def authorize_client'):self.gateway.index('def redirect')]
        self.assertIn("data.update({'authorized_user'", authz)
        self.assertIn("'authorized_groups'", authz)
        self.assertIn("'project_role'", authz)

    def test_broker_is_internal_only_and_has_no_second_user_auth(self):
        unit = BROKER_UNIT.read_text()
        gateway_unit = GATEWAY_UNIT.read_text()
        self.assertIn('CLOUDIF_SUPABASE_MCP_BROKER_HOST=127.0.0.1', unit)
        self.assertIn('CLOUDIF_SUPABASE_MCP_BROKER_PORT=18218', unit)
        self.assertIn('IPAddressDeny=any', unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/supabase-mcp-broker.env', gateway_unit)
        self.assertIn('cloudif-supabase-mcp-broker.service', gateway_unit)
        self.assertNotIn('oauth/authorize', self.broker)
        self.assertNotIn('client_secret', self.broker)
        self.assertIn("if not self.authed()", self.broker)

    def test_broker_has_only_known_routes_and_no_shell_endpoint(self):
        for route in ('/health', '/v1/read', '/v1/plan', '/v1/effect'):
            self.assertIn(route, self.broker)
        for forbidden in ('/shell', '/terminal', '/exec-command', 'shell=True', 'os.system(', 'eval(', 'exec('):
            self.assertNotIn(forbidden, self.broker)
        self.assertIn('SERVICE_ALLOWLIST', self.broker)
        self.assertIn("['docker', 'logs'", self.broker)
        self.assertIn("['docker', 'inspect'", self.broker)

    def test_database_access_is_bound_to_snapshot_project_and_tenant(self):
        block = self.broker[self.broker.index('def project_context'):self.broker.index('def require_role')]
        self.assertIn("select * from projects where slug=?", block)
        self.assertIn("select subject_type,subject,role from project_acl where project_id=?", block)
        self.assertIn("tenant_dir = TENANT_ROOT / tenant", block)
        self.assertIn('project_access_denied', block)
        self.assertIn('tenant_runtime_not_found', block)

    def test_database_port_comes_from_each_tenant_configuration(self):
        block = self.broker[self.broker.index('def db_target'):self.broker.index('def postgres')]
        self.assertIn("env.get('POSTGRES_INTERNAL_PORT') or env.get('POSTGRES_PORT')", block)
        self.assertIn('database_port_unavailable', block)
        self.assertNotIn('return host, 5432,', block)

    def test_sensitive_schemas_and_server_capabilities_are_blocked(self):
        for marker in (
            'SENSITIVE_SCHEMA_RE', 'FORBIDDEN_SQL', 'UNSAFE_FUNCTION_LANGUAGE',
            'alter\\s+system', 'copy\\b', 'security\\s+definer',
            'pg_(?:read_(?:binary_)?file', 'unsafe_function_language',
            'sensitive_schema_access_denied', 'forbidden_sql_capability',
        ):
            self.assertIn(marker, self.broker)
        self.assertIn("db_role: str = 'service_role'", self.broker)
        self.assertIn("db_role='postgres'", self.broker)
        self.assertIn("set local role {}", self.broker)
        self.assertIn("set local row_security=on", self.broker)

    def test_role_gates_separate_reads_admin_and_owner_secret_values(self):
        for marker in (
            'require_role(ctx, 50)',
            'require_role(ctx, 80)',
            "require_role(ctx, 100, 'owner_required_for_secret_values')",
            "minimum = 60 if operation == 'records.change' else 90",
        ):
            self.assertIn(marker, self.broker)
        self.assertIn("role = 'service' if not user else 'none'", self.broker)

    def test_changes_are_plan_approval_digest_and_effect_bound(self):
        for marker in (
            'def canonical_plan', 'plan_digest', 'approval_required',
            'def supabase_approval_create', 'supabase_plan_digest',
            "approval_transition(approval_id,'reserve'",
            "approval_transition(approval_id,'finalize'",
            'plan_digest_mismatch', 'approval_mismatch',
            'transaction_ids(action,approval_id,client_id,digest)',
        ):
            self.assertIn(marker, self.broker + self.gateway)
        self.assertIn("'secret_values_in_metadata':False", self.gateway)
        self.assertNotIn("'secrets':payload", self.gateway)

    def test_secret_values_are_one_time_and_not_persisted(self):
        block = self.broker[self.broker.index('def execution_finish'):self.broker.index('def execute_effect')]
        self.assertIn("'secret_values_stored': False", block)
        self.assertIn("'revealed_names'", block)
        self.assertNotIn("result_json text not null default '{}',\n      secret", self.broker)
        self.assertIn('secret_delivery_already_consumed', self.broker)
        self.assertIn("'one_time_delivery': True", self.broker)

    def test_portal_documents_tools_and_safe_approval_metadata(self):
        for name in sorted(READ_TOOLS | PLAN_TOOLS | WRITE_TOOLS):
            self.assertIn("'" + name + "'", self.guide, name)
        for marker in (
            'supabase_operation', 'supabase_plan_digest', 'secret_values_in_metadata',
            'Alterar registros do Supabase', 'Executar SQL no Supabase',
            'Alterar políticas RLS', 'Alterar schema do banco', 'Exibir segredos do tenant',
        ):
            self.assertIn(marker, self.approval)
        self.assertEqual(GUIDE.read_bytes(), GUIDE_LEGACY.read_bytes())
        self.assertEqual(APPROVAL_PANEL.read_bytes(), APPROVAL_PANEL_LEGACY.read_bytes())


if __name__ == '__main__':
    unittest.main()
