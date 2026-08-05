from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ProvisioningWaitsStartPageThemeTest(unittest.TestCase):
    def test_tenant_health_requires_all_critical_services_and_waits(self):
        source = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif-supabase.sh').read_text()
        for marker in (
            'cloudif_supabase_required_services',
            'db kong studio meta auth rest storage realtime supavisor',
            'cloudif_supabase_wait_until_ready',
            'Timeout aguardando tenant',
            'docker compose --env-file .env ps -q "$SERVICE"',
        ):
            self.assertIn(marker, source)

    def test_project_provisioner_uses_terminal_readiness_not_single_probe(self):
        source = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
        self.assertIn('cloudif_supabase_wait_until_ready', source)
        self.assertIn('CLOUDIF_TENANT_READY_TIMEOUT', source)
        self.assertIn('supabase_tenant_readiness', source)

    def test_worker_timeouts_cover_slow_tenant_and_d1(self):
        source = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
        self.assertIn("CLOUDIF_PROJECT_PROVISION_TIMEOUT', '7200'", source)
        self.assertIn("CLOUDIF_INITIAL_PUBLICATION_TIMEOUT', '9000'", source)

    def test_d1_requires_exact_healthy_runtime_before_promotion(self):
        source = (ROOT / 'components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text()
        for marker in (
            'deploy_initial_runtime',
            "last.get('healthy') is True",
            "str(last.get('container') or '') == expected",
            "str(last.get('stack_id') or '')",
            'promote_initial_runtime',
            'CLOUDIF_D1_PUBLIC_READY_TIMEOUT',
            'Repetindo o deploy após falha transitória do registry.',
        ):
            self.assertIn(marker, source)

    def test_new_project_page_teaches_supported_workflows(self):
        module_path = ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_onboarding_v2.py'
        spec = importlib.util.spec_from_file_location('cloudif_onboarding_v2_test', module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        page = dict(module.build_onboarding_v2('teste', 'iff0001', 'iff0001-teste', 1002))['site/index.html']
        for marker in (
            'Publicar nova versão',
            'Linux',
            'Windows · PowerShell',
            'Electron ou JavaScript',
            'Python · Tkinter',
            'SUA_CHAVE_PUBLICAVEL',
            'git clone https://cloudiff.duckdns.org/git/iff0001/cloudif-teste.git',
            'service_role',
        ):
            self.assertIn(marker, page)
        self.assertNotIn('postgresql://', page)
        self.assertNotIn('site/api/', page)

    def test_portal_header_has_persistent_theme_selector(self):
        shell = (ROOT / 'portal/ui/shell.py').read_text()
        js = (ROOT / 'portal/design/app.js').read_text()
        tokens = (ROOT / 'portal/design/tokens.css').read_text()
        css = (ROOT / 'portal/design/components.css').read_text()
        for marker in ('class="theme-menu"', 'data-theme-choice="light"', 'data-theme-choice="dark"', 'data-theme-choice="system"'):
            self.assertIn(marker, shell)
        self.assertIn('localStorage.setItem("cloudif-theme",value)', js)
        self.assertIn('html[data-theme="dark"]', tokens)
        self.assertIn('.theme-menu .theme-picker', css)
        guide = (ROOT / 'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertIn('Conclusão real do provisionamento', guide)
        self.assertIn('o botão Tema no cabeçalho', guide)


if __name__ == '__main__':
    unittest.main()
