from pathlib import Path
import unittest
from portal.ui import shell


class AdminProjectDeleteContractTest(unittest.TestCase):
    def test_admin_navigation_contains_project_deletion(self):
        self.assertIn(("admin-excluir-projeto", "Excluir projeto"), shell._TAB_GROUPS["Administração"])

    def test_delete_module_preserves_tenant_and_requires_confirmation(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        self.assertIn("expected = f'EXCLUIR {slug}'", source)
        self.assertIn("tenant_preserved", source)
        self.assertIn("forja_rollback(slug, execute=True)", source)
        self.assertIn("BEGIN IMMEDIATE", source)
        self.assertIn("cloudif-project-state-reconcile.service", source)

    def test_portal_route_is_global_admin_only(self):
        source=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text(encoding='utf-8')
        self.assertIn("admin-excluir-projeto", source)
        self.assertIn("/cloudiff/portal/action/admin-delete-project", source)
        self.assertIn("_admin_project_delete_global", source)
        self.assertIn("_prod_csrf_equal", source)


if __name__ == '__main__':
    unittest.main()
