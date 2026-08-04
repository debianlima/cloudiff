from pathlib import Path
import unittest

class KomodoLocalHealthJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_healthy_result_does_not_embed_itself(self):
        self.assertIn('result=dict(item)',self.source)
        self.assertIn('"candidates":[dict(x) for x in inspected]',self.source)
        self.assertNotIn('item.update({"ok":True,"expected_compose":expected_compose,"candidates":inspected})',self.source)

if __name__=='__main__':unittest.main()
