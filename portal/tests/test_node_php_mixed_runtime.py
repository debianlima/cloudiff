from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class NodePhpMixedRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location("tpl",Path("components/control-plane/usr/local/sbin/cloudif-project-template-apply.py"));cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
  cls.portal=Path("components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py").read_text()
  cls.action=Path("components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py").read_text()
 def test_all_node_versions_include_php_sidecar(self):
  for node in ("node20","node22","node24"):
   for php in ("8.2","8.3","8.4"):
    files=dict(self.mod.runtime_overlay(node,php))
    self.assertIn(f"FROM php:{php}-apache",files["Dockerfile.php"])
    self.assertIn("php:",files["docker-compose.yml"])
    self.assertIn("/php",files["server.js"])
 def test_php_version_is_independent_and_defaults_to_83(self):
  self.assertIn('name="php_version"',self.portal)
  self.assertIn('value="8.3" selected',self.portal)
  self.assertIn('"php_version": php_version',self.action)
 def test_php_only_runtime_accepts_selected_version(self):
  files=dict(self.mod.runtime_overlay("php-apache","8.4"))
  self.assertIn("FROM php:8.4-apache",files["Dockerfile"])

if __name__=="__main__":unittest.main()
