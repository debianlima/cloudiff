from pathlib import Path
import unittest
SCRIPT=Path("components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py")
class InitialPublicationReadinessContractTest(unittest.TestCase):
 def test_requires_healthy_versioned_runtime_and_public_urls(self):
  source=SCRIPT.read_text()
  for marker in ("not deployment.get('ok')","not promotion.get('ok')","wait_public(publisher['version_url'])","wait_public(publisher['stable_url'])","public_health_status_"):
   self.assertIn(marker,source)
if __name__=="__main__":unittest.main()
