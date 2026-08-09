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
KOMODO_EMBED_AUTH=(ROOT/'components/runtime/usr/local/sbin/cloudif-configure-komodo-embed-auth.sh').read_text()


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
        self.assertIn('function publicationTerminalRender(requestId)',BASE)
        self.assertIn("/release-flow/stage/terminal",BASE)
        self.assertIn("target.hostname!=='komodoiff.duckdns.org'",BASE)
        self.assertIn('data-publication-terminal-open',BASE)

    def test_site_preview_is_sandboxed_and_only_accepts_cloudiff_stage_urls(self):
        self.assertIn("target.hostname.endsWith('.cloudiff.duckdns.org')",BASE)
        self.assertIn('class="stage-site-preview"',BASE)
        self.assertIn('sandbox="allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-downloads"',BASE)
        self.assertIn("frame-src 'self' https://*.cloudiff.duckdns.org https://komodoiff.duckdns.org https://authiff.duckdns.org",BASE)
        self.assertIn('.stage-site-preview iframe{',CSS)

    def test_terminal_is_embedded_and_keeps_external_fallback(self):
        self.assertIn('stage-site-preview stage-terminal-embed',BASE)
        self.assertIn('stage-terminal-embed__frame',BASE)
        self.assertIn('allow=\"clipboard-read; clipboard-write; fullscreen\"',BASE)
        self.assertIn("embed.searchParams.set('_cloudiff_embed',String(Date.now()))",BASE)
        self.assertIn('Abrir no Komodo',BASE)
        self.assertIn("https://komodoiff.duckdns.org",BASE)
        self.assertIn('.stage-terminal-embed__frame',CSS)
        terminal_block=BASE[BASE.index('async function publicationTerminalOpen'):BASE.index('async function publicationVariablesLoad')]
        self.assertNotIn('window.open(',terminal_block)

    def test_komodo_and_authentik_proxy_allow_only_cloudiff_portal_as_frame_ancestor(self):
        self.assertIn('KOMODO_DOMAIN=komodoiff.duckdns.org',KOMODO_EMBED)
        self.assertIn('AUTH_DOMAIN=authiff.duckdns.org',KOMODO_EMBED)
        self.assertIn('PORTAL_ORIGIN=https://cloudiff.duckdns.org',KOMODO_EMBED)
        self.assertIn("more_clear_headers 'X-Frame-Options';",KOMODO_EMBED)
        self.assertIn('more_set_headers',KOMODO_EMBED)
        self.assertIn("frame-ancestors 'self' {portal}",KOMODO_EMBED)
        self.assertIn("more_set_headers -t 'text/html' 'Cache-Control: no-store';",KOMODO_EMBED)
        self.assertIn('patch_db_host "$AUTH_HOST_ID" \'Authentik\'',KOMODO_EMBED)
        self.assertIn('verify_host "$AUTH_DOMAIN"',KOMODO_EMBED)
        self.assertIn('nginx -t',KOMODO_EMBED)
        self.assertIn('rollback()',KOMODO_EMBED)

    def test_komodo_core_uses_native_embed_and_cross_site_oidc_settings(self):
        for key in ('KOMODO_OIDC_AUTO_REDIRECT','OIDC_AUTO_REDIRECT','KOMODO_OIDC_REDIRECT_HOST','KOMODO_SESSION_ALLOW_CROSS_SITE','KOMODO_X_FRAME_OPTIONS','KOMODO_CONTENT_SECURITY_POLICY'):
            self.assertIn(key,KOMODO_EMBED_AUTH)
        self.assertIn("'KOMODO_OIDC_REDIRECT_HOST':'https://authiff.duckdns.org'",KOMODO_EMBED_AUTH)
        self.assertIn("'KOMODO_SESSION_ALLOW_CROSS_SITE':'true'",KOMODO_EMBED_AUTH)
        self.assertIn("'KOMODO_X_FRAME_OPTIONS':''",KOMODO_EMBED_AUTH)
        self.assertIn("frame-ancestors 'self' https://cloudiff.duckdns.org",KOMODO_EMBED_AUTH)
        self.assertIn('docker compose --env-file',KOMODO_EMBED_AUTH)
        self.assertIn('compose up -d core',KOMODO_EMBED_AUTH)
        self.assertIn("SameSite=None",KOMODO_EMBED_AUTH)
        self.assertIn("komodo_native_x_frame_options_present",KOMODO_EMBED_AUTH)
        self.assertIn("location: https://authiff",KOMODO_EMBED_AUTH)
        self.assertIn('rollback()',KOMODO_EMBED_AUTH)

    def test_every_portal_komodo_navigation_starts_direct_oidc_and_preserves_destination(self):
        self.assertIn("function cloudifKomodoLoginUrl(value)",BASE)
        self.assertIn("login.searchParams.set('redirect',target.href)",BASE)
        self.assertIn("document.addEventListener('click'",BASE)
        self.assertIn("const embedLogin=cloudifKomodoLoginUrl(embed.href),externalLogin=cloudifKomodoLoginUrl(target.href)",BASE)
        self.assertIn("CLOUDIF_KOMODO_OIDC_URL",BASE)
        self.assertIn("_cpx_parse.urlencode({'redirect':target})",BASE)
        self.assertIn("auth/oidc/login?redirect=https%3A%2F%2Fkomodoiff.duckdns.org%2Fservers",BASE)
        self.assertIn("auth/oidc/login?redirect=https%3A%2F%2Fkomodoiff.duckdns.org%2Fcontainers",COEXIST)
        self.assertIn("auth/oidc/login?redirect='+encodeURIComponent(data.terminalUrl)",COEXIST)

    def test_active_portal_has_no_raw_hardcoded_komodo_links(self):
        for source in (BASE,COEXIST):
            for fragment in source.split('href=\"https://komodoiff.duckdns.org') [1:]:
                href=fragment.split('\"',1)[0]
                self.assertTrue(href.startswith('/auth/oidc/login'),href)
        self.assertNotIn('location.replace(data.terminalUrl)',BASE)
        self.assertNotIn('location.replace(data.terminalUrl)',COEXIST)

    def test_terminal_tabs_prepare_the_session_automatically(self):
        workspace=BASE[BASE.index('function publicationTerminalRender'):BASE.index('async function publicationVariablesLoad')]
        self.assertIn('publicationTerminalOpen(null,requestId)',workspace)
        self.assertNotIn('Abrir terminal no Komodo</button>',workspace)
        release=BASE[BASE.index('function renderReleaseTerminal'):BASE.index('async function load()',BASE.index('function renderReleaseTerminal'))]
        self.assertIn("if(model.view==='terminal')",release)
        self.assertIn('setTimeout(openStageTerminal,0)',release)
        self.assertNotIn('data-release-stage-terminal',release)

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
