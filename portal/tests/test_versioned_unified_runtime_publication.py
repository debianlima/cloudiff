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

    def test_publication_image_is_materialized_from_exact_versioned_base_before_komodo(self):
        self.assertIn("base_reference=str(base.get('image') or '').strip()",self.agent)
        self.assertIn("frozen_base_id=str(base.get('image_id') or '').strip()",self.agent)
        self.assertIn("docker','image','inspect',base_reference",self.agent)
        self.assertIn('hmac.compare_digest(resolved_base_id,frozen_base_id)',self.agent)
        self.assertIn("dockerfile=f'''FROM {base_reference}",self.agent)
        self.assertIn("'docker','build','--pull=false','--tag',image",self.agent)
        self.assertIn("'run_build':False",self.agent)
        self.assertNotIn("'run_build':True,'auto_pull':False,'file_contents':compose",self.agent)
        latest=self.agent[self.agent.rfind('def cloudif_publication_deploy(handler):'):]
        self.assertNotIn('build:\n      context: .\n      dockerfile: Dockerfile.runtime',latest)
        self.assertIn("'materialization':'local_base_derived'",latest)

    def test_publication_failures_are_short_and_actionable(self):
        self.assertIn("'publication_container_not_healthy'",self.agent)
        self.assertIn("def _publication_error(stage,data):",self.portal)
        self.assertIn("'publication_image_build_failed':'A imagem da publicação não pôde ser criada a partir da base atual.'",self.portal)
        self.assertNotIn("'Falha no deploy versionado: '+json.dumps",self.portal)
        self.assertNotIn("'Falha na publicação HTTPS: '+json.dumps",self.portal)

if __name__=='__main__':unittest.main()
