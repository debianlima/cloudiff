from pathlib import Path
import importlib.util,unittest
ROOT=Path(__file__).resolve().parents[2]
HELPER=ROOT/'components/control-plane/usr/local/libexec/cloudif-pgh-dashboard-session.py'
PANEL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
class TestPGHAtlasDashboardSession(unittest.TestCase):
 def test_url_parser_is_fail_closed(self):
  spec=importlib.util.spec_from_file_location('pghhelper',HELPER);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  base='https://164-152-61-172.sslip.io'
  good='open https://164-152-61-172.sslip.io/dashboard/bootstrap?ticket=opaque now'
  self.assertTrue(m.extract_bootstrap_url(good,base).startswith(base+'/dashboard/bootstrap'))
  for bad in ['https://evil.example/dashboard/bootstrap?ticket=x','http://164-152-61-172.sslip.io/dashboard/bootstrap?ticket=x','https://164-152-61-172.sslip.io/vault-admin/bootstrap?ticket=x']:
   with self.assertRaises(ValueError):m.extract_bootstrap_url(bad,base)
 def test_helper_uses_restricted_ssh_contract(self):
  s=HELPER.read_text()
  for x in ('pgh-vault-admin@127.0.0.1','dashboard-session','IdentitiesOnly=yes','StrictHostKeyChecking=yes','BatchMode=yes','/dashboard/bootstrap'):
   self.assertIn(x,s)
  self.assertNotIn('StrictHostKeyChecking=no',s)
 def test_portal_has_same_origin_admin_session_action(self):
  p=PANEL.read_text(); b=BASE.read_text()
  self.assertIn('/action/pgh_dashboard_session',p)
  self.assertIn("path.endswith('/action/pgh_dashboard_session')",b)
  self.assertIn('PGH_DASHBOARD_SESSION_HELPER',b)
  self.assertIn('approval_policy',b)
if __name__=='__main__':unittest.main()
