from pathlib import Path
import unittest

class ProvisionWorkerPersistsForgejoOwnerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
 def test_worker_persists_reported_personal_repo(self):
  for marker in ('def persist_forgejo_result','forgejo_repo_url','job[\'repo_url\']=repo_url','persist_forgejo_result(slug,job)'):
   self.assertIn(marker,self.source)
 def test_persistence_happens_before_onboarding(self):
  self.assertLess(self.source.index('persist_forgejo_result(slug,job)'),self.source.index("set_state(path,job,'running','onboarding-reconcile')"))

if __name__=='__main__':unittest.main()
