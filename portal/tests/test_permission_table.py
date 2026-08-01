"""A2 acceptance: every migrated v2 guard decides exactly as the v1 table.

Loads config/permissions-v1-observed.json and replays the three personas through
every registered endpoint's guard, asserting the edge decision matches the
recorded v1 decision. Conditional rows must ALLOW at the edge (scope decides
later, inside the service), matching the v1 which lets the request in and then
filters by project visibility.

Also asserts the coverage invariant: every one of the 31 inventory routes is
either served by a module or explicitly deferred to legacy — never silently lost.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from portal.core.auth import Identity
from portal.wiring import all_endpoints

ROOT = pathlib.Path(__file__).resolve().parents[2]
OBSERVED = json.loads((ROOT / "config/permissions-v1-observed.json").read_text("utf-8"))
BY_KEY = {(r["path"], r["method"]): r for r in OBSERVED["routes_inventory_31"]}

PERSONAS = {
    "aluno": Identity("iff-aluno", "aluno@x", frozenset({"CloudIF-Tenants"})),
    "professor": Identity("iff-prof", "prof@x", frozenset({"CloudIF-Tenants", "CloudIF-Professor"})),
    "admin": Identity("akadmin", "adm@x", frozenset({"CloudIF-Tenants-Admin"})),
}


class PermissionTableTest(unittest.TestCase):
    # Rotas de página nativas da v2 (renderização da nova interface). Não existem
    # na tabela v1 porque são superfície nova; o acesso é validado por perfil nos
    # testes de paridade de visibilidade/execução (feitos contra a v1 viva).
    V2_PAGE_ROUTES = {
        ("/cloudiff/portal/pagina/projetos", "GET"),
        ("/cloudiff/portal/", "GET"),  # home com barra, equivale a /cloudiff/portal
    }

    def test_every_endpoint_matches_v1(self):
        for ep in all_endpoints():
            if (ep.path, ep.method) in self.V2_PAGE_ROUTES:
                continue
            observed = BY_KEY.get((ep.path, ep.method))
            self.assertIsNotNone(observed, f"{ep.method} {ep.path} ausente na tabela v1")
            for persona, identity in PERSONAS.items():
                want = observed["decisions"][persona]
                got = "allow" if ep.guard(identity) else "deny"
                if want == "conditional":
                    self.assertEqual(got, "allow",
                        f"{ep.method} {ep.path} [{persona}]: v1=conditional exige allow na borda")
                else:
                    self.assertEqual(got, want,
                        f"{ep.method} {ep.path} [{persona}]: v1={want}, v2={got}")

    def test_all_action_routes_declare_csrf(self):
        # A3: CSRF preserved on every /action/ route. F3: publication gains CSRF
        # in the v2 (the single sanctioned divergence), so it must be True here.
        for ep in all_endpoints():
            if ep.path.startswith("/action/") and ep.method == "POST":
                self.assertTrue(ep.csrf, f"A3: {ep.path} deve exigir CSRF")

    def test_no_route_lost(self):
        # Coverage invariant: the union of module routes and legacy-deferred
        # routes covers the full 31-route inventory.
        served = {(ep.path, ep.method) for ep in all_endpoints()}
        # GET-only proxy variant and internal token routes stay in legacy.
        # Kept in legacy on purpose: the control-dashboard proxy (auth delegated
        # to 127.0.0.1:18200), the shell navigation API, and the token-only
        # internal ingest routes (IP allowlist + bearer, not group-based).
        deferred = {
            ("/cloudiff/portal/control", "GET"),
            ("/cloudiff/portal/control/", "GET"),
            ("/control/api/dashboard", "GET"),
            ("/api/navigation", "GET"),
            ("/cloudiff/internal/access-ingest", "POST"),
            ("/cloudiff/internal/access-latest", "GET"),
        }
        inventory = set(BY_KEY)
        missing = inventory - served - deferred
        self.assertEqual(missing, set(), f"rotas perdidas (nem módulo nem legado): {missing}")


if __name__ == "__main__":
    unittest.main()
