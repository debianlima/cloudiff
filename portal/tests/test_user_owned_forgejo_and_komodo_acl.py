from pathlib import Path
import unittest

class UserOwnedForgejoAndKomodoAclTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.prov=Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
  cls.forja=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.helper=Path('components/runtime/usr/local/sbin/cloudif-komodo-project-authz.py').read_text()
  cls.acl=Path('components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py').read_text()
 def test_provisioner_uses_project_owner_namespace(self):
  for m in ('def _cloudif_project_access','forgejo_owner": owner','owner_user": owner','_v115_repo_path(slug, owner)'):
   self.assertIn(m,self.prov)
 def test_forja_creates_repo_in_existing_user_namespace(self):
  self.assertIn('/admin/users/{urllib.parse.quote(owner)}/repos',self.forja)
  self.assertIn('forgejo_user_not_found',self.forja)
  self.assertIn('forgejo_owner_kind',self.forja)
 def test_komodo_owner_and_acl_permissions(self):
  for m in ("'level':'Write'","'level':'Execute'","specific:['Terminal','Inspect']","(p.stack_ids||[]).map","{type:'Repo'"):
   self.assertIn(m,self.helper)
 def test_acl_changes_trigger_komodo_sync(self):
  self.assertIn('def sync_komodo_acl',self.acl)
  self.assertIn('/komodo/project/authz-sync',self.acl)
 def test_admin_professor_global_sync_remains(self):
  sync=Path('components/runtime/usr/local/sbin/cloudif-komodo-authz-sync.py').read_text()
  self.assertIn("ADMIN_GROUPS={'CloudIF-Tenants-Admin','CloudIF-Professor'}",sync)
  self.assertIn('UserGroup.updateOne',sync)

if __name__=='__main__':unittest.main()
