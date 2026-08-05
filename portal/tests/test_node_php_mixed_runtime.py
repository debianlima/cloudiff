from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class NodePhpMixedRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
 def test_supported_combinations_are_validated_without_git_infra(self):
  for node in ('node20','node22','node24'):
   for php in ('8.2','8.3','8.4'):
    files=dict(self.mod.runtime_overlay(node,php))
    self.assertEqual(set(files),{'api/server.js','api/package.json'})
  self.assertIn("if template not in {'node20','node22','node24'}",self.agent)
  self.assertIn("if php not in {'8.2','8.3','8.4'}",self.agent)
 def test_generated_platform_runtime_serves_root_and_api(self):
  for marker in ('DocumentRoot /var/www/html','ProxyPass /api/','pdo_pgsql','mysqli','COPY --chown=www-data:www-data source/ /var/www/html/'):
   self.assertIn(marker,self.agent)

if __name__=='__main__':unittest.main()
