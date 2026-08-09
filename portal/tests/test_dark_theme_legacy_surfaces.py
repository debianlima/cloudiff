from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DarkThemeLegacySurfacesTest(unittest.TestCase):
    def test_active_legacy_modules_use_theme_tokens_for_surfaces(self):
        modules = (
            ROOT / "portal/legacy/cloudif_ai_agents_guide.py",
            ROOT / "portal/legacy/cloudif_portal_sections98.py",
            ROOT / "portal/legacy/cloudif_unique_pages98.py",
        )
        for path in modules:
            source = path.read_text()
            compact = source.replace(" ", "").lower()
            self.assertNotIn("background:#fff", compact, path)
            self.assertNotIn("background:white", compact, path)
            self.assertIn("background:var(--surface)", compact, path)
            self.assertIn("color:var(--ink)", compact, path)

    def test_agent_details_are_theme_surfaces(self):
        source = (ROOT / "portal/legacy/cloudif_ai_agents_guide.py").read_text()
        self.assertIn(
            ".agent-detail{padding:16px;border:1px solid var(--rule);"
            "border-radius:14px;background:var(--surface);color:var(--ink)}",
            source,
        )
        self.assertIn(
            ".agent-security>details{padding:16px;border:1px solid var(--rule);"
            "border-radius:14px;background:var(--surface);color:var(--ink)}",
            source,
        )

    def test_final_dark_guard_covers_page_local_modules(self):
        css = (ROOT / "portal/design/components.css").read_text()
        for selector in (
            ".agent-detail",
            ".agent-provider-grid details",
            ".s98-hero",
            ".s98-kpi",
            ".s98-item",
            ".u98-kpi",
            ".u98-panel",
            ".u98-row",
        ):
            self.assertIn(
                'html[data-theme="dark"] body .legacy-content ' + selector,
                css,
            )
        self.assertIn("Final dark-surface guard for page-local legacy CSS", css)

    def test_final_dark_guard_covers_projects_banks_and_help(self):
        css = (ROOT / "portal/design/components.css").read_text()
        for selector in (
            ".project-management-final",
            ".project-final",
            ".project-final__grid",
            ".project-final__section",
            ".db96-compact",
            ".db96-service-list",
            ".db96-permissions-content",
            ".guide-connection-project",
            ".guide-connection-url",
            ".guide-connection-note",
        ):
            self.assertIn(
                'html[data-theme="dark"] body .legacy-content ' + selector,
                css,
            )
        self.assertIn(
            "Final dark guard for project, tenant and guide surfaces",
            css,
        )

    def test_playwright_regressions_do_not_force_legacy_details_white(self):
        current = (ROOT / "components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py").read_text()
        legacy = (ROOT / "portal/legacy/cloudif-admin-portal-base.py").read_text()
        for source in (current, legacy):
            self.assertIn(
                'details:not(.enterprise-nav details){border-color:var(--ui141-border)!important;background:var(--ui141-surface)!important}',
                source,
            )
            self.assertNotIn(
                'details:not(.enterprise-nav details){border-color:var(--ui141-border)!important;background:#fff!important}',
                source,
            )
            self.assertIn('html[data-theme=\"dark\"]{color-scheme:dark;--c-bg:#0d1320;', source)

    def test_dark_semantic_buttons_and_database_labels_keep_contrast(self):
        current = (ROOT / "components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py").read_text()
        self.assertIn('html[data-theme="dark"] .btn:not(.light):not(.gray)', current)
        self.assertIn('color:var(--on-iff,#061009)!important', current)
        css = (ROOT / "portal/design/components.css").read_text()
        self.assertIn('html[data-theme="dark"] body .legacy-content .db96-eyebrow{', css)
        self.assertIn('html[data-theme="dark"] body .legacy-content .db96-mode.active .db96-check{', css)
        coexist = (ROOT / "components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py").read_text()
        self.assertIn('button[aria-selected="true"]{{border-color:var(--iff)!important;background:var(--iff-wash)!important;color:var(--ink)!important}}', coexist)

    def test_admin_and_guide_local_css_use_theme_surfaces(self):
        source = (ROOT / "components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py").read_text()
        admin = source[source.index('.admin-operation-center'):source.index('</style>', source.index('.admin-operation-center'))]
        self.assertIn('background:var(--surface)!important', admin)
        self.assertIn('background:var(--surface);color:var(--ink)', admin)
        self.assertIn('background:var(--rule-soft);color:var(--ink)', admin)
        global_css = source[source.index('.global-admin-hub'):source.index('</style>', source.index('.global-admin-hub'))]
        self.assertNotIn('background:#fff', global_css)
        self.assertIn('color:var(--iff-dark)', global_css)
        guide_css = source[source.index('.platform-guide'):source.index('</style>', source.index('.platform-guide'))]
        self.assertIn('.guide-repository-kicker', guide_css)
        self.assertIn('color:var(--iff-dark)', guide_css)

    def test_code_blocks_keep_a_dark_terminal_surface_in_both_themes(self):
        css = (ROOT / "portal/design/components.css").read_text()
        self.assertIn(
            '.legacy-content pre{padding:var(--s4);border-radius:var(--r-md);background:var(--terminal-bg);color:var(--terminal-ink)',
            css,
        )

    def test_canonical_help_uses_theme_tokens_for_connection_surfaces(self):
        source = (
            ROOT
            / "components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py"
        ).read_text()
        help_css = source[
            source.index(".guide-connection-url") :
            source.index("@media(max-width:1100px)", source.index(".guide-connection-url"))
        ]
        for marker in (
            "background:var(--rule-soft",
            "background:var(--paper",
            "background:var(--surface",
            "color:var(--ink",
            "border:1px solid var(--rule",
        ):
            self.assertIn(marker, help_css)
        for forbidden in (
            "background:#f4f7f5",
            "background:#f7faf8",
            "background:#fff",
        ):
            self.assertNotIn(forbidden, help_css)

    def test_runtime_copies_match_canonical_modules(self):
        pairs = (
            ("cloudif_ai_agents_guide.py",),
            ("cloudif_portal_sections98.py",),
            ("cloudif_unique_pages98.py",),
        )
        for (name,) in pairs:
            canonical = ROOT / "portal/legacy" / name
            runtime = ROOT / "components/control-plane/current-apps/portal-current" / name
            self.assertEqual(canonical.read_bytes(), runtime.read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
