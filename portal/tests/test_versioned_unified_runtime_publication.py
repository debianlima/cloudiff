from pathlib import Path
import unittest

class VersionedUnifiedRuntimePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
        cls.portal=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
        cls.initial=Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text()
    def test_each_deploy_has_unique_runtime_resources(self):
        for marker in (
            "name=f'cloudif-p{public_number}-d{deploy_number}'",
            "image=f'cloudif/publication-p{public_number}-d{deploy_number}:php{php}-node{node}'",
            "container=name+'-web'",
            'create table if not exists publication_runtimes',
        ):
            self.assertIn(marker,self.agent)
    def test_initial_publication_uses_versioned_deploy(self):
        self.assertIn("base + '/komodo/publication/deploy'",self.initial)
        self.assertIn('next_recorded_deploy_number(slug)',self.initial)
        self.assertIn("result['deploy_number'] = deploy_number",self.initial)
        self.assertIn('immutable_conflicts_skipped',self.initial)
        self.assertIn('Publicação inicial em container versionado próprio',self.initial)
        self.assertNotIn('deployment_ready()',self.initial)
    def test_activation_rebuilds_missing_exact_version(self):
        self.assertIn("reason!='target_not_healthy'",self.portal)
        self.assertIn("'commit':commit",self.portal)
        self.assertIn("ku+'/komodo/publication/deploy'",self.portal)
        self.assertIn("'project':slug,'public_number':num,'deploy_number':dep",self.portal)
    def test_runtime_and_compose_are_generated_outside_git(self):
        for marker in ('def _cloudif_v143_base_files','Dockerfile.runtime',"snap/'source'",'infrastructure_in_git'):
            self.assertIn(marker,self.agent)
        self.assertIn('curl -fsS http://127.0.0.1/.cloudif-health',self.agent)

if __name__=='__main__':unittest.main()
