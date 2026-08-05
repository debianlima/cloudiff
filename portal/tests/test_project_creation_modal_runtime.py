import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
ACTION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
PROVISION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text()
TEMPLATE=ROOT/'components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'

class ProjectCreationModalRuntimeTest(unittest.TestCase):
    def test_permissions_and_new_project_are_overlay_modals(self):
        self.assertIn('.cloudif-wizard{position:fixed!important;inset:0!important',PORTAL)
        self.assertIn("target.style.display='grid'",PORTAL)
        self.assertIn("document.body.classList.add('cloudif-modal-open')",PORTAL)
        self.assertIn('role="dialog" aria-modal="true"',PORTAL)

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
        self.assertIn('"runtime_layout": "managed-root-v1"',ACTION)
        self.assertIn('"php_version": job.get("php_version")',PROVISION)
        self.assertIn('"runtime_layout": job.get("runtime_layout") or "managed-root-v1"',PROVISION)

    def test_repository_template_contains_only_root_source(self):
        spec=importlib.util.spec_from_file_location('tpl',TEMPLATE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        files=dict(module.merge_runtime([
            ('site/index.html','home'),
            ('site/assets/app.js','code'),
            ('.cloudif/docker-compose.yml','infra'),
            ('docker-compose.yml','infra'),
            ('.env','secret'),
        ],'node22','8.3'))
        self.assertEqual(files['index.html'],'home')
        self.assertEqual(files['assets/app.js'],'code')
        self.assertIn('api/server.js',files)
        self.assertIn('api/package.json',files)
        self.assertFalse(any(name.startswith('site/') for name in files))
        self.assertFalse(any(name.startswith('.cloudif/') for name in files))
        for forbidden in ('docker-compose.yml','.env','Dockerfile','nginx.conf'):
            self.assertNotIn(forbidden,files)

    def test_acl_uses_membership_reconciliation_event(self):
        self.assertIn('"project.membership.changed",',PORTAL)
        self.assertIn('"source":"project_acl"',PORTAL)
        self.assertIn('Forgejo, Komodo, terminal, tenant e integrações',PORTAL)
        self.assertNotIn('"project.acl.changed",',PORTAL)

if __name__=='__main__':unittest.main()
