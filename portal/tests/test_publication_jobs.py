import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portal.legacy import cloudif_portal_publications as publications


class PublicationJobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "portal.db"
        con = sqlite3.connect(self.db)
        con.executescript("""
        create table projects(slug text primary key, owner text, created_by text, status text, komodo_status text, updated_at text);
        create table project_acl(slug text, subject_type text, subject text);
        insert into projects(slug,owner,created_by) values('demo','alice','alice');
        """)
        con.commit(); con.close()
        self.old_db = publications.DB
        publications.DB = self.db

    def tearDown(self):
        publications.DB = self.old_db
        self.tmp.cleanup()

    def test_enqueue_is_fast_and_idempotent_while_pending(self):
        user = {"username": "alice", "groups": [], "admin": False}
        first = publications.enqueue_publish("demo", user)
        second = publications.enqueue_publish("demo", user)
        self.assertTrue(first["queued"])
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertTrue(second["existing"])

    def test_alias_is_unique_and_validated(self):
        user = {"username": "alice", "groups": [], "admin": False}
        result = publications.set_alias("demo", "lima", user)
        self.assertEqual(result["hostname"], "lima.cloudiff.duckdns.org")
        with self.assertRaises(ValueError):
            publications.set_alias("demo", "API", user)

    def test_claim_moves_job_to_running(self):
        user = {"username": "alice", "groups": [], "admin": False}
        publications.enqueue_publish("demo", user)
        job = publications.claim_next_job()
        self.assertEqual(job["status"], "running")
        latest = publications.latest_job("demo")
        self.assertEqual(latest["step"], "preparing")


if __name__ == "__main__":
    unittest.main()
