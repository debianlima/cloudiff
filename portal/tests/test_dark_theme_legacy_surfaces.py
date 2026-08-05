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
