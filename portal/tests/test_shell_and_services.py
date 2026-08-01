"""Shell rendering and per-module service unit tests (A5)."""
from __future__ import annotations

import unittest

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

    def test_nav_links_only_ported_modules(self):
        # Regra "portar antes de linkar": só módulos em shell.PORTED viram link;
        # os demais aparecem desabilitados com marca "em breve".
        html = shell.render(self.admin, ["overview"], "overview", "Início", "")
        self.assertIn("Início", html)
        # Administração aparece, porém desabilitada (não é link) até ser portada.
        self.assertIn("Administração", html)
        self.assertIn("nav-link-soon", html)
        self.assertIn("em breve", html)
        # e não é um <a href> enquanto não estiver em PORTED
        self.assertNotIn('href="/cloudiff/portal?tab=admin"', html)


class ServiceTest(unittest.TestCase):
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

    def test_overview_fmt_bytes(self):
        # server_metrics() lê o banco; aqui validamos a formatação de bytes pura.
        f = overview_service._fmt_bytes
        self.assertEqual(f(0), "0 B")
        self.assertTrue(f(2 * 1024**3).endswith("GB"))
        self.assertEqual(f(None), "0 B")


if __name__ == "__main__":
    unittest.main()


class DataServiceTest(unittest.TestCase):
    def test_tenant_filter_and_render(self):
        from portal.modules.data import service as data_service
        from portal.modules.data import views as data_views
        entries = ["akadmin", "aluno", "BAD_NAME", "iff1742962", "x"]
        tenants = data_service.filter_tenants(entries)
        self.assertEqual(tenants, ["akadmin", "aluno", "iff1742962"])
        html_admin = data_views.tenant_grid(tenants, admin=True)
        self.assertIn("Avançado", html_admin)
        html_user = data_views.tenant_grid(tenants, admin=False)
        self.assertNotIn("Avançado", html_user)
        self.assertIn("akadmin", html_user)
