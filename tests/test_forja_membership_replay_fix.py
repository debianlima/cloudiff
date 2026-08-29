import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
class ForjaMembershipReplayFixTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.text=SRC.read_text(); cls.tree=ast.parse(cls.text)
 def test_membership_uses_defined_slug_helper(self):
  fn=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=='reconcile_project_membership')
  calls=[n.func.id for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  self.assertIn('_v118_slug',calls)
  self.assertNotIn('safe_slug',calls)
 def test_slug_helper_is_defined_before_membership(self):
  defs={n.name:n.lineno for n in self.tree.body if isinstance(n,ast.FunctionDef)}
  self.assertIn('_v118_slug',defs)
  self.assertIn('reconcile_project_membership',defs)
  self.assertLess(defs['_v118_slug'],defs['reconcile_project_membership'])
 def test_route_still_dispatches_membership_reconcile(self):
  self.assertIn('if path == "/project/membership/reconcile":',self.text)
  self.assertIn('result=reconcile_project_membership(data)',self.text)
if __name__=='__main__': unittest.main()
