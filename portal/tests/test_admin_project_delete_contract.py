from pathlib import Path
import unittest

from portal.core.auth import Identity
from portal.core.rbac import is_global
from portal.ui import shell


class AdminProjectDeleteContractTest(unittest.TestCase):
    def setUp(self):
        self.admin = Identity('admin', 'admin@example.invalid', frozenset({'CloudIF-Tenants-Admin'}))
        self.professor = Identity('professor', 'professor@example.invalid', frozenset({'CloudIF-Professor'}))
        self.student = Identity('aluno', 'aluno@example.invalid', frozenset({'CloudIF-Aluno'}))

    def test_delete_navigation_is_visible_only_to_professor_or_admin(self):
        self.assertIn(('admin-excluir-projeto', 'Excluir projeto'), shell._TAB_GROUPS['Administração'])
        admin_doc = shell.render_legacy(self.admin, 'projetos', 'Projetos', '<p>x</p>', '', '')
        professor_doc = shell.render_legacy(self.professor, 'projetos', 'Projetos', '<p>x</p>', '', '')
        student_doc = shell.render_legacy(self.student, 'projetos', 'Projetos', '<p>x</p>', '', '')
        self.assertIn('admin-excluir-projeto', admin_doc)
        self.assertIn('admin-excluir-projeto', professor_doc)
        self.assertNotIn('admin-excluir-projeto', student_doc)
        self.assertTrue(is_global(self.admin))
        self.assertTrue(is_global(self.professor))
        self.assertFalse(is_global(self.student))

    def test_delete_module_preserves_tenant_and_requires_confirmation(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')
        self.assertIn("expected = f'EXCLUIR {slug}'", source)
        self.assertIn('tenant_preserved', source)
        self.assertIn('forja_rollback(slug, execute=True)', source)
        self.assertIn('BEGIN IMMEDIATE', source)
        self.assertIn('cloudif-project-state-reconcile.service', source)

    def test_portal_route_accepts_professor_or_admin_and_keeps_security_checks(self):
        source = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text(encoding='utf-8')
        self.assertIn('admin-excluir-projeto', source)
        self.assertIn('/cloudiff/portal/action/admin-delete-project', source)
        self.assertIn("'cloudif-professor'", source)
        self.assertIn('_prod_csrf_equal', source)
        self.assertIn('Acesso restrito a professor ou administrador.', source)


if __name__ == '__main__':
    unittest.main()
