import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py').read_text()
ACTION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
PROVISION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
TEMPLATE=ROOT/'components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'

class ProjectCreationModalRuntimeTest(unittest.TestCase):
    def test_permissions_and_new_project_are_overlay_modals(self):
        self.assertIn('.cloudif-wizard{position:fixed!important;inset:0!important',PORTAL)
        self.assertIn("target.style.display='grid'",PORTAL)
        self.assertIn("document.body.classList.add('cloudif-modal-open')",PORTAL)
        self.assertIn("role=\"dialog\" aria-modal=\"true\"",PORTAL)

    def test_new_project_uses_integrated_project_action(self):
        block=PORTAL[PORTAL.rfind('id="pm197_new"'):]
        for marker in (
            "action=\"{url('/action/project_action')}\"",
            'name="action" value="create_project"',
            'name="create_repo" value="1"',
            'name="setup_komodo" value="1"',
            'name="runtime_template"',
            'name="csrf_token"',
        ):
            self.assertIn(marker,block)

    def test_runtime_is_validated_and_forwarded(self):
        self.assertIn('allowed_runtimes',ACTION)
        self.assertIn('"runtime_template": runtime_template',ACTION)
        self.assertIn('"runtime_template": job.get("runtime_template")',PROVISION)

    def test_runtime_templates_generate_real_files(self):
        spec=importlib.util.spec_from_file_location('cloudif_template_apply',TEMPLATE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        node=dict(module.merge_runtime([('docker-compose.yml','base')],'node22'))
        php=dict(module.merge_runtime([('docker-compose.yml','base')],'php83-apache'))
        self.assertIn('FROM node:22-alpine',node['Dockerfile'])
        self.assertIn('package.json',node)
        self.assertIn('server.js',node)
        self.assertIn('FROM php:8.3-apache',php['Dockerfile'])
        self.assertIn('site/health.php',php)

    def test_acl_uses_supported_reconciliation_event(self):
        self.assertIn('"project.updated",',PORTAL)
        self.assertIn('"source":"project_acl"',PORTAL)
        self.assertIn('"targets":["portal","forgejo","tenant","publication"]',PORTAL)
        self.assertNotIn('"project.acl.changed",',PORTAL)

if __name__=='__main__':
    unittest.main()
