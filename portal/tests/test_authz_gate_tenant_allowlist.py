from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'components/control-plane/usr/local/sbin/cloudif-authz-gate.py'


def load_module():
    spec = importlib.util.spec_from_file_location('cloudif_authz_gate_allowlist_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class AuthzGateTenantAllowlistTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.module.ACCESS_DIR = Path(self.temp.name)
        self.module.ADMIN_USERS = {'admin-user'}
        self.module.ADMIN_GROUPS = {'cloudif-tenants-admin'}

    def tearDown(self):
        self.temp.cleanup()

    def write_access(self, tenant, users='', groups=''):
        (self.module.ACCESS_DIR / f'{tenant}.users').write_text(users, encoding='utf-8')
        (self.module.ACCESS_DIR / f'{tenant}.groups').write_text(groups, encoding='utf-8')

    def test_owner_from_materialized_project_acl_is_allowed(self):
        self.write_access('iff1860746-silvipro', users='iff1860746\n')
        allowed, reason = self.module.authorize_tenant(
            'iff1860746', {'domain users'}, 'iff1860746-silvipro'
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, 'tenant-user-allowlist')

    def test_materialized_group_is_allowed_with_pipe_headers(self):
        self.write_access('tenant-lab', groups='CloudIF-Lab-Readers\n')
        parsed = self.module.groups_to_set('Domain Users|CloudIF-Lab-Readers;Other')
        allowed, reason = self.module.authorize_tenant('student', parsed, 'tenant-lab')
        self.assertTrue(allowed)
        self.assertEqual(reason, 'tenant-group-allowlist')

    def test_unknown_user_remains_denied(self):
        self.write_access('tenant-lab', users='owner\n', groups='readers\n')
        allowed, reason = self.module.authorize_tenant('unknown', {'other'}, 'tenant-lab')
        self.assertFalse(allowed)
        self.assertEqual(reason, 'user-unknown-cannot-access-tenant-tenant-lab')

    def test_admin_and_legacy_tenant_owner_still_work(self):
        self.assertEqual(
            self.module.authorize_tenant('tenant-lab', set(), 'tenant-lab'),
            (True, 'user-matches-tenant'),
        )
        self.assertEqual(
            self.module.authorize_tenant('admin-user', set(), 'tenant-lab'),
            (True, 'admin-user'),
        )
        self.assertEqual(
            self.module.authorize_tenant('other', {'cloudif-tenants-admin'}, 'tenant-lab'),
            (True, 'admin-group'),
        )

    def test_invalid_tenant_cannot_escape_access_directory(self):
        self.write_access('safe-tenant', users='allowed\n')
        users, groups = self.module.load_tenant_access('../safe-tenant')
        self.assertEqual(users, set())
        self.assertEqual(groups, set())
        self.assertEqual(
            self.module.tenant_from_request('../safe-tenant.cloudiff.duckdns.org', '/'),
            '',
        )


if __name__ == '__main__':
    unittest.main()
