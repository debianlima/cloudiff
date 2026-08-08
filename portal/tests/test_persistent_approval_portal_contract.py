from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PANEL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
GUIDE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
LEGACY_PANEL=ROOT/'portal/legacy/cloudif_approval_panel.py'
LEGACY_BASE=ROOT/'portal/legacy/cloudif-admin-portal-base.py'
LEGACY_GUIDE=ROOT/'portal/legacy/cloudif_ai_agents_guide.py'


class PersistentApprovalPortalContractTests(unittest.TestCase):
    def test_approval_panel_offers_always_allow_and_revocation(self):
        for path in (PANEL,LEGACY_PANEL):
            source=path.read_text()
            self.assertIn('name="always_allow" value="1"',source)
            self.assertIn('Sempre permitir',source)
            self.assertIn('name="operation" value="revoke_policy"',source)
            self.assertIn('Revogar sempre permitir',source)
            self.assertIn('def filter_policies',source)
            self.assertIn("authorization_mode')=='persistent_policy'",source)

    def test_portal_fetches_filters_and_revokes_policies_with_existing_csrf_guard(self):
        for path in (BASE,LEGACY_BASE):
            source=path.read_text()
            start=source.index('# CloudIF human approvals BEGIN')
            end=source.index('# CloudIF human approvals END',start)
            block=source[start:end]
            self.assertIn("'/v1/approval-policies?status=active'",block)
            self.assertIn('def _ap_visible_policies(user):',block)
            self.assertIn("val('always_allow')",block)
            self.assertIn("'always_allow':always_allow",block)
            self.assertIn("operation=='revoke_policy'",block)
            self.assertIn("'/v1/approval-policies/'",block)
            self.assertIn("'_prod_csrf_equal'".strip("'"),block)
            self.assertLess(block.index('_prod_csrf_equal'),block.index("operation=='revoke_policy'"))

    def test_approval_post_returns_to_canonical_v2_route_with_post_redirect_get(self):
        for path in (BASE,LEGACY_BASE):
            source=path.read_text()
            start=source.index('# CloudIF human approvals BEGIN')
            end=source.index('# CloudIF human approvals END',start)
            block=source[start:end]
            self.assertIn("target='/cloudiff/portal/?tab='+('agentes' if return_to=='agentes' else 'aprovacoes')",block)
            self.assertIn('self.send_response(303)',block)
            self.assertIn("self.send_header('Cache-Control','no-store')",block)
            self.assertIn("self.send_header('Pragma','no-cache')",block)
            self.assertNotIn("self.redirect('/cloudiff/portal/?tab='",block)

    def test_redirect_helper_is_idempotent_for_public_portal_paths(self):
        for path in (BASE,LEGACY_BASE):
            source=path.read_text()
            start=source.index('    def redirect(self, path=None):')
            end=source.index('\n    def do_GET(self):',start)
            block=source[start:end]
            self.assertIn('path.startswith(("/cloudiff/portal", "/cloudif/portal"))',block)
            self.assertLess(block.index('path.startswith(("/cloudiff/portal"'),block.index('path.startswith("/?")'))
            self.assertIn('bypass the v2 shell',block)

    def test_agents_tab_offers_same_persistent_choice(self):
        for path in (GUIDE,LEGACY_GUIDE):
            source=path.read_text()
            self.assertIn('name="always_allow" value="1"',source)
            self.assertIn('Sempre permitir esta ação neste projeto para este agente.',source)

    def test_existing_web_surfaces_remain_separate_modules(self):
        self.assertNotEqual(PANEL,BASE)
        self.assertIn('import cloudif_approval_panel as _ap_panel',BASE.read_text())
        self.assertIn('import cloudif_approval_panel as _ap_panel',LEGACY_BASE.read_text())


if __name__=='__main__':unittest.main()
