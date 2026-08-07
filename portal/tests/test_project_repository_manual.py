from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest
class ProjectRepositoryManualTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location("tpl",Path("components/control-plane/usr/local/sbin/cloudif-project-template-apply.py"));cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
 def test_manual_explains_root_source_and_external_infrastructure(self):
  text=self.mod.project_readme("demo","user","tenant-demo",1001,"node22","8.3")
  for marker in ("A raiz deste repositório é a raiz da aplicação","`index.php` ou `index.html`","`api/server.js`","gerados pela CloudIFF fora do Git","Cada publicação recebe stack, imagem, container, URL e terminais próprios"):
   self.assertIn(marker,text)
  self.assertNotIn("Todo o código da aplicação fica em `site/`",text)
 def test_all_supported_versions_are_documented(self):
  for runtime in ("node20","node22","node24"):
   text=self.mod.project_readme("demo","user","tenant-demo",1001,runtime,"8.4");self.assertIn("Apache + PHP 8.4 + Node.js",text)
 def test_template_version_forces_layout_upgrade_for_new_projects(self):
  source=Path("components/control-plane/usr/local/sbin/cloudif-project-template-apply.py").read_text();self.assertIn("old.get('version') == 12",source);self.assertIn("'version': 12",source)
if __name__=="__main__":unittest.main()
