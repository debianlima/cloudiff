from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
UI=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
COEXIST=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()

class ReleaseFlowWizardUITests(unittest.TestCase):
    def test_primary_ui_uses_w_h_p_and_no_direct_publish_button(self):
        self.assertIn('Preview → Homologação → Publicação',UI)
        self.assertIn('data-release-flow-open',UI)
        self.assertNotIn('>Publicar site<',UI)
        self.assertNotIn('>Publicar nova versão<',UI)
        self.assertIn('Detalhes técnicos e versões legadas',UI)

    def test_cached_legacy_publish_is_redirected_to_homologation(self):
        self.assertIn('publications.enqueue_homologation(slug,user)',BASE)
        self.assertNotIn('result=publications.enqueue_publish(slug,user)',BASE)
        self.assertIn('A ativação direta de artefatos dN foi desativada',BASE)

    def test_project_card_points_to_release_wizard_not_base_editor(self):
        block=BASE[BASE.index('<section class="project-final__section project-final__publication">'):]
        block=block[:block.index('</section>')+10]
        self.assertIn('W Preview · H Homologation · P Publication',block)
        self.assertIn('data-release-flow-open',block)
        self.assertNotIn('/publication/base/',block)

    def test_release_flow_api_is_csrf_protected(self):
        self.assertIn('/release-flow(?:/(approval/status))?',COEXIST)
        self.assertIn('/release-flow/(preview/ensure|preview/recreate|homologation/enqueue',COEXIST)
        self.assertIn("getattr(owner,'_prod_csrf_equal')",COEXIST)
        self.assertIn("'production/approval/request'",COEXIST)
        self.assertIn("'production/enqueue'",COEXIST)

    def test_wizard_has_dark_theme_safe_tokens_and_mobile_layout(self):
        self.assertIn('_WHP_RELEASE_ASSETS',BASE)
        self.assertIn('var(--c-surface)',BASE)
        self.assertIn('var(--c-border)',BASE)
        self.assertIn('@media(max-width:700px)',BASE)
        self.assertIn('W = Workspace Preview · H = Homologation · P = Publication',BASE)

if __name__=='__main__':unittest.main()
