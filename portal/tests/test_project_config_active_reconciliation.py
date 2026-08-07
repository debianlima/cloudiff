from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
CONTROLLER=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
RECONCILER=ROOT/'components/control-plane/current-apps/project-config-reconciler-current/cloudif-project-config-reconciler.py'
EVENTS=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_config_events.py'
WORKER=ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'
WORKER_MIRROR=ROOT/'components/control-plane/usr/local/sbin/cloudif-reconcile-worker.py'
RECONCILER_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-project-config-reconciler.service'
WORKER_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-reconcile-worker.service'

class ActiveProjectConfigurationReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller=CONTROLLER.read_text();cls.reconciler=RECONCILER.read_text();cls.events=EVENTS.read_text();cls.worker=WORKER.read_text()

    def test_controller_queues_events_for_active_verification(self):
        self.assertIn("'mode': 'active-verification'",self.controller)
        self.assertIn("'pending'",self.controller)
        self.assertIn("observation_status='reconcile_pending'",self.controller)
        self.assertIn("'reconciliationPending': True",self.controller)
        self.assertIn("'project.membership.reconciled'",self.controller)

    def test_membership_mapping_does_not_increment_for_publication(self):
        tree=ast.parse(self.events)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='event_for_reconcile')
        module=ast.Module(body=[fn],type_ignores=[]);ast.fix_missing_locations(module);ns={};exec(compile(module,'<events>','exec'),ns)
        mapping=ns['event_for_reconcile']
        self.assertEqual(mapping('project.membership.changed',{'source':'project_acl','operation':'add'}),'project.member.added')
        self.assertEqual(mapping('project.membership.changed',{'source':'project_acl','operation':'remove'}),'project.member.removed')
        self.assertEqual(mapping('project.membership.changed',{'source':'publication_activation','operation':'reconcile'}),'publication.created')
        self.assertEqual(mapping('project.membership.changed',{'operation':'reconcile'}),'project.membership.reconciled')

    def test_reconciler_requires_matching_build_without_triggering_effects(self):
        for marker in ('toolchain_build_required','application_build_required','create_multiservice_build','matchingBuildSucceeded','latest_build','config_digest','toolchain_digest'):
            self.assertIn(marker,self.reconciler)
        for forbidden in ('docker build','docker run','subprocess.','shell=True','os.system('):
            self.assertNotIn(forbidden,self.reconciler)

    def test_secret_values_are_not_read_or_persisted(self):
        self.assertIn("'secretValuesRead':False",self.reconciler)
        self.assertIn("'secretsExposed':False",self.reconciler)
        self.assertNotIn('POSTGRES_PASSWORD',self.reconciler+self.events)
        self.assertNotIn('SERVICE_ROLE_KEY',self.reconciler+self.events)
        self.assertIn('secretValuesIncluded',self.controller)

    def test_existing_reconcile_worker_delivers_configuration_event(self):
        self.assertIn('import cloudif_project_config_events as config_events',self.worker)
        self.assertIn('config_events.notify(project,event,payload)',self.worker)
        self.assertIn('configuration_event',self.worker)
        self.assertEqual(WORKER.read_bytes(),WORKER_MIRROR.read_bytes())
        unit=WORKER_UNIT.read_text()
        self.assertIn('cloudif-project-config-controller.service',unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/project-config-controller.env',unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/runtime-reconciler.env',unit)
        self.assertIn('reconcile_project_runtime(project,environment)',self.worker)

    def test_reconciler_service_is_local_and_hardened(self):
        unit=RECONCILER_UNIT.read_text()
        for marker in ('CLOUDIF_PROJECT_CONFIG_RECONCILER_HOST=127.0.0.1','CLOUDIF_PROJECT_CONFIG_RECONCILER_PORT=18229','IPAddressAllow=127.0.0.0/8','IPAddressDeny=any','NoNewPrivileges=true','CapabilityBoundingSet=','ReadWritePaths=/var/lib/cloudif/project-config'):
            self.assertIn(marker,unit)

if __name__=='__main__':unittest.main()
