from pathlib import Path
import ast,unittest
ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
GUIDE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
APPROVAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
TRANSACTION=ROOT/'components/control-plane/current-apps/portal-current/cloudif_transaction_panel.py'
PORTAL_PROXY=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_multiservice_preview_portal.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
GATEWAY_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service'
PORTAL_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-admin-portal.service'
READ={'preview.multiservice.plan','preview.multiservice.status'};WRITE={'approval.request-multiservice-preview','preview.multiservice.create','preview.multiservice.delete'}
class PreviewMCPContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.g=GATEWAY.read_text();cls.r=REGISTRY.read_text();cls.o=ONBOARDING.read_text();cls.guide=GUIDE.read_text()
 def test_tools_and_annotations(self):
  for tool in READ|WRITE:self.assertIn("'name':'"+tool+"'",self.g)
  read=self.g[self.g.index('READ_ONLY_TOOLS='):self.g.index('DESTRUCTIVE_TOOLS=')];destructive=self.g[self.g.index('DESTRUCTIVE_TOOLS='):self.g.index('OPEN_WORLD_PREFIXES=')]
  for tool in READ:self.assertIn("'"+tool+"'",read)
  self.assertIn("'preview.multiservice.create'",destructive);self.assertIn("'preview.multiservice.delete'",destructive);self.assertNotIn("'approval.request-multiservice-preview'",destructive);ast.parse(self.g)
 def test_approval_is_digest_bound_and_transactional(self):
  block=self.g[self.g.index("elif name=='preview.multiservice.create':"):self.g.index("elif name=='preview.multiservice.status':")]
  for marker in ('preview_plan_digest','build_plan_digest','config_digest','archive_sha256','preview_ttl_seconds',"transaction_ids('preview.multiservice'","approval_transition(approval_id,'reserve'","approval_transition(approval_id,'finalize'",'approval_binding_mismatch'):
   self.assertIn(marker,block)
  helper=self.g[self.g.index('def approval_create_multiservice_preview'):self.g.index('def build_broker_call')]
  self.assertIn("'content_stored':False",helper);self.assertIn("'secret_values_in_metadata':False",helper);self.assertNotIn('content_base64',helper)
 def test_scopes_preserve_read_write_separation(self):
  for scope in ('preview:multiservice-plan','approval:request-multiservice-preview','preview:multiservice-execute','preview:multiservice-delete'):
   self.assertIn(scope,self.r);self.assertIn(scope,self.o);self.assertIn(scope,self.g);self.assertIn(scope,self.guide)
  viewer=next(line for line in self.r.splitlines() if line.startswith(" 'viewer':"));developer=next(line for line in self.r.splitlines() if line.startswith(" 'developer':"));self.assertIn('PROJECT_PREVIEW_READ_SCOPES',viewer);self.assertNotIn('PROJECT_PREVIEW_WRITE_SCOPES',viewer);self.assertIn('PROJECT_PREVIEW_WRITE_SCOPES',developer)
 def test_portal_route_is_authenticated_and_drops_credentials(self):
  proxy=PORTAL_PROXY.read_text();coexist=COEXIST.read_text()
  self.assertIn('/cloudiff/portal/preview/',proxy);self.assertIn('X-authentik-username',proxy);self.assertNotIn("'cookie'",proxy[proxy.index('REQUEST_HEADERS='):proxy.index('RESPONSE_HEADERS=')]);self.assertNotIn("'authorization'",proxy[proxy.index('REQUEST_HEADERS='):proxy.index('RESPONSE_HEADERS=')]);self.assertIn("'set-cookie'",proxy[proxy.index('HOP='):proxy.index('def _send')]);self.assertIn('handle_preview_request(self)',coexist)
  self.assertIn('EnvironmentFile=-/etc/cloudif/multiservice-preview.env',PORTAL_UNIT.read_text());self.assertIn('EnvironmentFile=/etc/cloudif/multiservice-preview.env',GATEWAY_UNIT.read_text())
 def test_portal_documents_and_labels(self):
  for tool in READ|WRITE:self.assertIn("'"+tool+"':",self.guide)
  self.assertIn("'documentation_version':'134A'",self.guide);self.assertIn('Criar preview multissserviço',APPROVAL.read_text());self.assertIn('Criar preview multissserviço',TRANSACTION.read_text())
if __name__=='__main__':unittest.main()
