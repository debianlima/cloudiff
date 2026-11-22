from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
AGENT=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'

class FixedPreviewRuntimeV144Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=AGENT.read_text()
        cls.tree=ast.parse(cls.source)

    def _last_function(self,name):
        nodes=[n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
        self.assertTrue(nodes,name)
        lines=self.source.splitlines(True);n=nodes[-1]
        return ''.join(lines[n.lineno-1:n.end_lineno])

    def test_final_preview_create_is_fixed_w1_continuous_runtime(self):
        block=self._last_function('_cloudif_preview_create')
        self.assertIn("container=f'cloudif-p{public_number}-preview-web'",self.source)
        self.assertIn("generation':1",block)
        self.assertIn("stageCode':'W1'",block)
        self.assertNotIn("generation=int((old or {}).get('generation') or 0)+1",block)

    def test_preview_stack_keeps_public_w1_dns_alias(self):
        block=self._last_function('_cloudif_v144_preview_stack')
        self.assertIn("cloudif-p{public_number}-w1-preview-web",block)
        self.assertIn("aliases:",block)

    def test_ensure_migrates_old_generation_to_fixed_runtime_and_sync_starts(self):
        block=self._last_function('cloudif_preview_request')
        self.assertIn("expected=f'cloudif-p{num}-preview-web'",block)
        self.assertIn("migrated=not row",block)
        self.assertIn("_cloudif_v144_start_preview_sync()",self.source)

if __name__=='__main__': unittest.main()
