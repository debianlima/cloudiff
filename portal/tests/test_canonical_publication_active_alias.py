from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / 'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'


class CanonicalPublicationActiveAliasTest(unittest.TestCase):
    def test_activation_detaches_legacy_d_from_shared_active_alias(self):
        source = AGENT.read_text(encoding='utf-8')
        self.assertIn("legacy_containers=[n for n in names if re.match(rf'^cloudif-p{num}-d\\d+-web$',n)]", source)
        self.assertIn("routable_containers=production_containers+legacy_containers", source)
        self.assertIn("previous=next((n for n in routable_containers if active in aliases(n)),''", source)
        self.assertIn("for name in routable_containers:", source)
        self.assertIn("legacy=[n for n in names if re.match(rf'^cloudif-p{num}-d\\d+-web$',n)]", source)
        self.assertIn("for name in candidates+legacy:", source)


if __name__ == '__main__':
    unittest.main()
