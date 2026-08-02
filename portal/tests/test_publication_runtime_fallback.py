import unittest
from pathlib import Path


class PublicationRuntimeFallbackTest(unittest.TestCase):
    def test_runtime_supports_common_web_directories_and_placeholder(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py").read_text()
        self.assertIn('(\"site\",\"dist\",\"build\",\"public\")', source)
        self.assertIn('git_file("index.html")', source)
        self.assertIn('generated_placeholder=not publication_files', source)
        self.assertIn('CloudIFF · pré-publicação', source)
        self.assertIn('generated_nginx', source)


if __name__ == "__main__":
    unittest.main()
