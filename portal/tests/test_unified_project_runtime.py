from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import json,unittest

class UnifiedProjectRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
  cls.portal=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.action=Path('components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.project_delete=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
 def test_single_container_apache_php_node_layout(self):
  files=dict(self.mod.runtime_overlay('node24','8.3'))
  compose=files['.cloudif/docker-compose.yml']
  self.assertIn('services:\n  web:',compose)
  self.assertNotIn('\n  php:',compose)
  self.assertIn('site/index.php',files)
  self.assertIn('site/api/server.js',files)
  self.assertIn('ProxyPass /api/',files['.cloudif/apache-vhost.conf'])
  self.assertIn('pdo_pgsql',files['.cloudif/Dockerfile.base'])
  self.assertIn('mysqli',files['.cloudif/Dockerfile.base'])
 def test_shared_base_is_named_by_version_combination(self):
  files=dict(self.mod.runtime_overlay('node20','8.4'))
  runtime=json.loads(files['.cloudif/runtime.json'])
  self.assertEqual(runtime['base_image'],'cloudif/runtime-apache-php8.4-node20:v1')
  self.assertIn('FROM cloudif/runtime-apache-php8.4-node20:v1',files['.cloudif/Dockerfile'])
 def test_user_repository_surface_is_minimal(self):
  files=self.mod.merge_runtime([('README.md','old'),('site/index.html','old'),('.env','CLOUDIF_PUBLIC_NUMBER=1001\nCLOUDIF_DEPLOY_NUMBER=1\n')],'node22','8.3')
  names={x[0] for x in files}
  self.assertTrue(all(name.startswith('site/') or name.startswith('.cloudif/') for name in names))
  for forbidden in ('Dockerfile','Dockerfile.php','docker-compose.yml','server.js','package.json','php/index.php'):
   self.assertNotIn(forbidden,names)
 def test_wizard_only_selects_node_and_php_versions(self):
  self.assertIn('Todo projeto recebe Apache, PHP e Node.js em um container isolado',self.portal)
  self.assertIn('<select name="runtime_template" required>',self.portal)
  self.assertNotIn('value="static-nginx" checked',self.portal)
  self.assertNotIn('value="php-apache"',self.portal)
 def test_new_jobs_are_marked_unified(self):
  self.assertIn('"runtime_layout": "unified-v1"',self.action)
  self.assertIn('{"node20", "node22", "node24"}',self.action)
 def test_komodo_supports_hidden_compose_and_shared_base(self):
  for marker in ('.cloudif/docker-compose.yml','runtime_manifest_invalid','runtime_base_build_failed','shared_base_exists'):
   self.assertIn(marker,self.agent)
 def test_project_delete_remains_layout_independent_and_preserves_tenant(self):
  self.assertIn('/komodo/stack/destroy',self.project_delete)
  self.assertIn("'tenant_preserved'",self.project_delete)
  self.assertNotIn('.cloudif/docker-compose.yml',self.project_delete)

if __name__=='__main__': unittest.main()
