from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ProvisioningPolicyReadmeDarkThemeTest(unittest.TestCase):
    def test_new_tenant_policy_is_persisted_and_verified(self):
        script = ROOT / 'components/control-plane/usr/local/sbin/cloudif-tenant-policy-ensure.py'
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'portal.db'
            sqlite3.connect(db).close()
            run = subprocess.run(
                [str(script), '--tenant', 'iff0001-teste', '--hours', '6', '--portal-db', str(db)],
                check=True,
                text=True,
                capture_output=True,
            )
            data = json.loads(run.stdout)
            self.assertTrue(data['ok'])
            self.assertTrue(data['verified'])
            self.assertEqual(data['hours'], 6)
            con = sqlite3.connect(db)
            row = con.execute(
                'select always_alive,max_hours,keepalive_until from tenant_policy where tenant=?',
                ('iff0001-teste',),
            ).fetchone()
            con.close()
            self.assertEqual(row[0], 0)
            self.assertEqual(row[1], 6)
            self.assertTrue(row[2])

    def test_project_job_carries_selected_availability_period(self):
        action = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
        portal = (ROOT / 'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        for marker in (
            'tenant_keepalive_hours = int',
            '"tenant_keepalive_hours": tenant_keepalive_hours',
            'Tempo inicial ligado',
            'name="tenant_keepalive_hours"',
            '6 horas — padrão',
        ):
            self.assertIn(marker, action + portal)

    def test_worker_requires_tenant_policy_and_validated_backup_policy(self):
        source = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
        for marker in (
            "'tenant-availability-policy'",
            'cloudif-tenant-policy-ensure.py',
            'backup_configuration_not_persisted',
            "require_timer('cloudif-project-backup-auto.timer')",
            "require_timer('cloudif-tenant-db-backup-v2.timer')",
            "'list', '--slug', slug",
            'backup_policy_not_verified',
        ):
            self.assertIn(marker, source)

    def test_certificate_requires_publisher_tls_and_public_route(self):
        script = (ROOT / 'components/control-plane/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh').read_text()
        provisioner = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
        for marker in (
            'publisher_rejected_tenant',
            'CLOUDIF_TENANT_CERTIFICATE_WAIT_SECONDS:-900',
            'tls_verified',
            'route_verified',
            'CLOUDIF_TENANT_CERTIFICATE_TIMEOUT',
            'certificate_verified',
        ):
            self.assertIn(marker, script + provisioner)

    def test_readme_mirrors_initial_page_with_personalized_safe_examples(self):
        module_path = ROOT / 'components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'
        spec = importlib.util.spec_from_file_location('cloudif_template_apply_test', module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        readme = module.project_readme(
            'laboratorio-de-hardware',
            'iff1742962',
            'iff1742962-laboratoriodehardware',
            1001,
            'node24',
            '8.4',
            project_name='Laboratório de Hardware',
            description='Laboratório de Hardware.',
            owner_email='iff1742962@laboratorios.bomjesus.iff.edu.br',
        )
        for marker in (
            '# Laboratório de Hardware',
            'https://1001.cloudiff.duckdns.org/',
            'https://1001-d1.cloudiff.duckdns.org/',
            'git clone https://cloudiff.duckdns.org/git/iff1742962/cloudif-laboratorio-de-hardware.git',
            'iff1742962-laboratoriodehardware.cloudiff.duckdns.org',
            'SUA_CHAVE_PUBLICAVEL',
            'Windows PowerShell',
            'Python desktop',
            '--readme-only',
        ):
            self.assertIn(marker, readme + module_path.read_text())
        self.assertNotIn('postgresql://', readme)
        self.assertNotIn('service_role=', readme)
        self.assertNotIn('PRIVATE KEY', readme)

    def test_dark_theme_covers_all_legacy_operational_modules(self):
        css = (ROOT / 'portal/design/components.css').read_text()
        for selector in (
            '.db96-card',
            '.backup-console-card',
            '.agent-hero',
            '.admin-operation-center',
            '.global-admin-hero',
            '.backup-remote-config-form',
            '.pm-new-shell',
        ):
            self.assertIn('html[data-theme="dark"] body .legacy-content ' + selector, css)
        self.assertIn('background:var(--surface)!important', css)
        self.assertIn('background:var(--paper)!important', css)


if __name__ == '__main__':
    unittest.main()
