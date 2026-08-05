from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class UnifiedProjectRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
  cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.action=Path('components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.project_delete=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
 def test_runtime_overlay_is_source_only(self):
  files=dict(self.mod.runtime_overlay('node24','8.3'))
  self.assertEqual(set(files),{'api/server.js','api/package.json'})
  self.assertNotIn('.cloudif/docker-compose.yml',files)
  self.assertNotIn('Dockerfile',files)
 def test_runtime_is_managed_outside_git(self):
  for marker in ('def _cloudif_v143_base_files','runtime-bases','cloudif/runtime-apache-php{php}-node{node}:v2','infrastructure_in_git'):
   self.assertIn(marker,self.agent)
  self.assertIn("snap/'source'",self.agent)
  self.assertIn("stack_dir/'source'",self.agent)
 def test_user_repository_root_replaces_site_folder(self):
  files=self.mod.merge_runtime([('README.md','old'),('site/index.html','old'),('site/css/app.css','css'),('.env','secret')],'node22','8.3')
  names={x[0] for x in files}
  self.assertIn('index.html',names);self.assertIn('css/app.css',names)
  self.assertFalse(any(name.startswith('site/') or name.startswith('.cloudif/') for name in names))
  for forbidden in ('Dockerfile','docker-compose.yml','.env','nginx.conf'):
   self.assertNotIn(forbidden,names)
 def test_wizard_only_selects_node_and_php_versions(self):
  self.assertIn('Todo projeto recebe Apache, PHP e Node.js em um container isolado',self.portal)
  self.assertIn('<select name="runtime_template" required>',self.portal)
  self.assertNotIn('value="static-nginx" checked',self.portal)
 def test_new_jobs_are_marked_managed_root(self):
  self.assertIn('"runtime_layout": "managed-root-v1"',self.action)
  self.assertIn('{"node20", "node22", "node24"}',self.action)
 def test_project_delete_remains_layout_independent_and_preserves_tenant(self):
  self.assertIn('/komodo/stack/destroy',self.project_delete)
  self.assertIn("'tenant_preserved'",self.project_delete)

if __name__=='__main__':unittest.main()
