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
