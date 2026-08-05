from pathlib import Path
import unittest

class InitialPublicationVersionedRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.source=Path("components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py").read_text()
 def test_initial_publication_calls_versioned_deploy(self):
  for marker in ("/komodo/publication/deploy","'deploy_number': 1","timeout=900","versioned_d1_deploy_failed"):
   self.assertIn(marker,self.source)
 def test_health_is_checked_after_promotion(self):
  self.assertIn("wait_public(publisher['version_url'])",self.source)
  self.assertIn("wait_public(publisher['stable_url'])",self.source)
 def test_full_deploy_error_is_preserved(self):
  self.assertIn("json.dumps(deployment, ensure_ascii=False)[:900]",self.source)
if __name__=="__main__":unittest.main()
