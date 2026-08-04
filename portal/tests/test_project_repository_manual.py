from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class ProjectRepositoryManualTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
  cls.mod=module_from_spec(spec);spec.loader.exec_module(cls.mod)
 def test_node_php_manual_explains_editable_and_managed_files(self):
  text=self.mod.project_readme('demo','user','tenant-demo',1001,'node22','8.3')
  for marker in ('`site/`','`php/`','`server.js`','`package.json`','`Dockerfile`','`Dockerfile.php`','`docker-compose.yml`','`.env`','Pode alterar?'):
   self.assertIn(marker,text)
 def test_manual_states_deployment_contract(self):
  text=self.mod.project_readme('demo','user','tenant-demo',1001,'node22','8.3')
  for marker in ('branch de implantação é `main`','serviço público do Compose se chama `web`','porta `80`','`GET /health`','rede externa `cloudif-publications`','segredos não são enviados ao Git'):
   self.assertIn(marker,text)
 def test_all_runtime_manuals_are_supported(self):
  for runtime in ('static-nginx','node20','node22','node24','php-apache'):
   text=self.mod.project_readme('demo','user','tenant-demo',1001,runtime,'8.4')
   self.assertIn('## Comece por aqui',text)
   self.assertIn('## O que acontece após um push',text)
   self.assertIn('## Antes de alterar arquivos de infraestrutura',text)
 def test_template_version_forces_readme_upgrade(self):
  source=Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py').read_text()
  self.assertIn("old_marker.get('version')==8",source)
  self.assertIn("'version':8",source)
  self.assertIn("[('README.md',project_readme",source)

if __name__=='__main__':unittest.main()
