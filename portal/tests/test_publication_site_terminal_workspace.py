from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
UI=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
PUBLICATIONS=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
COEXIST=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
PUBLISHER=(ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text()
CSS=(ROOT/'portal/design/components.css').read_text()
KOMODO_EMBED=(ROOT/'components/proxy/usr/local/sbin/cloudif-configure-komodo-embed.sh').read_text()


class PublicationSiteTerminalWorkspaceTests(unittest.TestCase):
    def test_information_cards_match_runtime_tool_pattern(self):
        self.assertIn('<span>Site</span><strong>Preview do site</strong>',UI)
        self.assertIn('data-publication-tool="site"',UI)
        self.assertIn('<span>Terminal</span><strong>Terminal do ambiente</strong>',UI)
        self.assertIn('data-publication-tool="terminal"',UI)
        self.assertIn('publication-card-action',UI)

    def test_environment_workspace_has_site_and_terminal_tools(self):
        self.assertIn("const publicationTools=['overview','site','php','node','terminal','variables']",BASE)
        self.assertIn('function publicationSiteRender()',BASE)
        self.assertIn('function publicationTerminalRender()',BASE)
        self.assertIn("/release-flow/stage/terminal",BASE)
        self.assertIn("target.hostname!=='komodoiff.duckdns.org'",BASE)
        self.assertIn('data-publication-terminal-open',BASE)

    def test_site_preview_is_sandboxed_and_only_accepts_cloudiff_stage_urls(self):
        self.assertIn("target.hostname.endsWith('.cloudiff.duckdns.org')",BASE)
        self.assertIn('class="stage-site-preview"',BASE)
        self.assertIn('sandbox="allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-downloads"',BASE)
        self.assertIn("frame-src 'self' https://*.cloudiff.duckdns.org https://komodoiff.duckdns.org",BASE)
        self.assertIn('.stage-site-preview iframe{',CSS)

    def test_terminal_is_embedded_and_keeps_external_fallback(self):
        self.assertIn('stage-site-preview stage-terminal-embed',BASE)
        self.assertIn('stage-terminal-embed__frame',BASE)
        self.assertIn('allow=\"clipboard-read; clipboard-write\"',BASE)
        self.assertIn('Abrir no Komodo',BASE)
        self.assertIn("https://komodoiff.duckdns.org",BASE)
        self.assertIn('.stage-terminal-embed__frame',CSS)
        terminal_block=BASE[BASE.index('async function publicationTerminalOpen'):BASE.index('async function publicationVariablesLoad')]
        self.assertNotIn('window.open(',terminal_block)

    def test_komodo_proxy_allows_only_cloudiff_portal_as_frame_ancestor(self):
        self.assertIn('DOMAIN=komodoiff.duckdns.org',KOMODO_EMBED)
        self.assertIn('PORTAL_ORIGIN=https://cloudiff.duckdns.org',KOMODO_EMBED)
        self.assertIn("more_clear_headers 'X-Frame-Options';",KOMODO_EMBED)
        self.assertIn('more_set_headers',KOMODO_EMBED)
        self.assertIn("frame-ancestors 'self' {portal}",KOMODO_EMBED)
        self.assertIn('nginx -t',KOMODO_EMBED)
        self.assertIn('rollback()',KOMODO_EMBED)

    def test_stage_terminal_portal_contract_is_exact_and_production_is_privileged(self):
        block=PUBLICATIONS[PUBLICATIONS.index('def stage_terminal('):PUBLICATIONS.index('def recreate_preview(',PUBLICATIONS.index('def stage_terminal('))]
        self.assertIn("environment not in {'preview','homologation','production'}",block)
        self.assertIn("if environment=='preview':return preview_terminal",block)
        self.assertIn("if environment=='production' and not _owner_or_admin",block)
        self.assertIn("cloudif-p{num}-d{dep}-web",block)
        self.assertIn("cloudif-p{num}-p{publication}-publication-web",block)
        self.assertIn("/komodo/project/stage/terminal",block)
        self.assertIn("'secretValuesIncluded':False",block)
        self.assertIn('stage/terminal',COEXIST)
        self.assertIn('publications.stage_terminal',COEXIST)

    def test_runtime_agent_re_resolves_and_validates_exact_stage_container(self):
        block=RUNTIME[RUNTIME.index('def cloudif_stage_terminal('):RUNTIME.index('def cloudif_preview_snapshot(',RUNTIME.index('def cloudif_stage_terminal('))]
        self.assertIn("publication_runtimes where project=? and public_number=? and deploy_number=? and status='ready'",block)
        self.assertIn("stage_production_releases where project=? and public_number=? and publication_number=? and status='ready' and is_active=1",block)
        self.assertIn("expected=f'cloudif-p{num}-d{dep}-web'",block)
        self.assertIn("expected=f'cloudif-p{num}-p{publication}-publication-web'",block)
        self.assertIn('_cloudif_wait_health(container,2)',block)
        self.assertIn('_cloudif_ensure_container_terminal(server_id,container)',block)
        self.assertIn('/komodo/project/stage/terminal',RUNTIME)

    def test_manage_publication_reuses_the_same_site_and_terminal_pattern(self):
        self.assertIn('class="release-tools"',BASE)
        for view,label in (('stage','Etapa'),('site','Site'),('terminal','Terminal')):
            self.assertIn(f'data-release-view="{view}">{label}</button>',BASE)
        self.assertIn('function renderReleaseSite()',BASE)
        self.assertIn('function renderReleaseTerminal()',BASE)
        self.assertIn('function openStageTerminal()',BASE)
        self.assertIn('function renderEmbeddedTerminal(result,ctx)',BASE)
        self.assertIn("post('stage/terminal',{environment})",BASE)
        self.assertIn('.release-tools{display:flex',CSS)

    def test_publisher_allows_only_the_portal_to_frame_managed_sites(self):
        managed=PUBLISHER[PUBLISHER.index('for num_s,p in sorted'):PUBLISHER.index('for alias,a in sorted')]
        self.assertNotIn('X-Frame-Options SAMEORIGIN',managed)
        self.assertGreaterEqual(managed.count("frame-ancestors 'self' https://cloudiff.duckdns.org"),3)


if __name__=='__main__':
    unittest.main()
