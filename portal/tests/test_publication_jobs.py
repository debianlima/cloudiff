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


    def test_alias_failure_does_not_reserve_name(self):
        user = {"username": "alice", "groups": [], "admin": False}
        con = sqlite3.connect(self.db)
        publications._ensure_schema(con)
        con.execute("insert into project_publications(project_slug,public_number,deploy_number,stable_hostname,version_hostname,status,is_active,created_by,created_at) values(?,?,?,?,?,?,?,?,?)",('demo',1001,1,'1001.cloudiff.duckdns.org','1001-d1.cloudiff.duckdns.org','published',1,'alice','2026-01-01T00:00:00Z'))
        con.commit();con.close()
        with (
            patch.object(publications, '_clients', return_value=('http://runtime','token','publisher')),
            patch.object(publications, '_post', return_value=(422, {'ok': False, 'error': 'cert_failed'})),
        ):
            with self.assertRaises(RuntimeError):
                publications.set_alias('demo','lima',user)
        con = sqlite3.connect(self.db)
        row = con.execute('select alias from project_publication_aliases where project_slug=?',('demo',)).fetchone()
        con.close()
        self.assertIsNone(row)

if __name__ == "__main__":
    unittest.main()
