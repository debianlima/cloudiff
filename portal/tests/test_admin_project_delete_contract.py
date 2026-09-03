from pathlib import Path
import unittest

from portal.core.auth import Identity
from portal.core.rbac import is_admin, is_admin_legacy, is_global, is_professor, is_student
from portal.ui import shell


class AdminProjectDeleteContractTest(unittest.TestCase):
    def setUp(self):
        self.admin = Identity('admin', 'admin@example.invalid', frozenset({'CloudIF-Tenants-Admin'}))
        self.professor = Identity('professor', 'professor@example.invalid', frozenset({'CloudIF-Professor'}))
        self.student = Identity('aluno', 'aluno@example.invalid', frozenset({'CloudIF-Aluno'}))
        self.domain_admin = Identity('domain-admin', 'da@example.invalid', frozenset({'Domain Admins'}))
        self.legacy_admin = Identity('admin', 'legacy@example.invalid', frozenset())

    def test_profiles_use_only_canonical_cloudif_groups(self):
        self.assertTrue(is_admin(self.admin))
        self.assertTrue(is_professor(self.professor))
        self.assertTrue(is_student(self.student))
        self.assertFalse(is_global(self.student))
        self.assertFalse(is_admin(self.domain_admin))
        self.assertFalse(is_global(self.domain_admin))
        self.assertFalse(is_admin_legacy(self.legacy_admin))

    def test_delete_navigation_is_visible_only_to_cloudif_professor_or_admin(self):
        self.assertIn(('admin-excluir-projeto', 'Excluir projeto'), shell._TAB_GROUPS['Administração'])
        admin_doc = shell.render_legacy(self.admin, 'projetos', 'Projetos', '<p>x</p>', '', '')
        professor_doc = shell.render_legacy(self.professor, 'projetos', 'Projetos', '<p>x</p>', '', '')
        student_doc = shell.render_legacy(self.student, 'projetos', 'Projetos', '<p>x</p>', '', '')
        domain_admin_doc = shell.render_legacy(self.domain_admin, 'projetos', 'Projetos', '<p>x</p>', '', '')
        self.assertIn('admin-excluir-projeto', admin_doc)
        self.assertIn('admin-excluir-projeto', professor_doc)
        self.assertNotIn('admin-excluir-projeto', student_doc)
        self.assertNotIn('admin-excluir-projeto', domain_admin_doc)

    def test_delete_module_preserves_tenant_and_requires_confirmation(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        self.assertIn("expected = f'EXCLUIR {slug}'", source)
        self.assertIn("normalized.casefold() == expected.casefold()", source)
        self.assertIn("if not _confirmation_matches(slug, confirmation)", source)
        self.assertIn('tenant_preserved', source)
        self.assertIn('forja_rollback(slug, execute=True, include_komodo=False)', source)
        self.assertIn('BEGIN IMMEDIATE', source)
        self.assertIn('cloudif-project-state-reconcile.service', source)

    def test_portal_route_keeps_csrf_and_exact_cloudif_groups(self):
        source = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text(encoding='utf-8')
        base = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text(encoding='utf-8')
        self.assertIn("{'cloudif-tenants-admin','cloudif-professor'}", source)
        self.assertNotIn("'domain admins','cloudif-professor'", source)
        self.assertIn('/cloudiff/portal/action/admin-delete-project', base)
        self.assertIn('_prod_csrf_equal', base)


if __name__ == '__main__':
    unittest.main()
