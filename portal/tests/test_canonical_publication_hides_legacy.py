import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "components/control-plane/current-apps/portal-current/cloudif_ui_publications.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("cloudif_ui_publications_current", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CanonicalPublicationHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "portal.db"
        con = sqlite3.connect(self.db)
        con.executescript(
            """
            create table production_releases(
              project_slug text,
              publication_number integer,
              candidate_number integer,
              deploy_number integer,
              status text,
              hostname text,
              stage_code text,
              is_active integer
            );
            create table publication_candidates(
              project_slug text,
              candidate_number integer,
              commit_sha text,
              runtime_diff_json text
            );
            create table project_publications(
              project_slug text,
              public_number integer,
              deploy_number integer,
              status text,
              commit_sha text,
              version_hostname text,
              is_active integer,
              detail_json text
            );
            """
        )
        con.commit()
        con.close()
        self.module = load_module()
        self.module.DB = str(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_canonical_release_hides_legacy_history(self):
        con = sqlite3.connect(self.db)
        con.execute(
            "insert into publication_candidates values(?,?,?,?)",
            ("demo", 3, "canonical-sha", "{}"),
        )
        con.execute(
            "insert into production_releases values(?,?,?,?,?,?,?,?)",
            ("demo", 3, 3, 3, "published", "demo.cloudiff.duckdns.org", "P3", 1),
        )
        con.execute(
            "insert into project_publications values(?,?,?,?,?,?,?,?)",
            ("demo", 1021, 1, "published", "legacy-sha", "1021-d1.cloudiff.duckdns.org", 0, "{}"),
        )
        con.commit()
        con.close()

        rows = self.module._rows("demo")

        self.assertEqual([row["kind"] for row in rows], ["P"])
        self.assertEqual(rows[0]["number"], 3)

    def test_legacy_history_remains_fallback_without_canonical_release(self):
        con = sqlite3.connect(self.db)
        con.execute(
            "insert into project_publications values(?,?,?,?,?,?,?,?)",
            ("demo", 1021, 1, "published", "legacy-sha", "1021-d1.cloudiff.duckdns.org", 1, "{}"),
        )
        con.commit()
        con.close()

        rows = self.module._rows("demo")

        self.assertEqual([row["kind"] for row in rows], ["D"])
        self.assertEqual(rows[0]["number"], 1)


if __name__ == "__main__":
    unittest.main()
