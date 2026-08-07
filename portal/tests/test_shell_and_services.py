"""Shell rendering and per-module service unit tests (A5)."""
from __future__ import annotations

import unittest
from pathlib import Path

from portal.core.auth import Identity
from portal.modules.delivery import service as delivery_service
from portal.modules.environments import service as env_service
from portal.modules.health import service as health_service
from portal.modules.overview import service as overview_service
from portal.ui import shell


class ShellTest(unittest.TestCase):
    def setUp(self):
        self.admin = Identity("akadmin", "a@x", frozenset({"CloudIF-Tenants-Admin"}))

    def test_renders_institutional_footer_and_profile(self):
        html = shell.render(self.admin, ["overview", "health", "admin"], "overview", "Início", "<p>x</p>")
        self.assertIn("Bom Jesus do Itabapoana", html)
        self.assertIn("(22) 3833-9850", html)
        self.assertIn("CloudIF-Tenants-Admin", html)  # primary group in profile
        self.assertIn('aria-current="page"', html)

    def test_navigation_is_stable_across_native_modules(self):
        doc = shell.render(self.admin, ["overview"], "overview", "Resumo", "<p>ok</p>")
        self.assertIn('href="/cloudiff/portal/?tab=resumo"', doc)
        self.assertIn('href="/cloudiff/portal/?tab=projetos"', doc)
        self.assertIn('href="/cloudiff/portal/?tab=bancos"', doc)
        self.assertIn('href="/cloudiff/portal/?tab=backup"', doc);self.assertIn('href="/cloudiff/portal/?tab=agentes"', doc)


    def test_health_summary_and_score(self):
        items = [{"healthy": True}, {"healthy": True}, {"state": "unlinked"}, {"state": "unknown"}]
        summary = health_service.summarize_repairs(items)
        self.assertEqual(summary, {"ok": 2, "warn": 0, "bad": 2, "total": 4})
        self.assertEqual(health_service.score(summary), 50)
        self.assertEqual(health_service.score({"total": 0}), 0)

    def test_environments_window_and_incident(self):
        self.assertTrue(env_service.window_is_valid(600))
        self.assertFalse(env_service.window_is_valid(60))
        self.assertFalse(env_service.window_is_valid(3600))
        self.assertEqual(env_service.incident_status("close"), "closed")

    def test_delivery_promotions_gate(self):
        self.assertTrue(delivery_service.can_see_promotions({"sistema-de-biblioteca-teste"}))
        self.assertFalse(delivery_service.can_see_promotions({"outro"}))

    def test_overview_server_aggregate(self):
        nodes = [
            {"ram_used": 2, "ram_total": 4, "disk_used": 10, "disk_total": 50, "online": True},
            {"ram_used": 3, "ram_total": 6, "disk_used": 44, "disk_total": 61, "online": False},
        ]
        agg = overview_service.aggregate_servers(nodes)
        self.assertEqual(agg["ram_used"], 5)
        self.assertEqual(agg["ram_total"], 10)
        self.assertEqual(agg["online"], 1)
        self.assertEqual(agg["count"], 2)


    def test_shell_has_keyboard_skip_link(self):
        root = Path(__file__).resolve().parents[1]
        shell = (root / "ui" / "shell.py").read_text()
        css = (root / "design" / "base.css").read_text()
        self.assertIn('class="skip-link" href="#conteudo-principal"', shell)
        self.assertIn('.skip-link:focus', css)


if __name__ == "__main__":
    unittest.main()


class DataServiceTest(unittest.TestCase):
    def test_tenant_screen_remains_on_legacy_adapter(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "modules" / "data").exists())
        self.assertEqual(shell._MODULE_TO_TAB["data"], "bancos")
        coexist = (root.parent / "components" / "control-plane" / "srv" / "cloudif" / "lib" / "cloudif_portal_v2_coexist.py").read_text()
        self.assertIn("legacy", coexist.lower())
