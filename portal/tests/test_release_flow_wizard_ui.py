from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
UI=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
COEXIST=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
CSS=(ROOT/'portal/design/components.css').read_text()

class ReleaseFlowWizardUITests(unittest.TestCase):
    def test_primary_ui_uses_w_h_p_and_no_direct_publish_button(self):
        self.assertIn('Preview → Homologação → Publicação',UI)
        self.assertIn('data-release-flow-open',UI)
        self.assertNotIn('>Publicar site<',UI)
        self.assertNotIn('>Publicar nova versão<',UI)
        self.assertIn('Alternar entre Publicações',UI);self.assertNotIn('Detalhes técnicos e versões legadas',UI)

    def test_primary_actions_are_grouped_side_by_side(self):
        controls=UI[UI.index('def _configuration_controls'):UI.index('def publication_panel')]
        tools=controls[controls.index('publication-release-flow__tools'):]
        self.assertIn('Gerenciar publicação',tools)
        self.assertIn('Variáveis por ambiente',tools)
        self.assertLess(tools.index('Gerenciar publicação'),tools.index('Variáveis por ambiente'))
        head=controls[controls.index('publication-release-flow__head'):controls.index('publication-release-flow__stages')]
        self.assertNotIn('Gerenciar publicação',head)

    def test_cached_legacy_publish_is_redirected_to_homologation(self):
        self.assertIn('publications.enqueue_homologation(slug,user)',BASE)
        self.assertNotIn('result=publications.enqueue_publish(slug,user)',BASE)
        self.assertIn('A ativação direta de artefatos dN foi desativada',BASE)

    def test_project_card_redirects_to_publications_and_deep_links_requested_view(self):
        block=BASE[BASE.index('<section class="project-final__section project-final__publication">'):]
        block=block[:block.index('</section>')+10]
        self.assertIn('W Preview · H Homologation · P Publication',block)
        self.assertNotIn('data-release-flow-open',block)
        self.assertNotIn('data-publication-environments',block)
        self.assertIn('?tab=publicacao&amp;project={urllib.parse.quote(slug,safe=',block)
        self.assertIn('&amp;open=release',block)
        self.assertIn('&amp;open=variables',block)
        self.assertIn('Gerenciar publicação</a>',block)
        self.assertIn('Variáveis por ambiente</a>',block)
        self.assertNotIn('/publication/base/',block)

    def test_publications_page_auto_opens_release_deep_link(self):
        self.assertIn("const releaseDeepLink=new URLSearchParams(location.search)",BASE)
        self.assertIn("releaseDeepLink.get('open')==='release'",BASE)
        self.assertIn("x.dataset.projectSlug===releaseDeepLinkProject",BASE)
        self.assertIn("setTimeout(()=>open(button),0)",BASE)

    def test_publications_page_auto_opens_variables_deep_link(self):
        self.assertIn("const publicationDeepLink=new URLSearchParams(location.search)",BASE)
        self.assertIn("publicationDeepLinkOpen==='variables'",BASE)
        self.assertIn('[data-publication-environments][data-publication-tool="variables"]',BASE)
        self.assertIn("x.dataset.projectSlug===publicationDeepLinkProject",BASE)
        self.assertIn("setTimeout(()=>publicationEnvironmentOpen(button),0)",BASE)

    def test_release_flow_api_is_csrf_protected(self):
        self.assertIn('/release-flow(?:/(approval/status))?',COEXIST)
        self.assertIn('/release-flow/(preview/ensure|preview/recreate|preview/terminal|stage/terminal|homologation/enqueue',COEXIST)
        self.assertIn("getattr(owner,'_prod_csrf_equal')",COEXIST)
        self.assertIn("'production/approval/request'",COEXIST)
        self.assertIn("'production/enqueue'",COEXIST)

    def test_preview_tab_embeds_preview_terminal_without_popup(self):
        self.assertIn('Abrir terminal do Preview',BASE)
        self.assertIn("data-release-action=\"preview-terminal\"",BASE)
        self.assertIn('async function openPreviewTerminal()',BASE)
        self.assertIn('function renderEmbeddedTerminal(result,ctx)',BASE)
        self.assertIn('class=\"stage-site-preview stage-terminal-embed\"',BASE)
        block=BASE[BASE.index('async function openPreviewTerminal()'):BASE.index('function bindActions()',BASE.index('async function openPreviewTerminal()'))]
        self.assertNotIn('window.open(',block)
        self.assertIn("post('preview/terminal',{})",BASE)
        self.assertIn("target.hostname!=='komodoiff.duckdns.org'",BASE)
        self.assertIn('preview/terminal',COEXIST)

    def test_terminal_tool_auto_loads_and_cache_busts_komodo_document(self):
        release=BASE[BASE.index('function renderReleaseTerminal'):BASE.index('async function load()',BASE.index('function renderReleaseTerminal'))]
        self.assertIn("if(model.view==='terminal')",release)
        self.assertIn('setTimeout(openStageTerminal,0)',release)
        self.assertNotIn('data-release-stage-terminal',release)
        self.assertIn("embed.searchParams.set('_cloudiff_embed',String(Date.now()))",BASE)
        embedded=BASE[BASE.index('function renderEmbeddedTerminal'):BASE.index('async function openStageTerminal')]
        self.assertNotIn('sandbox=',embedded)

    def test_wizard_has_dark_theme_safe_tokens_and_mobile_layout(self):
        self.assertIn('_WHP_RELEASE_ASSETS',BASE)
        self.assertIn('cloudif-whp-release-script',BASE)
        self.assertNotIn('cloudif-whp-release-style',BASE)
        self.assertIn('/* CloudIFF W/H/P release wizard */',CSS)
        self.assertIn('var(--surface)',CSS)
        self.assertIn('var(--rule)',CSS)
        self.assertIn('var(--overlay)',CSS)
        self.assertIn('@media(max-width:700px)',CSS)
        self.assertNotIn('!important',CSS)
        self.assertIn('W = Workspace Preview · H = Homologation · P = Publication',BASE)

if __name__=='__main__':unittest.main()
