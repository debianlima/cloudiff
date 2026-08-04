from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class NodePhpMixedRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
 def test_supported_combinations_use_one_container(self):
  for node in ('node20','node22','node24'):
   for php in ('8.2','8.3','8.4'):
    files=dict(self.mod.runtime_overlay(node,php));compose=files['.cloudif/docker-compose.yml']
    self.assertIn(f'php{php}-node{node[4:]}',compose)
    self.assertNotIn('\n  php:',compose)
    self.assertIn(f'FROM php:{php}-apache',files['.cloudif/Dockerfile.base'])
 def test_php_is_interpreted_in_site(self):
  files=dict(self.mod.runtime_overlay('node22','8.3'))
  self.assertIn('site/index.php',files)
  self.assertEqual(files['.cloudif/apache-vhost.conf'].count('DocumentRoot /var/www/html'),1)

if __name__=='__main__':unittest.main()
