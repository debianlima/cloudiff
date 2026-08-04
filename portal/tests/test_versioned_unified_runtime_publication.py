from pathlib import Path
import unittest

class VersionedUnifiedRuntimePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_runtime_manifest_selects_unified_runtime(self):
        for marker in ('git_file(".cloudif/runtime.json")','unified_runtime=bool','runtime_manifest.get("php")','runtime_manifest.get("node")'):
            self.assertIn(marker,self.source)
    def test_versioned_image_reuses_project_runtime(self):
        for marker in ('FROM cloudif/project-{public_number}:php{php}-node{node}','Dockerfile.runtime','cloudif/publication-p{public_number}-d{deploy_number}'):
            self.assertIn(marker,self.source)
    def test_php_node_compose_uses_apache_health(self):
        self.assertIn('curl -fsS http://127.0.0.1/.cloudif-health',self.source)
        self.assertIn('runtime\"]=\"unified-php-node',self.source)
        self.assertIn('\"run_build\": bool(unified_runtime)',self.source)
        self.assertIn('actual_image==expected_image',self.source)
        self.assertIn('\"auto_pull\": not bool(unified_runtime)',self.source)
        self.assertIn('context: .',self.source)
        self.assertIn('version_runtime_stage_failed',self.source)
        self.assertIn('shutil.copytree(snap_dir / "site",staged_site)',self.source)
    def test_static_nginx_fallback_remains_for_static_sites(self):
        self.assertIn('nginxinc/nginx-unprivileged:1.27-alpine',self.source)

if __name__=='__main__': unittest.main()
