from pathlib import Path
import unittest

class ProjectDeleteTrackingModalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
    def test_tracking_is_a_fixed_modal(self):
        for marker in ('project-delete-modal','project-delete-dialog','position:fixed;inset:0;z-index:10000','aria-modal="true"'):
            self.assertIn(marker,self.source)
    def test_all_project_deletion_steps_are_visible(self):
        for marker in ('Validação','Publicação e aliases','Stack e runtime','Forgejo e agentes','Registros do Portal','Identidade e onboarding','Reconciliação'):
            self.assertIn(marker,self.source)
    def test_modal_reconnects_and_preserves_progress(self):
        for marker in ('Reconectando ao processo','Tentativa ${{attempt+1}} de 75','showReconnect','admin-delete-project-status','Cache-Control'):
            self.assertIn(marker,self.source)
    def test_modal_cannot_close_while_job_runs(self):
        self.assertIn('if(activeJob&&!terminal)return',self.source)
        self.assertIn('Exclusão em andamento…',self.source)
    def test_modal_uses_portal_theme_tokens(self):
        for marker in (
            'background:var(--surface',
            'background:var(--paper',
            'color:var(--ink',
            'border:1px solid var(--rule',
            'background:var(--iff-wash',
            'background:var(--halt-wash',
        ):
            self.assertIn(marker, self.source)
        modal_css = self.source[self.source.index('body.project-delete-modal-open'):self.source.index('</style>', self.source.index('body.project-delete-modal-open'))]
        self.assertNotIn('background:#fff', modal_css)
        self.assertNotIn('color:#111', modal_css)

    def test_modal_never_polls_an_undefined_job(self):
        for marker in (
            "form.dataset.deleteSubmitting==='1'",
            "const job=payload&&payload.result",
            "const jobId=String(job.job_id||payload.job_id||'').trim()",
            "if(!jobId||jobId==='undefined')",
            "poll(jobId)",
            "if(!id||id==='undefined')",
        ):
            self.assertIn(marker,self.source)
        self.assertNotIn('poll(job.job_id)',self.source)

    def test_protected_delete_contract_remains(self):
        for marker in ('wizard_token','consume_wizard_token','EXCLUIR {h(selected)}','admin-delete-form'):
            self.assertIn(marker,self.source)
    def test_inline_progress_box_was_removed(self):
        self.assertNotIn('id="admin-delete-progress"',self.source)

if __name__=='__main__':unittest.main()
