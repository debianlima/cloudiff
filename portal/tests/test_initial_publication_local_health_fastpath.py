from pathlib import Path
import unittest

class InitialPublicationLocalHealthFastPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text()
    def test_successful_local_health_skips_legacy_polling(self):
        for marker in ("deploy_confirmed=False","local.get('ok') is True","local_reconciled=True","while not deploy_confirmed"):
            self.assertIn(marker,self.source)
    def test_error_keeps_fuller_deploy_detail(self):
        self.assertIn("str(deploy_result)[:700]",self.source)
    def test_fast_path_synthesizes_runtime_state(self):
        self.assertIn("'runtime':{'running':True",self.source)
        self.assertIn("'deploy_status':'completed'",self.source)

if __name__=='__main__':unittest.main()
