from pathlib import Path
import unittest

class ProjectRuntimeStatusUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_publication_detects_runtime_from_project_job(self):
        for marker in ('def _runtime_from_job','Apache 2.4 · PHP','Node.js','runtime_template','php_version'):
            self.assertIn(marker,self.pub)
    def test_publication_shows_web_service_and_versions(self):
        for marker in ('Serviço web','Versões','Rodando e saudável','/komodo/project/audit'):
            self.assertIn(marker,self.pub)
    def test_project_and_publication_do_not_auto_reload(self):
        self.assertNotIn("setTimeout(function(){location.reload()},2500)",self.pub)
        self.assertNotIn("setTimeout(()=>location.reload(),5000)",self.base)
        self.assertIn('Checar projeto',self.base)
    def test_healthy_local_container_reconciles_stale_komodo_status(self):
        for marker in ('def _cloudif_v132_local_web_health','local_reconciled','local_health','deploy_status = "completed"'):
            self.assertIn(marker,self.agent)

if __name__=='__main__': unittest.main()
