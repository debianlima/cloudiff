"""Regression: generic PHP/Apache preview must not overwrite Paperclip Node24 W1.

Only isolated AST functions are evaluated; never import the live agent.
"""
from __future__ import annotations
import ast
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py"

def load_latest(name, globals_: dict):
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"))
    nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name]
    if not nodes:
        raise AssertionError("missing runtime function: " + name)
    isolated = ast.Module(body=[nodes[-1]], type_ignores=[])
    ast.fix_missing_locations(isolated)
    scope = dict(globals_)
    exec(compile(isolated, str(RUNTIME), "exec"), scope)
    return scope[name]

def do_not_mutate(*_args, **_kwargs):
    raise AssertionError("generic Paperclip preview attempted state mutation")

class PaperclipNativeRequiredTests(TestCase):
    def test_direct_v144_preview_create_rejects_before_checkout_or_schema(self):
        op = load_latest("_cloudif_preview_create", {
            "safe_slug": str, "_cloudif_v144_ensure_schema": do_not_mutate,
            "_cloudif_v143_ensure_checkout": do_not_mutate})
        result = op("paperclip", 1025, "portal", {}, 1, "digest")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "paperclip_native_runtime_required")
        self.assertEqual(result["stageCode"], "W1")
        self.assertFalse(result["secretValuesIncluded"])

    def test_other_projects_are_not_blocked_by_native_guard(self):
        op = load_latest("_cloudif_preview_create", {
            "safe_slug": str, "_cloudif_v144_ensure_schema": do_not_mutate})
        with self.assertRaisesRegex(AssertionError, "state mutation"):
            op("outro", 1002, "portal", {}, 1, "digest")

    def test_ensure_and_recreate_fail_before_env_database_or_docker(self):
        sent = []
        def send(_handler, status, content):
            sent.append((status, content))
            return status, content
        op = load_latest("cloudif_preview_request", {
            "_cloudif_pub_auth": lambda _handler: True,
            "_cloudif_pub_json": lambda _handler: {"project": "paperclip", "public_number": 1025},
            "safe_slug": str, "send": send,
            "_cloudif_v144_ensure_schema": do_not_mutate,
            "_cloudif_preview_row": do_not_mutate,
            "_cloudif_stage_write_environment": do_not_mutate})
        for operation in ("ensure", "recreate"):
            status, content = op(None, operation)
            self.assertEqual(status, 409)
            self.assertEqual(content["error"], "paperclip_native_runtime_required")
            self.assertEqual(content["project"], "paperclip")
            self.assertFalse(content["secretValuesIncluded"])
        self.assertEqual(len(sent), 2)

    def test_unauthenticated_request_fails_before_project_check(self):
        op = load_latest("cloudif_preview_request", {
            "_cloudif_pub_auth": lambda _handler: False,
            "_cloudif_pub_json": do_not_mutate,
            "send": lambda _handler, status, content: (status, content)})
        status, body = op(None, "ensure")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "forbidden")

    def test_legacy_apache_health_does_not_certify_paperclip(self):
        row={"public_number":1025,"container":"cloudif-p1025-w1-preview-web",
             "stack_id":"legacy-stack","stack_name":"generic-apache",
             "git_sync_status":"synced","environment_revision":3}
        op=load_latest("cloudif_preview_request", {
            "_cloudif_pub_auth":lambda _:True,
            "_cloudif_pub_json":lambda _:{"project":"paperclip","public_number":1025},
            "safe_slug":str,"send":lambda _h,code,body:(code,body),
            "_cloudif_v144_ensure_schema":lambda:None,
            "_cloudif_preview_row":lambda _:row,
            "_cloudif_wait_health":lambda *args:{"ok":True},
            "db_exec":do_not_mutate,"_cloudif_stage_write_environment":do_not_mutate})
        code,body=op(None,"status")
        self.assertEqual(code,200)
        self.assertTrue(body["configured"])
        self.assertFalse(body["healthy"])
        self.assertFalse(body["continuous"])
        self.assertTrue(body["legacyContainerHealthy"])
        self.assertTrue(body["nativeRuntimeRequired"])
        self.assertFalse(body["applicationE2EVerified"])
        self.assertFalse(body["secretValuesIncluded"])

    def test_unconfigured_paperclip_requires_native_runtime(self):
        op=load_latest("cloudif_preview_request", {
            "_cloudif_pub_auth":lambda _:True,
            "_cloudif_pub_json":lambda _:{"project":"paperclip","public_number":1025},
            "safe_slug":str,"send":lambda _h,code,body:(code,body),
            "_cloudif_v144_ensure_schema":lambda:None,
            "_cloudif_preview_row":lambda _:None,
            "_cloudif_wait_health":do_not_mutate,"db_exec":do_not_mutate})
        code,body=op(None,"status")
        self.assertEqual(code,200)
        self.assertFalse(body["configured"])
        self.assertFalse(body["healthy"])
        self.assertFalse(body["continuous"])
        self.assertTrue(body["nativeRuntimeRequired"])
        self.assertFalse(body["applicationE2EVerified"])

    def test_other_project_status_remains_compatible(self):
        row={"public_number":1002,"container":"cloudif-p1002-w1-preview-web",
             "stack_id":"valid-stack","stack_name":"generic-stage",
             "git_sync_status":"synced","environment_revision":2}
        op=load_latest("cloudif_preview_request", {
            "_cloudif_pub_auth":lambda _:True,
            "_cloudif_pub_json":lambda _:{"project":"silvipro","public_number":1002},
            "safe_slug":str,"send":lambda _h,code,body:(code,body),
            "_cloudif_v144_ensure_schema":lambda:None,
            "_cloudif_preview_row":lambda _:row,
            "_cloudif_wait_health":lambda *args:{"ok":True},
            "db_exec":do_not_mutate})
        code,body=op(None,"status")
        self.assertEqual(code,200)
        self.assertTrue(body["healthy"])
        self.assertTrue(body["continuous"])
        self.assertNotIn("nativeRuntimeRequired",body)
        self.assertNotIn("legacyContainerHealthy",body)

    def test_sync_does_not_restart_paperclip_on_checkout_change(self):
        op = load_latest("_cloudif_v144_preview_sync_once", {
            "_cloudif_v144_ensure_schema": lambda: None,
            "db_query": lambda _q: [{"project": "paperclip",
                  "container": "cloudif-p1025-w1-preview-web",
                  "workspace_path": "/etc/komodo/stacks/cloudif-paperclip", "stack_id": "existing"}],
            "safe_slug": str, "normalize_resource_id": str,
            "_cloudif_preview_git_sync": do_not_mutate,
            "_cloudif_wait_health": do_not_mutate, "db_exec": do_not_mutate})
        self.assertIsNone(op())

    def test_sync_does_not_disable_other_project_processing(self):
        op = load_latest("_cloudif_v144_preview_sync_once", {
            "_cloudif_v144_ensure_schema": lambda: None,
            "db_query": lambda _q: [{"project": "outro", "container": "web",
                                     "workspace_path": "/repo/outro", "stack_id": "existing"}],
            "safe_slug": str, "normalize_resource_id": str,
            "_cloudif_preview_git_sync": do_not_mutate,
            "_cloudif_wait_health": do_not_mutate, "db_exec": do_not_mutate,
            "now": lambda: "2026-11-18T02:45:00Z"})
        with self.assertRaisesRegex(AssertionError, "state mutation"):
            op()

if __name__ == "__main__":
    main()
