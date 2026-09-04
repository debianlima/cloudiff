from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
CONFIG=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_publication_config.py').read_text()
PUBLISHER=(ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text()
GATEWAY=(ROOT/'components/runtime/srv/cloudif/publication-gateway/conf.d/10-generic-publications.conf').read_text()

class WHPReleaseFlowTests(unittest.TestCase):
    def test_environment_contract_is_explicit_for_all_three_stages(self):
        self.assertIn("{'preview','homologation','production'}",CONFIG)
        self.assertIn("def environment_summary(slug:str,environment:str='production')",CONFIG)
        self.assertIn("def execution_environment(slug:str,expected_revision:int,expected_digest:str,environment:str='production')",CONFIG)
        self.assertIn("{'environment':environment,'references':references",CONFIG)

    def test_preview_is_live_workspace_and_git_failure_is_fail_soft(self):
        latest=RUNTIME[RUNTIME.index('def _cloudif_stage_env_root'):]
        self.assertIn("dst=/var/www/html",latest)
        self.assertIn("cloudif.stage=preview",latest)
        self.assertIn("remoteAvailable':False,'status':'degraded'",latest)
        self.assertIn('O Preview continua usando a cópia local',latest)
        self.assertIn("error':'git_remote_unavailable'",latest)
        self.assertIn('env_path},dst=/run/cloudif/runtime.env,readonly',latest)
        self.assertIn('cloudif-preview-security.conf',latest)

    def test_preview_terminal_targets_only_the_active_w_container(self):
        latest=RUNTIME[RUNTIME.index('def cloudif_preview_terminal'):RUNTIME.index('def cloudif_preview_snapshot')]
        self.assertIn("cloudif-p{num}-w{generation}-preview-web",latest)
        self.assertIn("_cloudif_wait_health(container,2)",latest)
        self.assertIn("_cloudif_ensure_container_terminal(server_id,container)",latest)
        self.assertIn("'terminalReady':True",latest)
        self.assertIn("'secretValuesIncluded':False",latest)
        self.assertIn('/komodo/project/preview/terminal',RUNTIME)
        self.assertIn('def preview_terminal(slug,user):',PORTAL)
        self.assertIn("if not auth.get('canWrite')",PORTAL)
        self.assertIn("terminalSource':'preview_workspace'",PORTAL)

    def test_homologation_freezes_code_runtime_and_exposes_diffs(self):
        latest=RUNTIME[RUNTIME.index('def cloudif_preview_snapshot'):]
        self.assertIn("GIT_INDEX_FILE",latest)
        self.assertIn("commit-tree",latest)
        self.assertIn("docker','commit','--pause=true'",latest)
        self.assertIn("'diff':{'files':files[:300]",latest)
        self.assertIn("'runtimeDiff':{'changes':runtime_changes[:200]",latest)
        self.assertIn("preview-w{generation}-h{candidate}-runtime",latest)

    def test_large_repository_homologation_has_build_headroom(self):
        self.assertIn('HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT=900',PORTAL)
        self.assertIn('HOMOLOGATION_DEPLOY_HTTP_TIMEOUT=1020',PORTAL)
        self.assertIn("'timeout':HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT",PORTAL)
        self.assertIn("'build_timeout':HOMOLOGATION_DEPLOY_RUNTIME_TIMEOUT",PORTAL)
        self.assertIn('import hashlib, hmac, json',PORTAL)
        self.assertIn('hmac.compare_digest',PORTAL)
        self.assertIn("payload.get('build_timeout') or payload.get('timeout') or 300",RUNTIME)
        self.assertIn("timeout=HOMOLOGATION_DEPLOY_HTTP_TIMEOUT",PORTAL)
        self.assertGreater(900,300)

    def test_publication_uses_exact_homologated_artifact_without_rebuild(self):
        release=RUNTIME[RUNTIME.index('def cloudif_publication_release(handler):'):RUNTIME.index('def cloudif_publication_release_activate(handler):')]
        self.assertIn("source=f'cloudif-p{num}-d{dep}-web'",release)
        self.assertIn("hmac.compare_digest(expected,image_id)",release)
        self.assertIn("image,image_id=parts[2],parts[3]",release)
        self.assertIn("cloudif-p{num}-p{publication}-publication-web",release)
        self.assertNotIn("docker','build",release)
        self.assertNotIn('environment_variables',release[release.index("cmd=['docker','run'"):])

    def test_stage_hostnames_are_unambiguous(self):
        for marker in ('-w(?<w>[0-9]+)-preview','-h(?<h>[0-9]+)-homologation','-p(?<r>[0-9]+)-publication'):
            self.assertIn(marker,GATEWAY)
        self.assertIn("labels={'preview':('w','preview'),'homologation':('h','homologation'),'publication':('p','publication')}",PUBLISHER)
        self.assertIn("if self.path=='/stage'",PUBLISHER)
        self.assertIn("if self.path=='/version'",PUBLISHER)

    def test_portal_separates_candidate_homologator_and_release_state(self):
        for table in ('project_homologators','publication_candidates','production_releases','production_activation_requests'):
            self.assertIn('CREATE TABLE IF NOT EXISTS '+table,PORTAL)
        for fn in ('ensure_preview','create_homologation_candidate','homologate_candidate','request_production_activation','publish_homologated_candidate','rollback_publication'):
            self.assertIn('def '+fn+'(',PORTAL)
        self.assertIn("sameArtifactAsHomologation':True",PORTAL)

    def test_preview_can_recreate_from_new_or_legacy_active_production(self):
        latest=RUNTIME[RUNTIME.index('def _cloudif_preview_create'):RUNTIME.index('def cloudif_preview_request')]
        self.assertIn("stage_production_releases where project=? and is_active=1",latest)
        self.assertIn("publication_runtimes where project=? and is_active=1 and status='ready'",latest)
        self.assertIn("docker','inspect',legacy_container,'--format','{{.Config.Image}}'",latest)

    def test_portal_uses_canonical_approval_environment_file(self):
        self.assertIn("cfg=_env('/etc/cloudif/approvals.env')",PORTAL)
        self.assertIn("cfg=_env('/etc/cloudif/approval-service.env')",PORTAL)
        self.assertIn("CLOUDIF_APPROVAL_TOKEN",PORTAL)

    def test_production_is_bound_to_critical_dual_approval(self):
        self.assertIn("'action':'deployment.production.activate'",PORTAL)
        self.assertIn("activationDigest",PORTAL)
        self.assertIn("_validate_production_approval",PORTAL)
        self.assertIn("'/reserve'",PORTAL)
        self.assertIn("_finalize_production_approval",PORTAL)
        self.assertIn("approval.get('requested_by')!=str(local['requested_by'])",PORTAL)
        self.assertIn("metadata.get('secret_values_in_metadata') is not False",PORTAL)

if __name__=='__main__':unittest.main()
