import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PANEL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
LEGACY_PANEL_PATH=ROOT/'portal/legacy/cloudif_approval_panel.py'
COMPONENTS=ROOT/'portal/design/components.css'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

PANEL=load('approval_history_dialog_panel',PANEL_PATH)
LEGACY_PANEL=load('approval_history_dialog_legacy_panel',LEGACY_PANEL_PATH)


def row(aid,status):
    return {
        'approval_id':aid,'project_slug':'teste-sofa','action':'deployment.production.activate',
        'action_label':'Pré-ativação de produção real','status':status,'reason':'QA','created_at':1,'expires_at':9999999999,
        'requested_by':'portal:owner','requester_role':'owner','approved_by':None,'approver_role':None,
        'second_approved_by':None,'second_approver_role':None,'two_approvers_required':1,
        'authorization_mode':'dual_admin_or_professor','metadata':{},'rejected_by':None,'cancelled_by':None,
    }


class ApprovalHistoryDialogThemeTests(unittest.TestCase):
    def test_context_active_link_uses_canonical_theme_tokens(self):
        css=COMPONENTS.read_text()
        self.assertIn('.project-context-group a[aria-current="page"]{background:var(--accent-soft);color:var(--accent);font-weight:750}',css)
        self.assertIn('.tab-aprovacoes .project-context-group a[aria-current="page"]{background:var(--iff-wash);color:var(--iff-dark);font-weight:750}',css)
        self.assertIn('.approval-history-dialog::backdrop{background:var(--overlay)}',css)
        self.assertIn('background:var(--surface);color:var(--ink)',css)

    def test_history_is_hidden_in_native_dialog_until_requested(self):
        for panel in (PANEL,LEGACY_PANEL):
            html=panel.render([row('apr_pending','pending'),row('apr_old','expired')],'csrf',False,[],actor_username='owner')
            self.assertIn('apr_pending',html)
            self.assertIn('Carregar histórico (1)',html)
            self.assertIn('<dialog id="approval-history-dialog"',html)
            self.assertIn('apr_old',html)
            self.assertGreater(html.index('apr_old'),html.index('<dialog id="approval-history-dialog"'))
            self.assertIn('document.getElementById(\'approval-history-dialog\').showModal()',html)

    def test_history_only_page_keeps_policies_adjacent_to_compact_approval_summary(self):
        policy={'policy_id':'pol_1','project_slug':'teste-sofa','action':'forgejo.proposal.merge','action_label':'Mesclar pull request','requested_by':'agent','created_by':'admin','creator_role':'admin','created_at':1,'active':True}
        html=PANEL.render([row('apr_old_a','expired'),row('apr_old_b','consumed')],'csrf',False,[policy],actor_username='owner')
        self.assertIn('Nenhuma aprovação pendente ou aguardando consumo.',html)
        self.assertIn('Carregar histórico (2)',html)
        self.assertIn('id="persistent-approval-policies"',html)
        # The historical articles live in a modal, not in the main approval list before the trigger.
        main=html[:html.index('<dialog id="approval-history-dialog"')]
        self.assertNotIn('apr_old_a',main)
        self.assertNotIn('apr_old_b',main)


if __name__=='__main__':unittest.main()
