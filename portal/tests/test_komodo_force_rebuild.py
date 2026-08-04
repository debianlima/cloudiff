from pathlib import Path
import unittest

class KomodoForceRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_deploy_full_supports_explicit_local_rebuild(self):
        for marker in ('_cloudif_v132_force_local_rebuild','force_rebuild = bool','docker", "compose", "build','--force-recreate','force_rebuild_failed'):
            self.assertIn(marker,self.source)
    def test_rebuild_is_opt_in(self):
        self.assertIn('if force_rebuild:',self.source)
        self.assertIn('no_cache = bool',self.source)

if __name__=='__main__':unittest.main()
