from pathlib import Path
import unittest

class ForjaPersonalOwnerAndKomodoPayloadTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
 def test_personal_namespace_never_falls_back_to_service_user(self):
  fn=self.source[self.source.index('def ensure_forgejo_repo'):self.source.index('RELEASE_RE',self.source.index('def ensure_forgejo_repo'))]
  owner_branch=fn[fn.index('if owner:'):]
  self.assertIn('Falha ao criar repositório no namespace pessoal solicitado.',owner_branch)
  self.assertLess(owner_branch.index('Falha ao criar repositório no namespace pessoal solicitado.'),owner_branch.index('/user/repos'))
 def test_komodo_trigger_has_complete_project_identity(self):
  fn=self.source[self.source.index('def trigger_komodo'):self.source.index('def _cloudif_forgejo_signature_ok')]
  for marker in ('"project": slug','"project_slug": slug','"slug": slug','"owner_user": owner','"access": access','"repo_url_original": repo_url'):
   self.assertIn(marker,fn)

if __name__=='__main__':unittest.main()
