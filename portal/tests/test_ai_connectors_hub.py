import importlib.util
from pathlib import Path
import unittest
import re
import shutil
import subprocess
import tempfile


class AIConnectorsHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py')
        spec = importlib.util.spec_from_file_location('cloudif_ai_agents_guide_test', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_empty_hub_keeps_guidance_and_separation(self):
        html = self.module.render([], 'csrf-test')
        for text in ('Portal e agentes funcionam de forma independente', 'ChatGPT', 'Claude', 'Llama / Ollama', 'Nenhum projeto disponível para conexão'):
            self.assertIn(text, html)
        self.assertNotIn('details open', html)

    def test_rendered_agent_javascript_is_syntax_valid(self):
        import importlib.util,sys
        root=Path(__file__).resolve().parents[2]
        guide_path=root/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
        spec=importlib.util.spec_from_file_location('agent_guide_js_syntax_test',guide_path)
        guide=importlib.util.module_from_spec(spec);sys.modules[spec.name]=guide;spec.loader.exec_module(guide)
        rows=[{'project_slug':'laboratorio-de-hardware','client_id':'project-test','owner_user':'owner','tenant':'tenant','role_profile':'project-admin','environment':'project','scopes':['workspace:change-set-plan'],'instructions':{'mcp_endpoint':'https://cloudiff.duckdns.org/cloudiff/mcp'}}]
        html=guide.render(rows,'a'*64,[],True)
        scripts=re.findall(r'<script[^>]*>(.*?)</script>',html,re.S|re.I)
        rotate=[script for script in scripts if 'agent-rotate' in script]
        self.assertEqual(len(rotate),1)
        self.assertIn('String.fromCharCode(10)',rotate[0])
        node=shutil.which('node')
        if not node:self.skipTest('node unavailable for rendered JavaScript syntax check')
        with tempfile.NamedTemporaryFile('w',suffix='.js',delete=False) as fh:
            fh.write(rotate[0]);name=fh.name
        try:
            proc=subprocess.run([node,'--jitless','--check',name],capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,0,proc.stderr)
        finally:
            Path(name).unlink(missing_ok=True)

    def test_rotation_route_refreshes_csrf_and_logs_sanitized_denials(self):
        root=Path(__file__).resolve().parents[2]
        portal=(root/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        api=portal[portal.index("if path in ('/cloudiff/portal/api/agent-guide'"):portal.index("return _aig_prev_get(self)",portal.index("if path in ('/cloudiff/portal/api/agent-guide'"))]
        self.assertIn("self.send_header('X-CSRF-Token',_prod_csrf_token(user))",api)
        self.assertIn("self.send_header('Cache-Control','no-store')",api)
        rotate=portal[portal.index("if path in ('/cloudiff/portal/action/rotate-project-credential'"):portal.index("return _oi_prev_post(self)",portal.index("if path in ('/cloudiff/portal/action/rotate-project-credential'"))]
        for marker in ('project_credential_rotation_denied','origin_denied','csrf_denied','project_denied'):
            self.assertIn(marker,rotate)
        self.assertNotIn("csrf_token':",rotate)

    def test_project_hub_uses_real_rotation_endpoint(self):
        row = {
            'project_slug': 'projeto-teste',
            'client_id': 'client-projeto-teste',
            'role_profile': 'developer',
            'environment': 'project',
            'scopes': ['project:read', 'workspace:prepare', 'forgejo:plan-edit'],
            'instructions': {'mcp_endpoint': 'https://cloudiff.example/mcp'},
        }
        html = self.module.render([row], 'csrf-test')
        self.assertIn('Gerar/rotacionar Client Secret para GPT Actions', html)
        self.assertIn('/cloudiff/portal/action/rotate-project-credential', html)
        self.assertIn('/cloudiff/portal/api/agent-guide', html)
        self.assertIn("pre.headers.get('X-CSRF-Token')", html)
        self.assertIn("csrf_token:fresh", html)
        self.assertIn('agent-rotate-status', html)
        self.assertIn('Exibição única', html)
        self.assertIn('MCP público + GPT Actions confidencial', html)
        self.assertIn('Client Secret', html)
        self.assertIn('Configuração pronta para copiar', html)



    def test_public_oauth_details_are_project_specific_and_secretless(self):
        row = {
            'project_slug': 'projeto-teste', 'client_id': 'client-projeto-teste',
            'owner_user': 'iff0001', 'tenant': 'iff0001-projeto-teste',
            'role_profile': 'developer', 'environment': 'project',
            'scopes': ['project:read'], 'instructions': {'mcp_endpoint': 'https://cloudiff.duckdns.org/cloudiff/mcp'},
        }
        html = self.module.render([row], 'csrf-test')
        for marker in (
            'Client Secret', 'Deixe vazio', 'token_endpoint_auth_method=none', 'PKCE', 'S256',
            '/cloudiff/mcp/oauth/authorize', '/cloudiff/mcp/oauth/token',
            'https://claude.ai/api/mcp/auth_callback', 'ChatGPT', 'Claude', 'Llama / Ollama',
            'client-projeto-teste', 'iff0001-projeto-teste',
            'https://cloudiff.duckdns.org/git/iff0001/cloudif-projeto-teste.git',
        ):
            self.assertIn(marker, html)
        self.assertIn('Gerar/rotacionar Client Secret para GPT Actions', html)
        self.assertIn('Client Secret obrigatório no token exchange', html)

    def test_chatgpt_actions_card_exposes_schema_and_privacy(self):
        row = {
            'project_slug': 'projeto-teste', 'client_id': 'client-projeto-teste',
            'owner_user': 'iff0001', 'tenant': 'iff0001-projeto-teste',
            'role_profile': 'developer', 'environment': 'project',
            'scopes': ['project:read'], 'instructions': {'mcp_endpoint': 'https://cloudiff.duckdns.org/cloudiff/mcp'},
        }
        html = self.module.render([row], 'csrf-test')
        for marker in (
            'GPT personalizado — Actions', 'Schema OpenAPI:', 'Copiar URL do schema', 'Abrir schema',
            'https://cloudiff.duckdns.org/cloudiff/mcp/openapi/client-projeto-teste.json',
            'https://cloudiff.duckdns.org/cloudiff/mcp/privacy', 'ChatGPT — MCP',
            'GPT Actions sem PKCE', 'Client Secret obrigatório no token exchange', 'Callback: use exatamente a URL fornecida pelo editor do GPT',
        ):
            self.assertIn(marker, html)
        guide = self.module.guide_data([row])
        self.assertEqual(guide['projects'][0]['openapi_schema_url'], 'https://cloudiff.duckdns.org/cloudiff/mcp/openapi/client-projeto-teste.json')
        self.assertEqual(guide['projects'][0]['privacy_policy_url'], 'https://cloudiff.duckdns.org/cloudiff/mcp/privacy')

    def test_generic_config_uses_public_oauth_without_token_headers(self):
        config = self.module.config_json('https://cloudiff.example/mcp', 'client-project', 'project')
        for marker in ('"token_endpoint_auth_method": "none"', '"code_challenge_method": "S256"', '"client_secret": ""'):
            self.assertIn(marker, config)
        self.assertNotIn('Authorization', config)
        self.assertNotIn('CLOUDIFF_TOKEN', config)

    def test_pending_approval_is_embedded_in_project_card(self):
        row = {
            'project_slug': 'projeto-teste', 'client_id': 'client-projeto-teste',
            'role_profile': 'developer', 'environment': 'project',
            'scopes': ['project:read'], 'instructions': {'mcp_endpoint': 'https://cloudiff.example/mcp'},
        }
        approval = {
            'approval_id': 'apr_test', 'project_slug': 'projeto-teste',
            'status': 'pending', 'action_label': 'Publicar em homologação', 'reason': 'Validar release',
        }
        html = self.module.render([row], 'csrf-test', [approval], True)
        self.assertIn('Aprovações humanas', html)
        self.assertIn('Publicar em homologação', html)
        self.assertIn('>Aceitar<', html)
        self.assertIn('>Rejeitar<', html)
        self.assertIn('name="return_to" value="agentes"', html)

    def test_global_services_has_dedicated_current_route(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertIn('def global_services_body', source)
        self.assertIn('tab == "admin-manutencao"', source)
        self.assertIn('Todos os containers', source)
        self.assertIn('Repositórios por usuário', source)

    def test_shell_does_not_append_legacy_identity_panel(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertNotIn('identities = getattr(owner, "_oi_panel")', source)


if __name__ == '__main__':
    unittest.main()
