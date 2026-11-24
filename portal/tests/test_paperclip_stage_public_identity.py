from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
BROKER=(ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py').read_text()
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()

class PaperclipStagePublicIdentityTests(unittest.TestCase):
    def test_homologation_plan_binds_public_stage_identity(self):
        block=PUB[PUB.index('def _create_preview_runtime_homologation_candidate'):PUB.index('def _supersede_prior_homologations',PUB.index('def _create_preview_runtime_homologation_candidate'))]
        self.assertIn("stage_identity={'public_number':num,'stage':'homologation','number':candidate} if slug=='paperclip' else None",block)
        self.assertIn("stage_identity=stage_identity",block)
        self.assertIn("'stage_identity':stage_identity",BROKER)
        self.assertIn("invalid_stage_identity",BROKER)

    def test_executor_rewrites_only_public_identity_not_secrets(self):
        block=EXEC[EXEC.index('def deploy_compose_snapshot'):EXEC.index('def assigned_port',EXEC.index('def deploy_compose_snapshot'))]
        self.assertIn("slug=='paperclip' and environment=='homologation'",block)
        self.assertIn("env.pop('PAPERCLIP_PUBLIC_URL',None)",block)
        self.assertIn("env['PAPERCLIP_AUTH_BASE_URL_MODE']='auto'",block)
        self.assertIn("env['PAPERCLIP_ALLOWED_HOSTNAMES']=h_host+','+stable_host",block)
        self.assertNotIn("BETTER_AUTH_SECRET",block)

    def test_production_bridge_uses_stable_numeric_runtime_host_without_recreate(self):
        block=PUB[PUB.index('def _publish_linked_compose_homologated_candidate'):PUB.index('def _compose_snapshot_promote',PUB.index('def _publish_linked_compose_homologated_candidate'))]
        self.assertIn("runtime_host=(f'{num}.cloudiff.duckdns.org' if slug=='paperclip' else '')",block)
        self.assertIn("runtime_host=runtime_host",block)
        self.assertIn("containersRecreated') is not False",block)
        self.assertIn("runtime_host!=f'{public_number}.cloudiff.duckdns.org'",BROKER)
        self.assertIn("runtime_host!=f'{public_number}.cloudiff.duckdns.org'",EXEC)
        self.assertIn("proxy_set_header X-Forwarded-Host",EXEC)

if __name__=='__main__': unittest.main()
