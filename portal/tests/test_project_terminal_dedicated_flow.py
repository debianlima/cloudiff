from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PORTAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


class ProjectTerminalDedicatedFlowTests(unittest.TestCase):
    def test_project_card_and_repair_dashboard_use_dedicated_terminal_route(self):
        source=PORTAL.read_text()
        self.assertIn("terminal_target='/cloudiff/portal/project-terminal/'+urllib.parse.quote(slug,safe='')",source)
        self.assertIn("const term=x.stack_id?'/cloudiff/portal/project-terminal/'+encodeURIComponent(x.project):'#';",source)
        renderer=source[source.index('def _pm197_render'):source.index('render_projects=_pm197_render')]
        self.assertNotIn('/action/open-project-terminal',renderer)

    def test_legacy_terminal_action_is_redirect_only(self):
        source=PORTAL.read_text()
        start=source.index("if path in ('/cloudiff/portal/action/open-project-terminal'")
        end=source.index('return _rd_prev_get(self)',start)
        block=source[start:end]
        self.assertIn("target='/cloudiff/portal/project-terminal/'",block)
        self.assertIn("self.send_response(303)",block)
        self.assertIn("self.send_header('Location',target)",block)
        self.assertNotIn("_rd_agent('/komodo/project/terminal/ensure'",block)
        self.assertNotIn("page(user,'projetos'",block)

    def test_dedicated_get_shows_progress_and_post_prepares_terminal(self):
        source=COEXIST.read_text()
        self.assertIn('def project_terminal_page(',source)
        self.assertIn('Preparando o terminal no Komodo',source)
        self.assertIn("project_terminal_match = re.fullmatch(r'/cloudiff?/portal/project-terminal/",source)
        self.assertIn("terminal_prepare_match = re.fullmatch(r'/cloudiff?/portal/api/projects/",source)
        self.assertIn("'/terminal/prepare'",source)
        self.assertIn("getattr(owner,'_prod_csrf_equal')",source)
        self.assertIn("getattr(owner,'_rd_actor_allowed')",source)
        self.assertIn("getattr(owner,'_rd_agent')('/komodo/project/terminal/ensure'",source)
        self.assertIn("parsed_target.scheme!='https'",source)
        self.assertIn("parsed_target.hostname!='komodoiff.duckdns.org'",source)
        self.assertIn("'terminalReady':True",source)
        self.assertIn("'secretValuesIncluded':False",source)
        self.assertIn('except urllib.error.HTTPError as exc:',source)
        self.assertIn("'missing_compose':'A stack do projeto não possui docker-compose.yml.'",source)
        self.assertIn("'container_not_running':'O container do projeto não está em execução.'",source)
        self.assertIn('Verificar ambiente',source)
        self.assertIn('data.message||data.error',source)
        self.assertIn("agent_code in {'container_not_running','missing_compose','stack_metadata_reconcile_failed'}",source)
        self.assertIn('publications.ensure_base_workspace(slug,user)',source)
        self.assertIn("'terminalSource':'base_workspace'",source)
        self.assertIn("data.terminalSource==='base_workspace'",source)
        self.assertIn('Runtime da publicação indisponível. Abrindo o container-base',source)
        self.assertIn("https://komodoiff.duckdns.org/auth/oidc/login?redirect='+encodeURIComponent(data.terminalUrl)",source)
        self.assertIn("encodeURIComponent(data.terminalUrl)",source)

    def test_normal_project_terminal_prefers_live_preview_and_preserves_legacy_fallback(self):
        source=COEXIST.read_text()
        terminal=source[source.index('terminal_prepare_match = re.fullmatch'):]
        self.assertIn('publications.preview_terminal(slug,user)',terminal)
        self.assertIn("'terminalSource':'preview_workspace'",terminal)
        self.assertIn("'preview_terminal_forbidden'",terminal)
        self.assertIn("getattr(owner,'_rd_agent')('/komodo/project/terminal/ensure'",terminal)
        self.assertIn('publications.ensure_base_workspace(slug,user)',terminal)

    def test_project_audit_resolves_base_stack_to_active_publication_and_user_terminal(self):
        runtime=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
        audit=runtime[runtime.index('def _cloudif_project_audit_data'):runtime.index('def cloudif_project_runtime_inspect')]
        self.assertIn("active=_cloudif_active_publication_stack(project,base_stack_id)",audit)
        self.assertIn("if active.get('ok') and normalize_resource_id(active.get('stack_id')):",audit)
        self.assertIn("stack_id=normalize_resource_id(active.get('stack_id'))",audit)
        self.assertIn("str(x.get('name') or '').startswith(terminal+'-')",audit)
        self.assertIn("str(x.get('command') or '').endswith(' '+shell)",audit)

    def test_terminal_errors_never_render_legacy_portal(self):
        portal=PORTAL.read_text();coexist=COEXIST.read_text()
        self.assertNotIn("diagnostic=f'<section class=\"card terminal-unavailable\"",portal)
        self.assertIn("recovery_page('Acesso ao terminal não autorizado'",coexist)
        self.assertIn("recovery_page('Terminal indisponível'",coexist)
        self.assertIn("recovery_page('Não foi possível preparar o terminal'",coexist)


if __name__=='__main__':
    unittest.main()
