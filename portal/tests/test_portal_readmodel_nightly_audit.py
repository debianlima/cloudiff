from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
AUDIT=(ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-readmodel-audit.py').read_text()
REFRESH=(ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py').read_text()
SERVICE=(ROOT/'components/control-plane/etc/systemd/system/cloudif-portal-readmodel-audit.service').read_text()
TIMER=(ROOT/'components/control-plane/etc/systemd/system/cloudif-portal-readmodel-audit.timer').read_text()
PUBLICATIONS=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
PROVISION_WORKER=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
ENVIRONMENT_WEB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py').read_text()
PROJECT_DELETE=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
REFRESH_TIMER=(ROOT/'components/control-plane/etc/systemd/system/cloudif-portal-refresh-cache.timer').read_text()

class PortalReadModelNightlyAuditTests(unittest.TestCase):
    def test_public_catalog_is_db_backed(self):
        self.assertIn("join projects p on p.slug=i.project_slug",REFRESH)
        self.assertIn("reserved-public-numbers",REFRESH)
        self.assertIn("rm.put('projects','public-catalog'",REFRESH)
    def test_nightly_audit_is_read_only_for_runtime(self):
        self.assertIn("runtime_mutations_performed':False",AUDIT)
        self.assertIn("historical-production-online",AUDIT)
        self.assertIn("active-production-offline",AUDIT)
        self.assertNotIn("historical_publication_stop(",AUDIT)
        self.assertNotIn("_multiservice_deactivate(",AUDIT)
    def test_nightly_schedule_is_local_and_low_priority(self):
        self.assertIn('03:20:00 America/Sao_Paulo',TIMER)
        self.assertIn('Persistent=true',TIMER)
        self.assertIn('Nice=15',SERVICE)
        self.assertIn('IOSchedulingClass=idle',SERVICE)
    def test_publication_mutations_refresh_index(self):
        for marker in ('historical-production-started','historical-production-stopped','historical-production-deleted','production-rollback','homologation-created','production-published'):
            self.assertIn("project_changed(slug,'"+marker+"')",PUBLICATIONS)

    def test_other_state_producers_refresh_index(self):
        self.assertIn("project-provision-completed",PROVISION_WORKER)
        self.assertIn("project-provision-failed",PROVISION_WORKER)
        self.assertIn("environment-human-save",ENVIRONMENT_WEB)
        self.assertIn("environment-change-executed",ENVIRONMENT_WEB)
        self.assertIn("project-deleted",PROJECT_DELETE)
        self.assertIn("project-deletion-reconciled",PROJECT_DELETE)

    def test_periodic_refresh_is_safety_net_not_per_minute_poll(self):
        self.assertIn('OnUnitActiveSec=5min',REFRESH_TIMER)
        self.assertNotIn('OnUnitActiveSec=60s',REFRESH_TIMER)

if __name__=='__main__':unittest.main()
