from pathlib import Path
import unittest

class BackupRemoteGlobalConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        cls.backup=Path('components/control-plane/usr/local/sbin/cloudif-project-backup.py').read_text()
        cls.worker=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
        cls.delete=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
    def test_admin_can_edit_remote_backup_target(self):
        for marker in ('Servidor remoto de backup','backup-remote-config','remote_host','remote_path','if not user.get("admin")','invalid_host','invalid_key_path'):
            self.assertIn(marker,self.portal)
    def test_remote_status_uses_canonical_host_and_tcp_probe(self):
        self.assertIn('10.68.128.250',self.portal)
        self.assertIn('["nc", "-z", "-w", "3", host, str(port)]',self.portal)
        self.assertIn("def remote_probe():",self.backup)
        self.assertIn("'host':env.get('REMOTE_HOST','10.68.128.250')",self.backup)
    def test_provisioning_has_backup_stage(self):
        self.assertIn("'backup-configuration'",self.worker)
        self.assertIn("cloudif-project-backup.py','set-auto'",self.worker)
    def test_platform_backup_has_action_history_and_download(self):
        for marker in ('Backup da plataforma','data-platform-backup','platform_backup','download/platform-backup'):
            self.assertTrue(marker in self.portal or marker in Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text())

    def test_project_delete_cleans_project_backup_state(self):
        self.assertIn('_delete_backup_state(slug)',self.delete)
        self.assertIn("BACKUP_ROOT/slug",self.delete)

if __name__=='__main__':unittest.main()
