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
    def test_release_permissions_are_managed_inside_the_publication_flow(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('data-release-permissions',release)
        self.assertIn('Autorizar homologação',release)
        self.assertNotIn('data-release-refresh',release)
        self.assertIn('Quem pode homologar e publicar',release)
        self.assertIn("post('permissions'",release)
        self.assertIn("post('production/publish'",release)
        self.assertNotIn('Abrir aprovação',release)
        self.assertNotIn("post('production/approval/request'",release)

    def test_preview_has_manual_refresh_without_reintroducing_old_prepare_buttons(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('data-release-action="preview-refresh"',release)
        self.assertIn('Atualizar Preview',release)
        self.assertIn('async function refreshPreview()',release)
        self.assertIn("post('preview/ensure', {})",release)
        self.assertIn('Atualizando Preview…',release)
        self.assertNotIn('preview-auto-retry',release)
        self.assertNotIn('Tentar preparar Preview',release)

    def test_homologation_authorization_button_opens_existing_permission_manager(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('data-release-permissions>Autorizar homologação e publicação</button>',release)
        self.assertIn('Autorizar homologação e publicação',release)
        self.assertIn('Quem pode homologar e publicar',release)
        self.assertIn('data-permission-homologate',release)
        self.assertIn('data-permission-publish',release)
        self.assertNotIn('data-release-refresh',release)

    def test_release_job_shows_real_step_percentage(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('function jobProgressPercent(job)',release)
        self.assertIn('snapshot: 20',release)
        self.assertIn('deploying: 58',release)
        self.assertIn('https: 85',release)
        self.assertIn('completed: 100',release)
        self.assertIn('class="release-job-percent">${percent}%</span>',release)
        self.assertIn('progress max="100" value="${percent}"',release)
        self.assertIn('aria-label="Progresso ${percent}%"',release)
        self.assertIn('.release-job-percent',PUBLICATION_CSS)

    def test_homologation_tab_shows_candidate_creation_progress(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn("job.operation === 'homologation_candidate'",release)
        self.assertIn("['queued', 'running'].includes(job.status)",release)
        self.assertIn('Criando candidato imutável',release)
        self.assertIn('Candidato em preparação',release)
        self.assertIn("job.message || 'Criando candidato imutável…'",release)
        self.assertIn('disabled>Criando candidato…</button>',release)

    def test_release_manager_is_promotion_only(self):
        self.assertTrue(RELEASE_JS_PATH.is_file(), 'release manager must live in a dedicated module')
        release=RELEASE_JS_PATH.read_text()
        self.assertNotIn('Gerenciar publicação',release)
        self.assertIn('window.CloudIFReleaseFlow = { mount: mountEmbedded }',release)
        self.assertIn('cloudif:publication-release-mount',release)
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

    def test_preview_transport_failure_recovers_from_healthy_readback(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('recoverHealthyPreviewAfterEnsureFailure',release)
        self.assertIn('if (preview.configured && preview.healthy)',release)
        self.assertIn("await recoverHealthyPreviewAfterEnsureFailure(error, 'Não foi possível preparar o Preview automaticamente.')",release)
        self.assertIn("await recoverHealthyPreviewAfterEnsureFailure(error, 'Não foi possível atualizar o Preview.')",release)
        self.assertNotIn("return act('preview/ensure', {}, 'Atualizando Preview…')",release)

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
        self.assertNotIn('data-release-flow-open',UI)
        self.assertIn('data-publication-tool="overview"',UI)
        self.assertIn('Ambiente de publicação',UI)
        self.assertNotIn('>Publicar site<',UI)
        self.assertNotIn('>Publicar nova versão<',UI)
        self.assertIn('Alternar entre Publicações',UI);self.assertNotIn('Detalhes técnicos e versões legadas',UI)

    def test_primary_ui_has_one_publication_workspace_entry_point(self):
        controls=UI[UI.index('def _configuration_controls'):UI.index('def publication_panel')]
        tools=controls[controls.index('publication-release-flow__tools'):]
        self.assertNotIn('Gerenciar publicação',tools)
        self.assertEqual(tools.count('Ambiente de publicação'),1)
        self.assertIn('data-publication-environments',tools)
        self.assertNotIn('data-release-flow-open',tools)

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

    def test_publications_page_auto_opens_release_deep_link_in_environment_workspace(self):
        self.assertIn("['variables','release'].includes(publicationDeepLinkOpen)",BASE)
        self.assertIn("publicationDeepLinkOpen==='release'?'release':'variables'",BASE)
        self.assertIn('publicationEnvironmentOpen(button,tool)',BASE)
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('window.CloudIFReleaseFlow = { mount: mountEmbedded }',release)
        self.assertNotIn("params.get('open') === 'release'",release)

    def test_publications_page_auto_opens_variables_deep_link(self):
        self.assertIn("const publicationDeepLink=new URLSearchParams(location.search)",BASE)
        self.assertIn("['variables','release'].includes(publicationDeepLinkOpen)",BASE)
        self.assertIn("publicationDeepLinkOpen==='release'?'release':'variables'",BASE)
        self.assertIn("x.dataset.projectSlug===publicationDeepLinkProject",BASE)
        self.assertIn("publicationEnvironmentOpen(button,tool)",BASE)

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
        self.assertIn('.publication-release-embedded',PUBLICATION_CSS)
        self.assertIn('.release-primary-action',PUBLICATION_CSS)
        self.assertIn('.nav-link{min-height:44px}',CSS)
        self.assertIn('.btn:focus-visible,.nav-link:focus-visible',CSS)

    def test_release_controls_are_embedded_in_environment_workspace(self):
        release=RELEASE_JS_PATH.read_text()
        self.assertIn('function mountEmbedded(detail = {})',release)
        self.assertIn('environmentToTab',release)
        self.assertIn('tabToEnvironment',release)
        self.assertIn('cloudif:publication-environment-select',release)
        self.assertNotIn("layer.id = 'cloudif-release-flow'",release)
        self.assertNotIn('release-wizard-close',release)

    def test_embedded_release_controls_keep_theme_tokens_and_mobile_layout(self):
        self.assertIn('_WHP_RELEASE_ASSETS',BASE)
        self.assertIn('cloudif-whp-release-script',BASE)
        self.assertNotIn('cloudif-whp-release-style',BASE)
        self.assertNotIn('/* CloudIFF W/H/P release wizard */',CSS)
        self.assertIn('/* CloudIFF W/H/P release wizard */',PUBLICATION_CSS)
        self.assertIn('.publication-release-embedded',PUBLICATION_CSS)
        self.assertIn('var(--surface)',PUBLICATION_CSS)
        self.assertIn('var(--rule)',PUBLICATION_CSS)
        self.assertIn('@media(max-width:700px)',PUBLICATION_CSS)
        self.assertNotIn('!important',PUBLICATION_CSS)
        self.assertNotIn('#cloudif-release-flow{',PUBLICATION_CSS)

if __name__=='__main__':unittest.main()
