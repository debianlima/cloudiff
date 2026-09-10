from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
UI=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
COEXIST=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
CSS=(ROOT/'portal/design/components.css').read_text()
PUBLICATION_CSS=(ROOT/'portal/design/publications.css').read_text()
RELEASE_JS_PATH=ROOT/'portal/design/publication-release.js'

class ReleaseFlowWizardUITests(unittest.TestCase):
    def test_release_manager_is_promotion_only(self):
        self.assertTrue(RELEASE_JS_PATH.is_file(), 'release manager must live in a dedicated module')
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('Gerenciar publicação',release)
        self.assertIn('Enviar Preview para homologação',release)
        self.assertIn('Homologar',release)
        self.assertIn('Publicar em Produção',release)
        self.assertNotIn('data-release-view=',release)
        self.assertNotIn('release-tools',release)
        self.assertNotIn('Abrir terminal do Preview',release)
        self.assertNotIn('preview-recreate-production',release)
        self.assertNotIn('preview-recreate-template',release)
        self.assertNotIn('Homologar e publicar',release)
        self.assertNotIn('data-env-wizard',release)

    def test_preview_is_prepared_automatically_in_release_manager(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('ensurePreviewAutomatically',release)
        self.assertIn("post('preview/ensure', {})",release)
        self.assertIn('Preparando Preview automaticamente',release)
        self.assertNotIn('>Preparar Preview<',release)
        self.assertNotIn('>Sincronizar Preview<',release)

    def test_environment_menu_is_the_only_runtime_toolbox(self):
        controls=UI[UI.index('def _configuration_controls'):UI.index('def publication_panel')]
        self.assertIn('Ambiente de publicação',controls)
        self.assertIn('data-publication-tool="overview"',controls)
        self.assertNotIn('Variáveis por ambiente',controls)
        release=RELEASE_JS_PATH.read_text() if RELEASE_JS_PATH.exists() else ''
        for label in ('Site','PHP','Node.js','Terminal','Variáveis'):
            self.assertNotIn('data-release-view="'+label.lower()+'"',release)

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
        self.assertIn('Ambiente de publicação',tools)
        self.assertLess(tools.index('Gerenciar publicação'),tools.index('Ambiente de publicação'))
        head=controls[controls.index('publication-release-flow__head'):controls.index('publication-release-flow__stages')]
        self.assertNotIn('Gerenciar publicação',head)

    def test_cached_legacy_publish_is_redirected_to_homologation(self):
        self.assertIn('publications.enqueue_homologation(slug,user)',BASE)
        self.assertNotIn('result=publications.enqueue_publish(slug,user)',BASE)
        self.assertIn('A ativação direta de artefatos dN foi desativada',BASE)

    def test_project_card_redirects_to_publications_and_deep_links_requested_view(self):
        block=BASE[BASE.index('<article class="project-workspace-detail"'):]
        block=block[:block.index('</article>')+10]
        self.assertIn('Preview → Homologação → Produção',block)
        self.assertNotIn('data-release-flow-open',block)
        self.assertNotIn('data-publication-environments',block)
        self.assertIn('?tab=publicacao&amp;project={urllib.parse.quote(slug,safe=',block)
        self.assertIn('&amp;open=release',block)
        self.assertIn('&amp;open=variables',block)
        self.assertIn('>Publicar</a>',block)
        self.assertIn('>Variáveis</a>',block)
        self.assertNotIn('/publication/base/',block)

    def test_publications_page_auto_opens_release_deep_link(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn("const params = new URLSearchParams(location.search)",release)
        self.assertIn("params.get('open') === 'release'",release)
        self.assertIn("item.dataset.projectSlug === deepLinkProject",release)
        self.assertIn("setTimeout(() => open(button), 0)",release)

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

    def test_terminal_remains_available_outside_release_manager(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('preview/terminal',COEXIST)
        self.assertIn('stage/terminal',COEXIST)
        self.assertNotIn("post('preview/terminal'",release)
        self.assertNotIn("post('stage/terminal'",release)
        self.assertNotIn('renderEmbeddedTerminal',release)

    def test_release_manager_is_loaded_as_publication_asset(self):
        self.assertIn('publication-release.js',COEXIST)
        self.assertIn('publication-release.js',BASE)
        self.assertNotIn('function renderEmbeddedTerminal',BASE)

    def test_impeccable_polish_reduces_nested_cards_and_improves_touch_targets(self):
        self.assertNotIn('Fluxo de publicação</span>',UI)
        self.assertNotIn('Publicação controlada</span>',BASE)
        self.assertIn('.publication-information{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border-block:1px solid var(--rule)}',CSS)
        self.assertIn('.publication-information>div{display:grid;align-content:start;gap:5px;padding:var(--s3) var(--s4);border:0;border-right:1px solid var(--rule-soft);border-radius:0;min-width:0}',CSS)
        self.assertIn('.publication-release-flow__stages{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border-block:1px solid var(--rule-soft)}',PUBLICATION_CSS)
        self.assertIn('.publication-release-flow__stages article{display:flex;align-items:center;gap:10px;padding:12px 14px;border:0;border-right:1px solid var(--rule-soft);border-radius:0;background:transparent}',PUBLICATION_CSS)
        self.assertIn('.publication-release-flow__tools',PUBLICATION_CSS)
        self.assertIn('#cloudif-release-flow .release-tabs button{min-height:44px}',PUBLICATION_CSS)
        self.assertIn('.nav-link{min-height:44px}',CSS)
        self.assertIn('.btn:focus-visible,.nav-link:focus-visible',CSS)

    def test_release_wizard_closes_with_escape_and_restores_focus(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('opener: null',release)
        self.assertIn('model.opener = button',release)
        self.assertIn('if (opener && document.contains(opener)) opener.focus()',release)
        self.assertIn("event.key === 'Escape'",release)

    def test_wizard_has_dark_theme_safe_tokens_and_mobile_layout(self):
        self.assertIn('_WHP_RELEASE_ASSETS',BASE)
        self.assertIn('cloudif-whp-release-script',BASE)
        self.assertNotIn('cloudif-whp-release-style',BASE)
        self.assertNotIn('/* CloudIFF W/H/P release wizard */',CSS)
        self.assertIn('/* CloudIFF W/H/P release wizard */',PUBLICATION_CSS)
        self.assertIn('var(--surface)',PUBLICATION_CSS)
        self.assertIn('var(--rule)',PUBLICATION_CSS)
        self.assertIn('var(--overlay)',PUBLICATION_CSS)
        self.assertIn('@media(max-width:700px)',PUBLICATION_CSS)
        self.assertNotIn('!important',PUBLICATION_CSS)
        self.assertIn('Promova o mesmo artefato do Preview até Produção.',RELEASE_JS_PATH.read_text())

if __name__=='__main__':unittest.main()
