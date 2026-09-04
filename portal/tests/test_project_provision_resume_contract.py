from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
ACTION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py').read_text()
WORKER=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
LEGACY=(ROOT/'portal/legacy/cloudif-admin-portal-base.py').read_text()
UNIT=(ROOT/'components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.service').read_text()


class ProjectProvisionResumeContractTests(unittest.TestCase):
    def test_resume_action_uses_existing_queue_and_owner_material(self):
        for marker in ('def resume_initial_publication(form, user):','resume_material(slug,user,global_admin=global_admin)','queue_provision_job(job)',"if action == 'resume_initial_publication':"):
            self.assertIn(marker,ACTION)

    def test_worker_resume_path_reapplies_template_only_when_recovery_starts_before_template(self):
        start=WORKER.index("if str(job.get('action') or '')=='resume_initial_publication':")
        end=WORKER.index('candidates = [',start)
        block=WORKER[start:end]
        self.assertIn("if str(job.get('resume_from') or '')=='template':",block)
        self.assertIn("cloudif-project-template-apply.py",block)
        self.assertIn("cloudif-project-initial-publish.py",block)
        self.assertIn("set_state(path,job,'running','initial-publication')",block)
        self.assertIn("result['resume_only']=True",block)
        self.assertIn("enqueue_post_provision(slug,job,'project.membership.changed')",block)
        for forbidden in ('cloudif-project-provision.sh','tenant-policy-ensure','project-backup.py'):
            self.assertNotIn(forbidden,block)

    def test_worker_persists_repo_for_release_and_enqueues_post_provision(self):
        for marker in ('release_settings','repo_full_name=excluded.repo_full_name','def enqueue_post_provision','project_provision_completed','cloudif-reconcile-worker.service'):
            self.assertIn(marker,WORKER)

    def test_portal_uses_durable_status_and_shows_controlled_resume(self):
        for source in (BASE,LEGACY):
            self.assertIn('from cloudif_project_provision_status import status as provision_status',source)
            self.assertIn("value=\"resume_initial_publication\"",source)
            self.assertIn("if provision_state.get('recoverable') else ''",source)
            self.assertIn('A retomada continuará da última etapa segura sem recriar projeto, repositório ou banco.',source)
            self.assertIn('data-provision-recoverable=',source)

    def test_project_state_reconciler_can_read_portal_database(self):
        self.assertIn('ReadWritePaths=/run /var/lib/cloudif/health /var/lib/cloudif/portal /srv/cloudif/jobs',UNIT)
        self.assertIn('ProtectSystem=strict',UNIT)
        reconciler=(ROOT/'components/control-plane/current-apps/project-state-reconcile-current/cloudif-project-state-reconcile.py').read_text()
        self.assertIn("sqlite3.connect(f'file:{PORTAL_DB}?mode=ro'",reconciler)
        self.assertNotIn('sqlite3.connect(PORTAL_DB)',reconciler)


if __name__=='__main__':unittest.main()
