from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class ProjectRepositoryManualTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
 def test_manual_explains_single_site_and_hidden_platform_folder(self):
  text=self.mod.project_readme('demo','user','tenant-demo',1001,'node22','8.3')
  for marker in ('Todo o código da aplicação fica em `site/`','`site/index.php`','`site/api/server.js`','pasta oculta `.cloudif/`','container final continua exclusivo'):
   self.assertIn(marker,text)
 def test_all_supported_versions_are_documented(self):
  for runtime in ('node20','node22','node24'):
   text=self.mod.project_readme('demo','user','tenant-demo',1001,runtime,'8.4')
   self.assertIn('Apache + PHP 8.4 + Node.js',text)
 def test_template_version_forces_layout_upgrade_for_new_projects(self):
  source=Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py').read_text()
  self.assertIn("old_marker.get('version')==9",source)
  self.assertIn("'version':9",source)

if __name__=='__main__':unittest.main()
