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
    def test_modal_establishes_and_restores_keyboard_focus(self):
        for marker in (
            'aria-describedby="project-delete-subtitle" tabindex="-1"',
            "dialog=modal.querySelector('.project-delete-dialog')",
            'opener=document.activeElement',
            'setTimeout(()=>dialog.focus(),0)',
            'if(target&&document.contains(target))target.focus()',
            "if(e.key==='Escape')closeModal()",
        ):
            self.assertIn(marker,self.source)

    def test_modal_cannot_close_while_request_or_job_runs(self):
        self.assertIn('function setClosable(value)',self.source)
        self.assertIn('setClosable(false);modal.hidden=false',self.source)
        self.assertIn('if(!terminal)return',self.source)
        self.assertIn('terminal=!activeJob;setClosable(terminal)',self.source)
        self.assertIn("x.disabled=!value;x.setAttribute('aria-disabled',String(!value))",self.source)
        self.assertIn('Exclusão em andamento…',self.source)
        self.assertNotIn('if(activeJob&&!terminal)return',self.source)
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

    def test_modal_translates_confirmation_and_wizard_errors(self):
        self.assertIn("invalid_confirmation:'A confirmação não confere.", self.source)
        self.assertIn("wizard_required:'A prévia de exclusão expirou.", self.source)
        self.assertIn("errorText(job.error||job.detail||payload.error", self.source)

    def test_confirmation_is_validated_live_before_destructive_submit(self):
        for marker in (
            'data-delete-confirmation="EXCLUIR {h(selected)}"',
            'data-project-delete-confirm',
            'data-project-delete-confirm-status',
            'normalizeConfirmation',
            "normalize('NFKC')",
            'syncConfirmation()',
            'button.disabled=!ok',
            'Confirmação reconhecida.',
            'Digite exatamente ',
        ):
            self.assertIn(marker,self.source)

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
