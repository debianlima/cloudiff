from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import subprocess
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

    def test_bank_deletion_modal_uses_portal_theme_tokens(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text()
        start = source.index('.tenant-delete-tool')
        end = source.index('</style>', start)
        css = source[start:end]
        for marker in (
            'background:var(--surface',
            'background:var(--paper',
            'color:var(--ink',
            'border:1px solid var(--rule',
            'background:var(--iff-wash',
            'background:var(--halt-wash',
        ):
            self.assertIn(marker, css)
        for forbidden in (
            'background:#fff',
            'color:#111',
            'background:#edf6ff',
            'background:#f0fdf4',
            'background:#fef2f2',
        ):
            self.assertNotIn(forbidden, css)

    def test_backup_failure_requires_explicit_second_confirmation_before_runtime_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            old_audit,old_tenants=self.mod.AUDIT_ROOT,self.mod.TENANTS
            self.mod.AUDIT_ROOT=base/'audit';self.mod.TENANTS=base/'tenants';(self.mod.TENANTS/'teste').mkdir(parents=True)
            calls=[]
            old_preview,old_backup,old_run=self.mod.preview,self.mod._backup_database,self.mod._run
            try:
                self.mod.preview=lambda tenant:{'ok':True,'tenant':tenant,'confirmation':'EXCLUIR BANCO '+tenant,'compose_projects':['cloudif-teste'],'resources':{},'linked_projects':[]}
                self.mod._backup_database=lambda tdir,audit:{'ok':False,'error':'database_container_not_found'}
                self.mod._run=lambda *a,**k: calls.append(a[0]) or subprocess.CompletedProcess(a[0],0,'','')
                result=self.mod.execute('teste','EXCLUIR BANCO teste','admin')
                self.assertFalse(result['ok'])
                self.assertEqual(result['error'],'backup_confirmation_required')
                self.assertTrue(result['can_continue_without_backup'])
                self.assertFalse(any(isinstance(c,list) and 'down' in c for c in calls))
            finally:
                self.mod.AUDIT_ROOT,self.mod.TENANTS=old_audit,old_tenants
                self.mod.preview,self.mod._backup_database,self.mod._run=old_preview,old_backup,old_run

    def test_explicit_backup_override_continues_and_is_written_to_audit_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);tdir=base/'tenants'/'teste';tdir.mkdir(parents=True)
            old={name:getattr(self.mod,name) for name in ('AUDIT_ROOT','TENANTS','preview','_backup_database','_run','_remove_labeled_resources','_docker_resources','_remove_registry_row','_delete_tenant_rows','_purge_platform_database_tenant','_remove_proxy_tenant','_tenant_reference_count')}
            self.mod.AUDIT_ROOT=base/'audit';self.mod.TENANTS=base/'tenants'
            preview_calls={'n':0}
            def fake_preview(tenant):
                preview_calls['n']+=1
                if preview_calls['n']==1:return {'ok':True,'tenant':tenant,'confirmation':'EXCLUIR BANCO '+tenant,'compose_projects':[],'resources':{},'linked_projects':[]}
                return {'ok':False,'tenant':tenant,'blockers':['tenant_not_found'],'tenant_dir_present':False,'registry_present':False,'resources':{}}
            try:
                self.mod.preview=fake_preview
                self.mod._backup_database=lambda *a,**k:{'ok':False,'error':'backup_server_unavailable'}
                self.mod._run=lambda cmd,*a,**k: subprocess.CompletedProcess(cmd,0,'','')
                self.mod._remove_labeled_resources=lambda x:{'containers':[],'networks':[],'volumes':[],'errors':[]}
                self.mod._docker_resources=lambda x:{'containers':[],'networks':[],'volumes':[]}
                self.mod._remove_registry_row=lambda *a:[]
                self.mod._delete_tenant_rows=lambda *a:{}
                self.mod._purge_platform_database_tenant=lambda *a:{'ok':True}
                self.mod._remove_proxy_tenant=lambda *a:{'ok':True}
                self.mod._tenant_reference_count=lambda *a:0
                result=self.mod.execute('teste','EXCLUIR BANCO teste','admin',allow_without_backup=True,backup_override_job_id='a'*32)
                self.assertTrue(result['ok'],result)
                self.assertTrue(result['backup_skipped'])
                self.assertEqual(result['backup_override']['confirmed_by'],'admin')
                self.assertEqual(result['backup_override']['source_job_id'],'a'*32)
                receipt=Path(result['audit_dir'])/'backup-override.json'
                self.assertTrue(receipt.is_file())
                self.assertIn('backup_server_unavailable',receipt.read_text())
            finally:
                for name,value in old.items():setattr(self.mod,name,value)

    def test_start_job_rejects_backup_override_without_matching_failed_job(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);old_jobs,old_receipts=self.mod.JOB_ROOT,self.mod.JOB_RECEIPTS
            self.mod.JOB_ROOT=base/'.jobs';self.mod.JOB_RECEIPTS=base/'.receipts'
            try:
                result=self.mod.start_job('teste','EXCLUIR BANCO teste','admin',allow_without_backup=True,backup_override_job_id='b'*32)
                self.assertFalse(result['ok'])
                self.assertEqual(result['error'],'backup_override_not_available')
            finally:self.mod.JOB_ROOT,self.mod.JOB_RECEIPTS=old_jobs,old_receipts

    def test_start_job_accepts_backup_override_only_from_matching_failed_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);old_jobs,old_receipts,old_launch=self.mod.JOB_ROOT,self.mod.JOB_RECEIPTS,self.mod._launch_worker
            self.mod.JOB_ROOT=base/'.jobs';self.mod.JOB_RECEIPTS=base/'.receipts'
            previous_id='c'*32
            previous={
                'ok':True,'job_id':previous_id,'tenant':'teste','actor':'admin','status':'failed',
                'error':'backup_confirmation_required','result':{'error':'backup_confirmation_required','can_continue_without_backup':True},
            }
            try:
                self.mod._job_write(previous_id,previous)
                self.mod._launch_worker=lambda job_id:'unit-'+job_id[:8]
                result=self.mod.start_job('teste','EXCLUIR BANCO teste','admin',allow_without_backup=True,backup_override_job_id=previous_id)
                self.assertTrue(result['ok'],result)
                self.assertTrue(result['allow_without_backup'])
                self.assertEqual(result['backup_override_job_id'],previous_id)
                stored=self.mod.job_status(result['job_id'])
                self.assertEqual(stored['backup_override_job_id'],previous_id)
            finally:
                (self.mod.JOB_ROOT/'.teste.lock').unlink(missing_ok=True)
                self.mod.JOB_ROOT,self.mod.JOB_RECEIPTS,self.mod._launch_worker=old_jobs,old_receipts,old_launch

    def test_ui_offers_continue_without_backup_only_after_recorded_backup_failure(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text()
        for marker in ('backup_confirmation_required','Continuar sem backup','data-backup-continue','backup_override_job_id','allow_without_backup'):
            self.assertIn(marker,source)
        route=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertIn('allow_without_backup=value("allow_without_backup") == "1"',route)
        self.assertIn('backup_override_job_id=value("backup_override_job_id")',route)

    def test_final_verification_counts_local_references(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py').read_text()
        self.assertIn('_tenant_reference_count(PORTAL_DB, tenant)', source)
        self.assertIn('_tenant_reference_count(ONBOARDING_DB, tenant)', source)
        self.assertIn('"final_references"', source)


if __name__ == '__main__':
    unittest.main()
