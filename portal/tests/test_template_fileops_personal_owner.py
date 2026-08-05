from pathlib import Path
import unittest
class TemplateFileOpsPersonalOwnerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.template=Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py').read_text()
  cls.agent=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
 def test_template_sends_explicit_owner(self):
  for marker in ("'owner': owner","'repo_owner': owner","'repo_path': f'{owner}/cloudif-{slug}'"):
   self.assertIn(marker,self.template)
 def test_template_urls_use_personal_owner(self):
  self.assertIn("git/{owner}/cloudif-{slug}",self.template)
  self.assertNotIn("git/cloudif/cloudif-{slug}",self.template)
 def test_fileops_requires_owner(self):
  self.assertIn('repo_owner_required',self.agent)
  self.assertIn('payload.get("owner") or payload.get("repo_owner")',self.agent)
  self.assertNotIn('owner = _v118_cfg("FORGEJO_OWNER", "cloudif")\n    repo = _v118_repo_name(slug)\n\n    before =',self.agent)
 def test_webhook_uses_canonical_owner(self):
  self.assertIn('def _v118_trigger_komodo(project_slug, owner, repo',self.agent)
  self.assertIn('f"{owner}/{repo}"',self.agent)
  self.assertIn('git/{owner}/{repo}.git',self.agent)
if __name__=='__main__':unittest.main()
