from pathlib import Path
import importlib.util
import os
import stat
import tempfile
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
    def test_testar_e_salvar_observes_atomic_config_effect(self):
        module_path = Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py')
        spec = importlib.util.spec_from_file_location('cloudif_portal_v2_coexist_action_map_test', module_path)
        module = importlib.util.module_from_spec(spec)
        previous = os.environ.pop('CLOUDIF_PORTAL_V2', None)
        try:
            spec.loader.exec_module(module)
        finally:
            if previous is not None:
                os.environ['CLOUDIF_PORTAL_V2'] = previous
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'project-backup-remote.env'
            target.write_text('OLD=1\n', encoding='utf-8')
            target.chmod(0o644)
            before = target.read_bytes()
            payload = (
                'REMOTE_ENABLED=1\nREMOTE_READY=1\nREMOTE_HOST=backup.invalid\n'
                'REMOTE_PORT=2222\nREMOTE_USER=cloudifbackup\nREMOTE_PATH=.\n'
                'REMOTE_KEY=/etc/cloudif/backup_ed25519\n'
            )
            module._write_backup_remote_env(target, payload)
            after = target.read_bytes()
            self.assertNotEqual(before, after)
            self.assertEqual(after, payload.encode('utf-8'))
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(list(target.parent.glob(target.name + '.tmp.*')), [])
        self.assertIn('_write_backup_remote_env(BACKUP_REMOTE_ENV, env_text)', self.portal)
        self.assertNotIn("target=Path('/etc/cloudif/project-backup-remote.env')", self.portal)

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
