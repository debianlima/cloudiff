from pathlib import Path
import unittest

class TerminalAndPublicationLayoutTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
  cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
  cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
  cls.coexist=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
 def test_terminal_route_has_friendly_failure(self):
  for marker in ('Terminal indisponível','Não foi possível preparar o terminal','Voltar aos projetos','Tentar novamente'):
   self.assertIn(marker,self.coexist)
  self.assertNotIn("page(user,'projetos',diagnostic)",self.base)
 def test_terminal_uses_unified_compose_and_real_container(self):
  for marker in ("unified_compose=stack_root/'.cloudif'/'docker-compose.yml'",'com.docker.compose.project.config_files','local_discovered','ListServers'):
   self.assertIn(marker,self.agent)
 def test_publication_summary_is_compact_and_runtime_tools_live_in_workspace(self):
  info=self.pub[self.pub.index('def _project_information'):self.pub.index('def _publication_snapshot_from_rows')]
  for marker in ('Configuração do PHP','Runtime do Node.js','Preview do site','Terminal do ambiente','Serviço web','<span>Ambiente</span>','<span>Framework</span>'):
   self.assertNotIn(marker,info)
  self.assertIn('<span>Versões</span>',info)
  for marker in ('data-publication-tool=\"php\"','data-publication-tool=\"node\"','data-publication-tool=\"site\"','data-publication-tool=\"terminal\"'):
   self.assertIn(marker,self.base)
 def test_publication_has_semantic_card_layout(self):
  for marker in ('publication-info-card','publication-info-primary','publication-info-wide'):
   self.assertIn(marker,self.base)

if __name__=='__main__':unittest.main()
