from pathlib import Path
import unittest
SCRIPT=Path("components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py")
class InitialPublicationReadinessContractTest(unittest.TestCase):
 def test_requires_healthy_versioned_runtime_and_public_urls(self):
  source=SCRIPT.read_text()
  for marker in ("last.get('healthy') is True","str(last.get('container') or '') == expected","promote_initial_runtime(","wait_public(publisher['version_url'], timeout=public_timeout)","wait_public(publisher['stable_url'], timeout=public_timeout)","public_health_status_"):
   self.assertIn(marker,source)
if __name__=="__main__":unittest.main()
