from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
CFG=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_publication_config.py').read_text()
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()

class HomologationEnvironmentPurgeContractTests(unittest.TestCase):
    def test_purge_is_scoped_to_homologation_and_revokes_secrets_before_delete(self):
        block=CFG[CFG.index('def purge_environment_configuration'):CFG.index('def execution_environment_services',CFG.index('def purge_environment_configuration'))]
        self.assertIn("if target!='homologation'",block)
        self.assertLess(block.index("revoke/plan"),block.index("changes=[{'operation':'delete'"))
        self.assertIn('homologation_environment_purge_incomplete',block)
        self.assertIn("'secretValuesIncluded':False",block)

    def test_rejection_purges_config_after_runtime_and_publisher_cleanup(self):
        block=PUB[PUB.rindex('def homologate_candidate('):PUB.index('# CloudIFF v144 END',PUB.rindex('def homologate_candidate('))]
        self.assertLess(block.index("cleanup['runtime']=_remove_compose_runtime"),block.index("purge_environment_configuration(slug,'homologation',actor)"))
        self.assertLess(block.index("stage/delete"),block.index("purge_environment_configuration(slug,'homologation',actor)"))

if __name__=='__main__':unittest.main()
