import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/reconciliation/project-events-cpp-reconciliation-v59.json'
CLIENT=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py'
WORKER=ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'
CONTROL=ROOT/'src/control/main.cpp'
ACTION=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py'
PUBLICATIONS=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'

class ProjectEventsCppReconciliationEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(EVIDENCE.read_text())
  cls.client=CLIENT.read_text(); cls.worker=WORKER.read_text(); cls.control=CONTROL.read_text()
  cls.action=ACTION.read_text(); cls.publications=PUBLICATIONS.read_text()

 def test_durable_producers_and_queue_are_explicit(self):
  for ev in ('project.created','project.membership.changed'):
   self.assertIn(f'"{ev}"',self.client)
  self.assertIn('INSERT INTO reconcile_requests',self.client)
  self.assertIn('os.replace(tmp_name, QUEUE / f"{request_id}.json")',self.client)
  self.assertIn('"project.created" if action == "create_project"',self.action)
  self.assertIn("enqueue('project.membership.changed'",self.publications)

 def test_python_worker_is_the_effect_consumer(self):
  self.assertIn('"project.created"',self.worker)
  self.assertIn('"project.membership.changed"',self.worker)
  self.assertIn('membership=reconcile_project_membership(project)',self.worker)
  self.assertIn('update_request(rid,status,msg,',self.worker)

 def test_cpp_control_is_node_observation_only(self):
  self.assertIn('cloudiff.v2.node.observed',self.control)
  self.assertIn('apply_observation(event)',self.control)
  self.assertNotIn('project.created',self.control)
  self.assertNotIn('project.membership.changed',self.control)

 def test_live_evidence_does_not_overclaim_cpp_project_reconciliation(self):
  e=self.e
  self.assertEqual(e['schema_version'],1)
  self.assertEqual(e['host']['ip'],'10.62.92.7')
  self.assertTrue(e['cpp_control']['active'])
  self.assertEqual(e['cpp_control']['binary_version'],'0.15.0-shadow')
  self.assertEqual(e['cpp_control']['subscription'],'cloudiff.v2.node.observed')
  self.assertTrue(e['python_reconcile_worker']['path_active'])
  self.assertTrue(e['python_reconcile_worker']['timer_active'])
  self.assertEqual(e['queue']['current_nonterminal'],[])
  self.assertEqual(e['queue']['historical_membership_dead_letter_count'],2)
  self.assertFalse(e['conclusions']['project_event_reconciliation_cpp_migrated'])
  self.assertTrue(e['conclusions']['python_reconcile_worker_authoritative'])
  self.assertFalse(e['conclusions']['safe_to_retire_python_reconcile_worker'])

if __name__=='__main__': unittest.main()
