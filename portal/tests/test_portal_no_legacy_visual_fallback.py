from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
PORTAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
PUB_CURRENT=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py'
PUB_SHARED=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_ui_publications.py'


class PortalNoLegacyVisualFallbackTests(unittest.TestCase):
    def test_base_workspace_uses_dedicated_get_route(self):
        portal=PORTAL.read_text();current=PUB_CURRENT.read_text();shared=PUB_SHARED.read_text();coexist=COEXIST.read_text()
        for source in (current,shared):
            self.assertIn('/cloudiff/portal/publication/base/',source)
            self.assertNotIn('name="op" value="open_base_workspace"',source)
            self.assertNotIn('target="_blank" action="/cloudiff/portal/action/publication"',source)
        renderer=portal[portal.index('def _pm197_render'):portal.index('render_projects=_pm197_render')]
        self.assertIn('href="/cloudiff/portal/publication/base/{h(slug)}"',renderer)
        self.assertNotIn('name="op" value="open_base_workspace"',renderer)
        self.assertIn('publication_base_workspace_prepare_redirect',portal)
        self.assertIn('/cloudiff/portal/publication/base/"+_cloudif_pub_urlparse.quote(slug,safe="")',portal)
        self.assertIn("base_workspace_match = re.fullmatch(r'/cloudiff?/portal/publication/base/",coexist)
        self.assertIn('publications.base_workspace_preflight(slug,user)',coexist)

    def test_adapter_never_returns_legacy_html_as_visual_fallback(self):
        source=COEXIST.read_text()
        self.assertIn('legacy',source)
        self.assertIn('HTML is never exposed as a visual fallback',source)
        self.assertIn('def recovery_page(',source)
        self.assertIn('cloudif_portal_v2_transform_failed',source)
        self.assertIn('cloudif_portal_v2_post_transform_failed',source)
        self.assertIn("recovery_page('Não foi possível montar esta tela'",source)
        self.assertNotIn('Auto-recovery: return byte-identical legacy output.',source)
        self.assertNotIn('Any adapter exception returns the exact legacy response.',source)
        self.assertNotIn("try:\n                    wrap(handler)\n                except Exception:\n                    pass",source)
        self.assertIn('if os.environ.get("CLOUDIF_PORTAL_V2") == "1":\n        raise',source)

    def test_base_workspace_errors_stay_on_modern_recovery_page(self):
        source=COEXIST.read_text()
        self.assertIn("recovery_page('Acesso ao terminal não autorizado'",source)
        self.assertIn("recovery_page('Não foi possível preparar o terminal'",source)
        self.assertIn("return send(self,503,'text/html; charset=utf-8',body)",source)
        self.assertIn('Tentar novamente',source)
        self.assertIn('Voltar aos projetos',source)


if __name__=='__main__':
    unittest.main()
