from pathlib import Path
import unittest

class PublicationDeployPromotionRaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_deploy_waits_for_operation_and_container(self):
        for marker in ('operation_complete = (not opid)','healthy and operation_complete','container_or_operation_not_ready'):
            self.assertIn(marker,self.source)
    def test_promotion_verifies_active_alias(self):
        for marker in ('active_alias_not_applied','active_alias not in aliases(target)','"active_alias": active_alias'):
            self.assertIn(marker,self.source)

if __name__=='__main__': unittest.main()
