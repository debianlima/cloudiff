import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ACTION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
PROVISION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
class ProjectProvisioningContractTest(unittest.TestCase):
    def test_check_is_read_only_for_configuration(self):
        self.assertIn('if action == "check":\n        return check_project(form, headers)',ACTION)
        block=ACTION[ACTION.index('def check_project'):ACTION.index('def resume_initial_publication')]
        self.assertNotIn('queue_provision_job',block)
        self.assertNotIn('tenant=?',block)
    def test_sync_and_integrate_do_not_fall_through_to_project_upsert(self):
        self.assertIn('if action in {"sync", "integrate"}:\n        return integration_project_action(form, user)',ACTION)
        block=ACTION[ACTION.index('def integration_project_action'):ACTION.index('def resume_initial_publication')]
        self.assertIn('SELECT slug,tenant,name,description FROM projects WHERE slug=?',block)
        self.assertNotIn('UPDATE projects SET',block)
        self.assertNotIn('ensure_tenant_record',block)
        self.assertIn('sem alterar nome, tenant ou descrição',block)

    def test_agent_results_are_persisted(self):
        for marker in ('def persist_portal_state(report):','INSERT INTO project_integrations','comp["stack_id"]','persist_portal_state(report)'):
            self.assertIn(marker,PROVISION)
    def test_wizard_uses_theme_tokens_and_durable_job_feedback(self):
        for marker in (
            '--pm-text:var(--ink', 'background:var(--surface',
            'def _pm197_job_state', 'cloudif_project_provision_status',
            'data-provision-status', 'data-provision-recoverable',
            'pollProvision', 'Retomar publicação',
        ):
            self.assertIn(marker,PORTAL)
        provisioning=PORTAL[PORTAL.index('# CloudIF definitive project management renderer BEGIN'):PORTAL.index('# CloudIF definitive project management renderer END')]
        self.assertNotIn('setTimeout(()=>location.reload(),5000)',provisioning)
if __name__=='__main__': unittest.main()
