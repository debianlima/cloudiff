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
 def test_project_rollback_supports_skipping_komodo_after_runtime_destroy(self):
  fn=self.source[self.source.index('def cloudif_v117_project_rollback'):self.source.index('# CloudIF v118',self.source.index('def cloudif_v117_project_rollback'))]
  self.assertIn('skip_komodo =',fn)
  self.assertIn('if skip_komodo:',fn)
  self.assertIn('"skipped": True',fn)
  self.assertIn('komodo_ok = True',fn)

 def test_project_import_bundle_api_is_authenticated_streaming_and_exact_head(self):
  source=self.source
  for marker in (
   '"/project/import-bundle"',
   'def _cloudif_v122_import_bundle(handler):',
   'if not cloudif_auth_ok(handler):',
   "X-CloudIF-Source-Repository",
   "X-CloudIF-Source-Commit",
   "X-CloudIF-Source-SHA256",
   "_cloudif_v122_read_stream(handler,bundle,size,expected_digest)",
   "git','bundle','verify",
   "git','init','--bare'",
   "cwd=verify_repo",
   "target_commit!=source_commit",
   "'idempotent':True",
  ): self.assertIn(marker,source)
  self.assertNotIn("git','push','--force",source)

if __name__=='__main__':unittest.main()
