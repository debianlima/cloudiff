from types import SimpleNamespace
import unittest

from portal.app import handle
from portal.core.auth import Identity
from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
from portal.registry import Registry


def _identity(*groups):
    return Identity("u", "u@x", frozenset(groups))


def _req(path, method="GET", **kw):
    return Request(path, method, kw.pop("identity", _identity()),
                   headers={"Host": "cloudiff.duckdns.org"}, form=kw.pop("form", {}))


class RegistryTest(unittest.TestCase):
    def test_empty_registry_falls_back_to_legacy(self):
        request = SimpleNamespace(path="/legacy", method="GET")
        self.assertEqual(handle(request, lambda r: ("legacy", r.path)), ("legacy", "/legacy"))

    def test_duplicate_route_is_rejected(self):
        reg = Registry()
        ep = Endpoint("/health", "GET", "health.view", lambda i: True,
                      lambda r: Response.html("ok"), "health")
        reg.register(ep)
        with self.assertRaises(ValueError):
            reg.register(ep)

    def test_method_disambiguates_same_path(self):
        reg = Registry()
        reg.register(Endpoint("/x", "GET", "x.view", lambda i: True, lambda r: Response.html("get"), "x"))
        reg.register(Endpoint("/x", "POST", "x.act", lambda i: True, lambda r: Response.html("post"), "x"))
        self.assertEqual(reg.match("/x", "GET").view(_req("/x")).body, b"get")
        self.assertEqual(reg.match("/x", "POST").view(_req("/x", "POST")).body, b"post")

    def test_navigation_is_filtered_before_render(self):
        reg = Registry()
        reg.register(Endpoint("/health", "GET", "health.view", lambda i: True, lambda r: Response.html("ok"), "health"))
        reg.register(Endpoint("/admin", "GET", "admin.view", lambda i: True, lambda r: Response.html("ok"), "admin"))
        nav = reg.navigation(lambda p: p == "health.view")
        self.assertEqual([e.path for e in nav], ["/health"])


if __name__ == "__main__":
    unittest.main()
