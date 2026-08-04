from pathlib import Path
import unittest
class TenantBackupAndTlsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.backup=Path('components/control-plane/usr/local/sbin/cloudif-tenant-db-backup-v2.sh').read_text()
  cls.worker=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
  cls.publisher=Path('components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text()
 def test_backup_discovers_tenants_dynamically(self):
  self.assertIn('for tdir in "$TENANTS"/*',self.backup)
  self.assertNotIn('[aluno]=cloudif_aluno-db-1',self.backup)
  self.assertIn('status=skipped reason=compose_missing',self.backup)
 def test_backup_preserves_stopped_state(self):
  self.assertIn('was_running=0',self.backup)
  self.assertIn('stop db',self.backup)
 def test_provisioner_enables_global_tenant_backup_timer(self):
  self.assertIn("'enable','--now','cloudif-tenant-db-backup-v2.timer'",self.worker)
 def test_publisher_uses_graceful_nginx_reload(self):
  self.assertIn("'nginx','-t'",self.publisher)
  self.assertIn("'nginx','-s','reload'",self.publisher)
  self.assertNotIn("'docker','restart','cloudif-nginx-proxy-manager'",self.publisher)
if __name__=='__main__':unittest.main()
