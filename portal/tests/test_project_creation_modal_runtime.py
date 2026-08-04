import importlib.util
import os
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def first_existing(*paths):
    for value in paths:
        if value and Path(value).exists():
            return Path(value)
    raise FileNotFoundError(paths)
PORTAL_PATH=first_existing(
    os.environ.get('CLOUDIF_TEST_PORTAL_SOURCE'),
    ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py',
    '/srv/cloudif/app-pointers/portal-current/cloudif-admin-portal.py',
)
ACTION_PATH=first_existing(
    ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py',
    '/srv/cloudif/lib/cloudif_project_action_safe.py',
)
PROVISION_PATH=first_existing(
    ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py',
    '/srv/cloudif/lib/cloudif_project_provision_real.py',
)
TEMPLATE=first_existing(
    ROOT/'components/control-plane/usr/local/sbin/cloudif-project-template-apply.py',
    '/usr/local/sbin/cloudif-project-template-apply.py',
)
PORTAL=PORTAL_PATH.read_text()
ACTION=ACTION_PATH.read_text()
PROVISION=PROVISION_PATH.read_text()

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
        spec=importlib.util.spec_from_file_location('tpl',TEMPLATE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        node=dict(module.merge_runtime([('.env','CLOUDIF_PUBLIC_NUMBER=1001\nCLOUDIF_DEPLOY_NUMBER=1\n')],'node22','8.3'))
        self.assertIn('FROM php:8.3-apache',node['.cloudif/Dockerfile.base'])
        self.assertIn('ARG NODE_MAJOR=22',node['.cloudif/Dockerfile.base'])
        self.assertIn('FROM cloudif/runtime-apache-php8.3-node22:v1',node['.cloudif/Dockerfile'])
        self.assertIn('site/index.php',node)
        self.assertIn('site/api/server.js',node)
        self.assertIn('.cloudif/docker-compose.yml',node)
        self.assertNotIn('Dockerfile.php',node)
        self.assertNotIn('docker-compose.yml',node)

    def test_acl_uses_supported_reconciliation_event(self):
        self.assertIn('"project.updated",',PORTAL)
        self.assertIn('"source":"project_acl"',PORTAL)
        self.assertIn('"targets":["portal","forgejo","tenant","publication"]',PORTAL)
        self.assertNotIn('"project.acl.changed",',PORTAL)

if __name__=='__main__':
    unittest.main()
