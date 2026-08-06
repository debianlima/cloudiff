from pathlib import Path
import unittest


class ConcurrentProjectTenantOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.action = Path('components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
        cls.worker = Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
        cls.create_tenant = Path('components/control-plane/srv/cloudif/bin/cloudif-create-tenant.real.sh').read_text()
        cls.delete_tenant = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text()
        cls.publish = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text()
        cls.portal = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.status = Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_status.py').read_text()

    def test_project_job_uses_uuid_and_systemd_owned_lock(self):
        for marker in (
            'uuid.uuid4().hex', 'project-{job[\'slug\']}.lock',
            'fcntl.LOCK_EX | fcntl.LOCK_NB', '"/usr/bin/systemd-run"',
            '"/usr/bin/flock"', '"--property=RuntimeMaxSec=4h"',
            'job["systemd_unit"]', 'DEDUP',
        ):
            self.assertIn(marker, self.action)
        launch = self.action[self.action.index('def _start_project_provision_unit'):self.action.index('def queue_provision_job')]
        self.assertNotIn('pass_fds=', launch)
        self.assertNotIn('start_new_session=True', launch)

    def test_create_and_delete_share_same_tenant_lock_namespace(self):
        self.assertIn('/run/cloudif-operation-locks', self.create_tenant)
        self.assertIn('tenant-${TENANT}.lock', self.create_tenant)
        self.assertIn('/run/cloudif-operation-locks', self.delete_tenant)
        self.assertIn('tenant-{tenant}.lock', self.delete_tenant)
        self.assertIn('fcntl.flock(tenant_lock_fd, fcntl.LOCK_EX)', self.delete_tenant)

    def test_initial_publication_uses_single_versioned_operation_with_long_timeouts(self):
        self.assertIn("'timeout': 600", self.publish)
        self.assertIn("CLOUDIF_D1_DEPLOY_REQUEST_TIMEOUT", self.publish)
        self.assertIn("'1500'", self.publish)
        self.assertIn("versioned_deploy_not_ready", self.publish)
        self.assertIn("initial_publication_failed: ", self.worker)
        self.assertIn('cloudif_project_provision_status', self.portal)
        self.assertIn("current_step='initial-publication'", self.status)
        self.assertIn("recovery_action':'resume_initial_publication'", self.status)
        self.assertIn("'recoverable':recoverable", self.status)



if __name__ == '__main__':
    unittest.main()
