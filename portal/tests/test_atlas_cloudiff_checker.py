"""Regression tests for the offline read-only Atlas/CloudIFF reconciler."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_atlas_cloudiff.py"
SPEC = importlib.util.spec_from_file_location("atlas_cloudiff_reconcile", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def fixtures():
    repo = "https://example.invalid/git/team/cloudif-demo"
    return (
        {"tables": {"projects": [{
            "slug": "demo", "name": "Demo", "status": "published", "repo_url": repo
        }]}},
        {"items": [
            {"id": "cloudiff.project.demo", "kind": "project", "name": "Demo",
             "status": "publicado (Portal)", "repo_url": repo},
            {"id": "cloudiff.repo.demo", "kind": "repo", "status": "referenciado (Portal)",
             "repo_url": repo},
        ]},
    )


class CloudIFFAtlasReconciliationTests(unittest.TestCase):
    def test_match(self):
        portal, atlas = fixtures()
        result = MOD.reconcile(portal, atlas)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["readonly"])

    def test_missing_atlas_repo(self):
        portal, atlas = fixtures()
        atlas["items"].pop()
        result = MOD.reconcile(portal, atlas)
        self.assertIn("missing", {i["type"] for i in result["issues"]})

    def test_duplicate_atlas_repo(self):
        portal, atlas = fixtures()
        atlas["items"].append(dict(atlas["items"][-1]))
        self.assertIn("duplicate", {i["type"] for i in MOD.reconcile(portal, atlas)["issues"]})

    def test_changed_repo_url(self):
        portal, atlas = fixtures()
        atlas["items"][0]["repo_url"] = "https://example.invalid/other"
        self.assertIn("repo_url_mismatch",
                      {i["type"] for i in MOD.reconcile(portal, atlas)["issues"]})

    def test_changed_portal_status(self):
        portal, atlas = fixtures()
        portal["tables"]["projects"][0]["status"] = "draft"
        self.assertIn("administrative_status_mismatch",
                      {i["type"] for i in MOD.reconcile(portal, atlas)["issues"]})

    def test_unexpected_extra_atlas_record(self):
        portal, atlas = fixtures()
        atlas["items"].append({"id": "cloudiff.project.unknown", "kind": "project"})
        self.assertIn("atlas_only_requires_review",
                      {i["type"] for i in MOD.reconcile(portal, atlas)["issues"]})

    def test_missing_portal_projects_fails_closed(self):
        _, atlas = fixtures()
        with self.assertRaises(ValueError):
            MOD.reconcile({"tables": {}}, atlas)

    def test_missing_atlas_items_fails_closed(self):
        portal, _ = fixtures()
        with self.assertRaises(ValueError):
            MOD.reconcile(portal, {})

    def test_bad_record_type_fails(self):
        portal, atlas = fixtures()
        atlas["items"].append("not-an-object")
        with self.assertRaises(ValueError):
            MOD.reconcile(portal, atlas)

    def test_cli_exit_codes_and_no_secret_output(self):
        portal, atlas = fixtures()
        portal["tables"]["projects"][0]["sensitive_token"] = "NEVER_PRINT_SECRET"
        with tempfile.TemporaryDirectory() as d:
            p, a = Path(d) / "portal.json", Path(d) / "atlas.json"
            p.write_text(json.dumps(portal))
            a.write_text(json.dumps(atlas))
            with patch("sys.argv", ["checker", "--portal-json", str(p), "--atlas-json", str(a)]):
                out = io.StringIO()
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    self.assertEqual(MOD.main(), 0)
                self.assertNotIn("NEVER_PRINT_SECRET", out.getvalue())
            a.write_text("{}")
            with patch("sys.argv", ["checker", "--portal-json", str(p), "--atlas-json", str(a)]):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(MOD.main(), 3)


if __name__ == "__main__":
    unittest.main()
