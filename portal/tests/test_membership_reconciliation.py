from pathlib import Path
import unittest

class MembershipReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.client=Path('components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py').read_text()
        cls.worker=Path('components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py').read_text()
        cls.forja=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
        cls.komodo=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_project_and_tenant_events_are_supported(self):
        self.assertIn('"project.membership.changed"',self.client)
        self.assertIn('"tenant.membership.changed"',self.client)
        self.assertIn('"project.membership.changed"',self.portal)
        self.assertIn('"tenant.membership.changed"',self.portal)
    def test_worker_applies_complete_current_state(self):
        for marker in ('def project_membership_snapshot','def tenant_membership_snapshot','def reconcile_project_membership','def reconcile_tenant_membership','TENANT_ACCESS_DIR'):
            self.assertIn(marker,self.worker)
        self.assertIn("'/project/membership/reconcile'",self.worker)
        self.assertIn("'/komodo/project/membership/reconcile'",self.worker)
    def test_forgejo_only_removes_managed_collaborators(self):
        for marker in ('managed_collaborators','previous-desired','permission\':\'write','reconcile_project_membership'):
            self.assertIn(marker,self.forja)
    def test_komodo_creates_and_removes_per_user_terminals(self):
        for marker in ('project_member_terminals','cloudif_project_membership_reconcile','CreateTerminal','DeleteTerminal','desired_users'):
            self.assertIn(marker,self.komodo)
        self.assertIn('active_publication',self.komodo)

if __name__=='__main__':unittest.main()
