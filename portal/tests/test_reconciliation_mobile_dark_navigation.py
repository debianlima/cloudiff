import unittest
from pathlib import Path
from portal.core.auth import Identity
from portal.core.legacy_shell import transform

ROOT=Path(__file__).resolve().parents[2]
COMPONENTS=(ROOT/'portal/design/components.css').read_text()
COEXIST=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()


class ReconciliationMobileDarkNavigationTests(unittest.TestCase):
    def test_project_context_active_state_uses_global_theme_tokens(self):
        self.assertIn('.project-context-primary a[aria-current="page"]{background:var(--iff-wash);color:var(--iff-dark);font-weight:750}',COMPONENTS)
        self.assertNotIn('.project-context-group',COMPONENTS)
        self.assertIn('html[data-theme="dark"] body.project-context-route{background:var(--paper);color:var(--ink)}',COMPONENTS)
        self.assertIn('html[data-theme="dark"] .tab-git .legacy-content',COMPONENTS)
        self.assertIn(':is(.ci-section,.ci-step,.ci-project-card,.ci-modal-card,.ci-choice,.ci-menu summary,.ci-menu-body,.ci-menu-body a,.ci-menu-body button)',COMPONENTS)
        self.assertIn('background:var(--surface);color:var(--ink);border-color:var(--rule)',COMPONENTS)
        self.assertIn('html[data-theme="dark"] .tab-git .legacy-content .ci-step strong{color:var(--iff-dark)}',COMPONENTS)
        self.assertIn('html[data-theme="dark"] .tab-git .legacy-content code{',COMPONENTS)
        self.assertIn(':is(.ci-pill-ok,.pill.ok,.badge.ok)',COMPONENTS)
        self.assertIn('background:var(--iff-wash);color:var(--iff-dark);border-color:var(--rule)',COMPONENTS)
        self.assertIn(':is(.ci-pill-off,.ci-pill:not(.ci-pill-ok),.pill:not(.ok),.badge:not(.ok))',COMPONENTS)

    def test_mobile_context_and_topbar_controls_keep_minimum_touch_targets(self):
        self.assertIn('.theme-menu>summary,.profile-menu>summary{display:flex;align-items:center;justify-content:center;min-width:40px;min-height:40px}',COMPONENTS)
        self.assertIn('.project-context-primary a,.project-context-more a{min-height:40px}',COMPONENTS)
        self.assertIn('.theme-menu .theme-picker button,.profile-card a{min-height:40px}',COMPONENTS)
        self.assertIn('.theme-menu .theme-picker{position:fixed;right:var(--s3);top:var(--bar-h);width:150px}.theme-menu .theme-picker button{min-height:40px}',COMPONENTS)

    def test_production_denial_is_adapted_without_changing_http_status(self):
        self.assertIn('adapt_production_denial = status == 403 and tab == "operacao-producao"',COEXIST)
        self.assertIn('if (status == 200 or adapt_production_denial) and content_type.lower().startswith("text/html"):',COEXIST)
        self.assertIn('return send(self, status, "text/html; charset=utf-8", adapted, captured_headers)',COEXIST)

    def test_legacy_production_denial_can_render_inside_canonical_shell(self):
        legacy='''<!doctype html><html><head><title>CloudIF Portal</title><style>body{background:white}.card{padding:12px}</style></head><body><main id="conteudo-principal"><section class="card"><h2>Operação de produção</h2><p class="pill bad">Projeto não autorizado.</p></section></main></body></html>'''
        identity=Identity('iff1742962','iff1742962@example.invalid',frozenset({'CloudIF-Tenants'}))
        doc=transform(legacy,identity,'operacao-producao')
        self.assertIn('class="tab-operacao-producao project-context-route"',doc)
        self.assertIn('aria-label="Navegação do projeto"',doc)
        self.assertIn('href="/cloudiff/portal/?tab=operacao-producao" data-project-context-link aria-current="page">Produção</a>',doc)
        self.assertIn('Projeto não autorizado.',doc)
        self.assertIn('/cloudiff/portal/assets/components.css',doc)


if __name__=='__main__':
    unittest.main()
