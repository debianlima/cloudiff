from pathlib import Path
import importlib.util,unittest
ROOT=Path(__file__).resolve().parents[2]
HELPER=ROOT/'components/control-plane/usr/local/libexec/cloudif-pgh-pair-approve.py'
PANEL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
LEGACY_PANEL=ROOT/'portal/legacy/cloudif_approval_panel.py'
LEGACY_BASE=ROOT/'portal/legacy/cloudif-admin-portal-base.py'
class TestPGHAtlasPairingRecovery(unittest.TestCase):
 def test_helper_is_pairing_only(self):
  s=HELPER.read_text()
  for x in ('pgh-atlas-pairing-recovery-v1','pair-approve','pghd_server_vps','principal:mobile.pghd_server_vps','access_manage=no','IdentitiesOnly=yes','StrictHostKeyChecking=yes','BatchMode=yes'):self.assertIn(x,s)
  self.assertNotIn('dashboard-session',s);self.assertNotIn('access.manage',s);self.assertNotIn('StrictHostKeyChecking=no',s)
 def test_helper_rejects_bad_code_before_ssh(self):
  spec=importlib.util.spec_from_file_location('pairhelper',HELPER);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertEqual(m.main(['helper','BAD']),13)
 def test_panel_uses_separate_pairing_identity_and_form(self):
  for p in (PANEL,LEGACY_PANEL):
   s=p.read_text();self.assertIn('pgh-atlas-pairing-recovery-v1.pub',s);self.assertIn('/action/pgh_pair_approve',s);self.assertIn('Aprovar pareamento pelo Atlas',s);self.assertIn('principal:mobile.pghd_server_vps',s)
 def test_portal_checks_authoritative_policy_and_fixed_requester(self):
  for p in (BASE,LEGACY_BASE):
   s=p.read_text();start=s.index("if path.endswith('/action/pgh_pair_approve'):");end=s.index("if path.endswith('/action/pgh_admin_session'):",start);b=s[start:end]
   self.assertIn("'/v1/approval-policies?status=active'",b)
   self.assertIn("policy.get('action')!='pgh.device.pair'",b)
   self.assertIn("policy.get('requested_by')!='principal:mobile.pghd_server_vps'",b)
   self.assertIn("run([helper,pair_code],15)",b)
   self.assertIn("log_action(user['username'],'pgh_pair_approve',policy_id",b)
   self.assertNotIn("log_action(user['username'],'pgh_pair_approve',pair_code",b)
   self.assertIn("CloudIF-Tenants-Admin",b)
 def test_admin_session_remains_separate(self):
  s=BASE.read_text();self.assertIn("path.endswith('/action/pgh_admin_session')",s);self.assertIn("requested_by')!='principal:admin.atlas'",s)
if __name__=='__main__':unittest.main()
