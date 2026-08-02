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


    def test_runtime_falls_back_to_normalized_stack_and_local_server(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py").read_text()
        self.assertIn('expected_names = {project, f"cloudif-{project}"}', source)
        self.assertIn('expected_repo = f"cloudif/{project}"', source)
        self.assertIn('item.get("name") == "Local"', source)
        self.assertIn('get("state") == "Ok"', source)


if __name__ == "__main__":
    unittest.main()
