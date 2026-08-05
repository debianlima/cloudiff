from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import unittest

class UnifiedRuntimeDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        cls.manual=Path('docs/manual-tecnico/11-RUNTIME-UNIFICADO.md').read_text()
        cls.root=Path('README.md').read_text()
        spec=spec_from_file_location('tpl',Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'))
        cls.tpl=module_from_spec(spec);spec.loader.exec_module(cls.tpl)

    def test_help_has_github_access_card(self):
        for marker in ('GitHub e manual técnico','https://github.com/debianlima/cloudiff','Abrir GitHub do projeto','target="_blank"','noopener noreferrer'):
            self.assertIn(marker,self.guide)

    def test_help_explains_unified_runtime(self):
        for marker in ('Ambiente do projeto','Apache, PHP e Node.js','raiz do repositório','gerados fora do Git','portas públicas 80 e 443'):
            self.assertIn(marker,self.guide)

    def test_project_base_readme_explains_editable_and_managed_paths(self):
        text=self.tpl.project_readme('demo','user','tenant-demo',1001,'node22','8.3')
        for marker in ('## Estrutura','raiz deste repositório','`index.php` ou `index.html`','`api/server.js`','gerados pela CloudIFF fora do Git'):
            self.assertIn(marker,text)

    def test_github_manual_documents_runtime_and_diagrams(self):
        for marker in ('# Runtime gerenciado de projetos','código-fonte separado da infraestrutura','imagem-base','```mermaid','cloudif/runtime-apache-php8.3-node22:v2','TLS é terminado no proxy'):
            self.assertIn(marker,self.manual)
        self.assertIn('Runtime unificado de projetos',self.root)

    def test_obsolete_runtime_choices_are_not_in_canonical_help(self):
        self.assertNotIn('Site estático + Nginx',self.guide)
        self.assertNotIn('PHP + Apache</option>',self.guide)

if __name__=='__main__': unittest.main()
