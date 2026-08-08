from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
CURRENT=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
LEGACY=(ROOT/'portal/legacy/cloudif-admin-portal-base.py').read_text()
RULE="automatic_active = (not always_alive) and (policy_hours == 0 or not deadline_active)"

class DatabaseActiveModeFallbackTests(unittest.TestCase):
    def test_expired_timed_policy_falls_back_to_automatic(self):
        def active(always_alive,policy_hours,deadline_active):
            automatic=(not always_alive) and (policy_hours==0 or not deadline_active)
            timed=deadline_active and not automatic
            return always_alive,timed,automatic
        self.assertEqual(active(False,6,False),(False,False,True))
        self.assertEqual(active(False,6,True),(False,True,False))
        self.assertEqual(active(False,0,True),(False,False,True))
        self.assertEqual(active(True,24,False),(True,False,False))
    def test_both_portal_sources_use_the_same_fallback_rule(self):
        self.assertGreaterEqual(CURRENT.count(RULE),2)
        self.assertGreaterEqual(LEGACY.count(RULE),2)
        self.assertNotIn("automatic_active = (not always_alive) and policy_hours == 0",CURRENT)
        self.assertNotIn("automatic_active = (not always_alive) and policy_hours == 0",LEGACY)

if __name__=='__main__':unittest.main()
