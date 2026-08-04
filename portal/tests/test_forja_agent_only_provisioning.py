from pathlib import Path
import unittest

class ForjaAgentOnlyProvisioningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
 def test_empty_environment_values_are_reloaded_from_files(self):
  self.assertIn("k not in os.environ or not str(os.environ.get(k) or '').strip()",self.source)
 def test_current_forgejo_flow_does_not_fallback_to_direct_token(self):
  final=self.source[self.source.rfind('def forgejo(job, report):'):self.source.index('\ndef komodo(job, report):',self.source.rfind('def forgejo(job, report):'))]
  self.assertNotIn('_original_forgejo_v101(job, report)',final)
  self.assertIn('direct_forgejo_fallback_disabled',final)
  self.assertIn('_v101_forja_project_ensure(job, report)',final)
 def test_clone_url_keeps_personal_owner(self):
  self.assertIn('_v115_repo_clone_url(slug, owner)',self.source)

if __name__=='__main__':unittest.main()
