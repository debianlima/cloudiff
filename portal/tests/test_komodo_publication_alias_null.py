from pathlib import Path
import unittest

SOURCE=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class KomodoPublicationAliasNullTests(unittest.TestCase):
    def test_production_release_tolerates_null_network_aliases(self):
        start=SOURCE.index('def cloudif_publication_release(handler):')
        end=SOURCE.index('def cloudif_publication_release_activate(handler):',start)
        block=SOURCE[start:end]
        self.assertIn("raw = subprocess.check_output",block)
        self.assertIn("return json.loads(raw) if raw and raw != 'null' else []",block)
        self.assertNotIn("return json.loads(subprocess.check_output",block)

if __name__=='__main__': unittest.main()
