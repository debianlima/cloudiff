"""Prevent regression to credential-bearing Git URL construction."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PATHS=[ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py',ROOT/'components/runtime/usr/local/sbin/cloudif-forja-agent.py']
class NoLegacyAuthUrl(unittest.TestCase):
    def test_no_legacy_credential_url_builder(self):
        for p in PATHS:
            tree=ast.parse(p.read_text())
            names={node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
            self.assertNotIn('_v119_forgejo_repo_git_url',names)
            self.assertIn('_v119_git_ephemeral_auth',names)
    def test_mirror_byte_identical(self):
        self.assertEqual(PATHS[0].read_bytes(),PATHS[1].read_bytes())
if __name__=='__main__':unittest.main()
