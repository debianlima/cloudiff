from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from portal.core.auth import Identity
from portal.core import academic_tracking as tracking


class AcademicTrackingCoreTests(unittest.TestCase):
    def test_summary_counts_only_project_members_as_active(self):
        now=datetime.now(timezone.utc).isoformat()
        identity=Identity("prof","prof@example.invalid",frozenset({"CloudIF-Professor"}))
        audit=[
            {"ts":now,"actor":"alice","source":"mcp","action":"workspace.validate"},
            {"ts":now,"actor":"service-bot","source":"mcp","action":"tools/list"},
            {"ts":now,"actor":"alice","source":"project-access","action":"environment.view"},
        ]
        forgejo=[{"ts":now,"actor":"alice","source":"forgejo","action":"push"}]
        taiga={
            "ok":True,
            "counts":{"tasks":4,"tasks_closed":2,"userstories":3,"userstories_closed":1,"members":2},
            "members":[
                {"username":"alice","last_login":now,"last_activity":now},
                {"username":"bob","last_login":"","last_activity":""},
            ],
            "timeline":[{"ts":now,"actor":"alice","type":"change"}],
        }
        production={'ok':True,'instrumented':True,'published':True,'public_requests':15,'public_unique_visitors':4}
        with mock.patch.object(tracking,"_audit_events",return_value=(audit,True)), mock.patch.object(tracking,"_forgejo_events",return_value=(forgejo,True)), mock.patch.object(tracking,"_taiga_summary",return_value=(taiga,True)), mock.patch.object(tracking,"project_production_access",return_value=production):
            summary=tracking.project_tracking_summary(identity,{"slug":"alpha","name":"Alpha","status":"active"})
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["members"],2)
        self.assertEqual(summary["active_7d"],1)
        self.assertEqual(summary["without_activity_7d"],1)
        self.assertEqual(summary["tasks_open"],2)
        self.assertEqual(summary["stories_open"],2)
        self.assertEqual(summary["channels_14d"],{"taiga":1,"forgejo":1,"mcp":2,"environment":1})
        self.assertEqual(summary["events_14d"],5)
        self.assertEqual(summary["last_activity"],now)
        self.assertTrue(summary["coverage"]["production_access"])
        self.assertEqual(summary["production"]["public_requests"],15)
        self.assertFalse(summary["coverage"]["external_authenticated_access"])

    def test_student_queries_are_subject_scoped(self):
        identity=Identity("alice","alice@example.invalid",frozenset({"CloudIF-Aluno"}))
        old=tracking._AUDIT_TOKEN
        try:
            tracking._AUDIT_TOKEN="token"
            with mock.patch.object(tracking,"_http_json",return_value=(200,{"ok":True,"events":[]})) as http:
                tracking._audit_events(identity,"alpha")
            url=http.call_args.args[0]
            self.assertIn("subject=alice",url)
        finally:
            tracking._AUDIT_TOKEN=old


if __name__ == "__main__":
    unittest.main()
