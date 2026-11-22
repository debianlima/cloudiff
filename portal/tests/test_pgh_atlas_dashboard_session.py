from pathlib import Path
import importlib.util,unittest
ROOT=Path(__file__).resolve().parents[2]
HELPER=ROOT/'components/control-plane/usr/local/libexec/cloudif-pgh-dashboard-session.py'
PANEL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
class TestPGHAtlasAdminSession(unittest.TestCase):
 def helper(self):
  spec=importlib.util.spec_from_file_location('pghhelper',HELPER);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 def test_url_parser_modes_are_fail_closed(self):
  m=self.helper();base='https://164-152-61-172.sslip.io'
  cases={'dashboard':'/dashboard/bootstrap','vault':'/vault-admin/bootstrap','openbao':'/openbao/bootstrap'}
  for mode,path in cases.items():
   good=f'open {base}{path}?ticket=opaque now'
   self.assertTrue(m.extract_bootstrap_url(good,base,path).startswith(base+path))
   with self.assertRaises(ValueError):m.extract_bootstrap_url(good,base,'/wrong/bootstrap')
  with self.assertRaises(ValueError):m.extract_bootstrap_url('https://evil.example/dashboard/bootstrap?ticket=x',base,'/dashboard/bootstrap')
 def test_helper_uses_restricted_ssh_contract(self):
  s=HELPER.read_text()
  for x in ('pgh-vault-admin@127.0.0.1','dashboard-session','web-session','openbao-session','IdentitiesOnly=yes','StrictHostKeyChecking=yes','BatchMode=yes'):
   self.assertIn(x,s)
  self.assertNotIn('StrictHostKeyChecking=no',s)
 def test_portal_policies_are_separate_from_pairing(self):
  p=PANEL.read_text();b=BASE.read_text()
  for action in ('pgh.dashboard.session','pgh.vault.session','pgh.openbao.session'):self.assertIn(action,p);self.assertIn(action,b)
  self.assertIn('/action/pgh_admin_session',p);self.assertIn("path.endswith('/action/pgh_admin_session')",b)
  self.assertIn("policy.get('requested_by')!='principal:admin.atlas'",b)
  self.assertIn("run([helper,mode],15)",b)
  self.assertNotIn('/action/pgh_dashboard_session',p)
 def test_pairing_card_remains_passwordless_and_public_key_only(self):
  p=PANEL.read_text()
  self.assertIn('Recuperação PGHD — fluxo sem senha:',p)
  self.assertIn('pgh-atlas-access-admin-v1.pub',p)
  self.assertIn('não forneça senha ao ChatGPT',p)
if __name__=='__main__':unittest.main()
