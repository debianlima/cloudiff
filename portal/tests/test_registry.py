from types import SimpleNamespace
import unittest

from portal.app import handle
from portal.registry import Registry, Route


class RegistryTest(unittest.TestCase):
    def test_empty_registry_falls_back_to_legacy(self):
        request = SimpleNamespace(path="/legacy")
        self.assertEqual(handle(request, lambda req: ("legacy", req.path)), ("legacy", "/legacy"))

    def test_route_requires_permission(self):
        with self.assertRaises(ValueError):
            Route("/health", "", lambda request: "ok", "health")

    def test_duplicate_route_is_rejected(self):
        registry = Registry()
        route = Route("/health", "health.view", lambda request: "ok", "health")
        registry.register(route)
        with self.assertRaises(ValueError):
            registry.register(route)

    def test_navigation_is_filtered_before_render(self):
        registry = Registry()
        registry.register(Route("/health", "health.view", lambda request: "ok", "health"))
        registry.register(Route("/admin", "admin.view", lambda request: "ok", "admin"))
        routes = registry.navigation(lambda permission: permission == "health.view")
        self.assertEqual([route.path for route in routes], ["/health"])


if __name__ == "__main__":
    unittest.main()
