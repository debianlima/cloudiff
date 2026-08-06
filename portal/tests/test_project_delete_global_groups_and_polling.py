from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
LEGACY=ROOT/'portal/legacy/cloudif-admin-portal-base.py'
LAUNCHER=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


class ProjectDeleteGlobalGroupsAndPollingTests(unittest.TestCase):
    def test_canonical_admin_identity_does_not_query_settings_database(self):
        for path in (BASE,LEGACY):
            source=path.read_text()
            start=source.index('def is_admin(groups):')
            end=source.index('\ndef can_create_tenant',start)
            block=source[start:end]
            self.assertIn('"cloudif-tenants-admin" in current',block)
            self.assertNotIn('setting_list',block)
            self.assertNotIn('domain admins',block)
            self.assertNotIn('sqlite3',block)

    def test_delete_global_policy_includes_admin_and_professor_only(self):
        for path in (BASE,LEGACY):
            source=path.read_text()
            start=source.index('def _admin_project_delete_global(user):')
            end=source.index('def _admin_project_delete_allowed',start)
            block=source[start:end]
            self.assertIn("{'cloudif-tenants-admin','cloudif-professor'}",block)
            self.assertNotIn('domain admins',block)
            self.assertNotIn("user.get('admin')",block)

    def test_launcher_accepts_already_canonical_base(self):
        source=LAUNCHER.read_text()
        self.assertIn('if _POLICY_OLD in source:',source)
        self.assertIn('elif _POLICY_NEW not in source:',source)
        self.assertNotIn('if source.count(_POLICY_OLD) != 1:',source)

    def test_status_polling_uses_authenticated_headers_without_sqlite_user_lookup(self):
        source=COEXIST.read_text()
        start=source.index('if path in {"/cloudif/portal/api/admin-delete-project-status"')
        end=source.index('if path in {"/cloudif/portal/api/admin-ad-search"',start)
        block=source[start:end]
        self.assertIn('actor = identity(self.headers)',block)
        self.assertIn('"cloudif-tenants-admin", "cloudif-professor"',block)
        self.assertIn('can_read_job(job_id,actor.username,global_access)',block)
        self.assertIn('delete_status_unavailable',block)
        self.assertNotIn('self.user()',block)
        self.assertNotIn('setting_value',block)
        self.assertNotIn('sqlite3',block)

    def test_async_delete_uses_header_identity_and_keeps_csrf_wizard_checks(self):
        source=COEXIST.read_text()
        start=source.index('if value("async") == "1":')
        end=source.index('self.rfile = BytesIO(raw)',start)
        block=source[start:end]
        self.assertIn('actor = identity(self.headers)',block)
        self.assertIn('_prod_csrf_equal',block)
        self.assertIn('_admin_project_delete_allowed',block)
        self.assertIn('consume_wizard_token',block)
        self.assertIn('start_job',block)
        self.assertNotIn('self.user()',block)
        self.assertLess(block.index('_prod_csrf_equal'),block.index('start_job'))
        self.assertLess(block.index('consume_wizard_token'),block.index('start_job'))


if __name__=='__main__':
    unittest.main()
