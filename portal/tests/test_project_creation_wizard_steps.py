import os
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CANDIDATES=[
    os.environ.get('CLOUDIF_TEST_PORTAL_SOURCE'),
    ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py',
    '/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py',
]
SOURCE=next(Path(p) for p in CANDIDATES if p and Path(p).exists()).read_text()

class ProjectCreationWizardStepsTest(unittest.TestCase):
    def test_true_four_step_navigation(self):
        for marker in (
            'data-pm-step="0"',
            'data-pm-step="1"',
            'data-pm-step="2"',
            'data-pm-step="3"',
            'data-pm-nav="previous"',
            'data-pm-nav="next"',
            'data-pm-nav="submit"',
            'pm-new-progress',
        ):
            self.assertIn(marker,SOURCE)

    def test_custom_tenant_name_uses_existing_contract(self):
        for marker in (
            'name="tenant_suffix"',
            'name="tenant" value=""',
            'name="tenant_existing"',
            'data-pm-tenant-preview',
            "tenant=username+'-'+base",
            'if(!base)base=stamp()',
        ):
            self.assertIn(marker,SOURCE)

    def test_green_accent_and_persistent_summary(self):
        self.assertIn('--pm-accent:#157a2b',SOURCE)
        self.assertIn('--pm-accent-soft:#edf7ef',SOURCE)
        self.assertIn('aria-label="Resumo do provisionamento"',SOURCE)
        self.assertIn('data-pm-summary="name"',SOURCE)
        self.assertIn('data-pm-summary="db"',SOURCE)
        self.assertIn('data-pm-summary="runtime"',SOURCE)

if __name__=='__main__':
    unittest.main()
