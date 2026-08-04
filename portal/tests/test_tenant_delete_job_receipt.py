from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest


class TenantDeleteJobReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = spec_from_file_location(
            'tenant_delete',
            Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py'),
        )
        cls.mod = module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_status_falls_back_to_durable_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            old_jobs, old_receipts = self.mod.JOB_ROOT, self.mod.JOB_RECEIPTS
            self.mod.JOB_ROOT = base / '.jobs'
            self.mod.JOB_RECEIPTS = base / '.job-receipts'
            try:
                job_id = 'a' * 32
                payload = {'ok': True, 'job_id': job_id, 'status': 'succeeded', 'progress': 100}
                self.mod._job_write(job_id, payload)
                (self.mod.JOB_ROOT / f'{job_id}.json').unlink()
                self.assertEqual(self.mod.job_status(job_id)['status'], 'succeeded')
                self.assertTrue((self.mod.JOB_RECEIPTS / f'{job_id}.json').is_file())
            finally:
                self.mod.JOB_ROOT, self.mod.JOB_RECEIPTS = old_jobs, old_receipts

    def test_final_verification_counts_local_references(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text()
        self.assertIn('_tenant_reference_count(PORTAL_DB, tenant)', source)
        self.assertIn('_tenant_reference_count(ONBOARDING_DB, tenant)', source)
        self.assertIn('"final_references"', source)


if __name__ == '__main__':
    unittest.main()
