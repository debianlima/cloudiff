import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PANEL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
GUIDE_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

PANEL=load('approval_panel_actor_consistency',PANEL_PATH)
GUIDE=load('ai_guide_actor_consistency',GUIDE_PATH)

class ApprovalPanelActorConsistencyTests(unittest.TestCase):
    def approval(self,status='pending_second',approved_by='admin-a',requested_by='portal:owner'):
        return {
            'approval_id':'apr_test','project_slug':'teste-sofa','action':'deployment.production.activate',
            'action_label':'Pré-ativação de produção real','status':status,'reason':'QA','created_at':1,'expires_at':9999999999,
            'requested_by':requested_by,'requester_role':'owner','approved_by':approved_by,'second_approved_by':None,
            'two_approvers_required':1,'authorization_mode':'dual_admin_or_professor','metadata':{},
        }

    def project(self):
        return {'project_slug':'teste-sofa','client_id':'client-x','role_profile':'developer','environment':'project','scopes':['project:read'],'instructions':{'mcp_endpoint':'https://example.invalid/mcp'}}

    def test_first_approver_sees_wait_message_not_second_action(self):
        row=self.approval()
        html=PANEL.render([row],'csrf',True,[],actor_username='admin-a')
        self.assertIn('Primeira aprovação registrada por você',html)
        self.assertNotIn('>Aprovar</button>',html)
        self.assertNotIn('>Rejeitar</button>',html)
        hub=GUIDE.render([self.project()],'csrf',[row],True,actor_username='admin-a')
        self.assertIn('Primeira aprovação registrada por você',hub)
        self.assertNotIn('>Aceitar</button>',hub)
        self.assertNotIn('>Rejeitar</button>',hub)

    def test_distinct_second_approver_gets_only_supported_second_action(self):
        row=self.approval()
        html=PANEL.render([row],'csrf',True,[],actor_username='admin-b')
        self.assertIn('>Aprovar</button>',html)
        self.assertNotIn('>Rejeitar</button>',html)
        hub=GUIDE.render([self.project()],'csrf',[row],True,actor_username='admin-b')
        self.assertIn('>Aceitar</button>',hub)
        self.assertNotIn('>Rejeitar</button>',hub)

    def test_requester_cannot_be_offered_first_dual_approval(self):
        row=self.approval(status='pending',approved_by=None,requested_by='portal:owner')
        html=PANEL.render([row],'csrf',True,[],actor_username='owner')
        self.assertIn('Você solicitou esta ativação',html)
        self.assertNotIn('>Aprovar</button>',html)
        hub=GUIDE.render([self.project()],'csrf',[row],True,actor_username='owner')
        self.assertIn('Você solicitou esta ativação',hub)
        self.assertNotIn('>Aceitar</button>',hub)

    def test_stale_double_submit_has_specific_conflict_copy(self):
        self.assertIn("err=='distinct_second_approver_required'",PORTAL)
        self.assertIn('A primeira aprovação já foi registrada por este usuário.',PORTAL)
        self.assertIn('<h1>Decisão não registrada</h1>',PORTAL)

if __name__=='__main__':unittest.main()
