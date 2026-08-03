import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ACTION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
PROVISION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text()
class ProjectProvisioningContractTest(unittest.TestCase):
    def test_check_is_read_only_for_configuration(self):
        self.assertIn('if action == "check":\n        return check_project(form, headers)',ACTION)
        block=ACTION[ACTION.index('def check_project'):ACTION.index('def handle_project_action')]
        self.assertNotIn('queue_provision_job',block)
        self.assertNotIn('tenant=?',block)
    def test_agent_results_are_persisted(self):
        for marker in ('def persist_portal_state(report):','INSERT INTO project_integrations','comp["stack_id"]','persist_portal_state(report)'):
            self.assertIn(marker,PROVISION)
    def test_wizard_contrast_and_job_feedback(self):
        for marker in ('--pm-text:#17201a','color-scheme:light','def _pm197_job_state','data-provision-status','setTimeout(()=>location.reload(),5000)'):
            self.assertIn(marker,PORTAL)
if __name__=='__main__': unittest.main()
