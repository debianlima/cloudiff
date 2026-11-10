import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "components/control-plane/srv/cloudif/lib/cloudif_ad_directory_module.py"
ACL_UI = ROOT / "components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py"
PORTAL = ROOT / "components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py"
SYNC = ROOT / "components/control-plane/usr/local/sbin/cloudif-directory-cache-sync.py"
SERVICE = ROOT / "components/control-plane/etc/systemd/system/cloudif-directory-cache-sync.service"


def load_directory(cache_path):
    os.environ["CLOUDIF_DIRECTORY_CACHE"] = str(cache_path)
    spec = importlib.util.spec_from_file_location("cloudif_ad_directory_module_test", DIRECTORY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_sync_module():
    spec = importlib.util.spec_from_file_location("cloudif_directory_cache_sync_test", SYNC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seed_cache(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE identities(kind TEXT,principal TEXT,display_name TEXT,email TEXT,stable_subject TEXT,
      groups_json TEXT,is_admin INTEGER,is_professor INTEGER,active INTEGER,source TEXT,search_text TEXT,
      updated_at TEXT,PRIMARY KEY(kind,principal));
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    """)
    rows = [
        ("user","iff3546365","IFF Admin","iff3546365@if.edu","uid-admin",'["CloudIF-Professor", "CloudIF-Tenants-Admin"]',1,1,1,"authentik-cache","iff3546365 iff admin cloudif-professor cloudif-tenants-admin","2026-11-10T20:00:00+00:00"),
        ("user","iff20222920038","Pedro Henrique","pedro@example.test","uid-user","[]",0,0,1,"authentik-cache","iff20222920038 pedro henrique pedro@example.test","2026-11-10T20:00:00+00:00"),
        ("group","CloudIF-Professor","CloudIF-Professor","","gid-prof","[]",0,0,1,"authentik-cache","cloudif-professor","2026-11-10T20:00:00+00:00"),
    ]
    con.executemany("INSERT INTO identities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO metadata VALUES(?,?)", [
        ("schema_version","1"),("synced_at","2026-11-10T20:00:00+00:00"),("source","authentik"),
        ("users","2"),("groups","1"),("admins","1"),("professors","1"),
    ])
    con.commit(); con.close()



class DirectoryCacheContractTest(unittest.TestCase):
    def test_cache_lists_without_query_and_highlights_admin(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "directory.db"
            seed_cache(db)
            mod = load_directory(db)
            payload = mod.search("", "all", user={}, page=1, page_size=50)
            assert payload["ok"] is True
            assert payload["total"] == 3
            admin = next(x for x in payload["items"] if x["principal"] == "iff3546365")
            assert admin["admin"] is True
            assert admin["professor"] is True
            assert "CloudIF-Tenants-Admin" in admin["groups"]

    def test_cache_search_and_pagination_are_local(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "directory.db"
            seed_cache(db)
            mod = load_directory(db)
            payload = mod.search("Pedro", "user", user={}, page=1, page_size=1)
            assert payload["count"] == 1
            assert payload["items"][0]["principal"] == "iff20222920038"
            assert payload["items"][0]["source"] == "authentik-cache"


    def test_sync_paginates_and_excludes_service_accounts(self):
        mod = load_sync_module()
        mod.PAGE_SIZE = 2
        pages = {
            1: {"results": [{"username":"iff3546365","name":"Admin","email":"","uid":"u1","is_active":True,"type":"external","groups_obj":[{"name":"CloudIF-Professor"},{"name":"CloudIF-Tenants-Admin"}]},{"username":"svc","name":"Svc","email":"","uid":"u2","is_active":True,"type":"service_account","groups_obj":[]}], "pagination":{"count":3,"total_pages":2}},
            2: {"results": [{"username":"iff20222920038","name":"Pedro","email":"p@example.test","uid":"u3","is_active":True,"type":"external","groups_obj":[]}], "pagination":{"count":3,"total_pages":2}},
        }
        def fake_get(path, token):
            import urllib.parse
            page = int(urllib.parse.parse_qs(urllib.parse.urlparse(path).query)["page"][0])
            return pages[page]
        mod.api_get = fake_get
        users = mod.all_results("/api/v3/core/users/", "not-a-real-token")
        self.assertEqual(len(users), 3)
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "cache.db"
            meta = mod.build_database(db, users, [{"name":"CloudIF-Professor","pk":"g1"}])
            self.assertEqual(meta["users"], "2")
            self.assertEqual(meta["admins"], "1")
            self.assertEqual(meta["professors"], "1")
            con = sqlite3.connect(db)
            principals = {r[0] for r in con.execute("select principal from identities where kind='user'")}
            con.close()
            self.assertEqual(principals, {"iff3546365", "iff20222920038"})

    def test_ui_and_sync_contract_are_explicit(self):
        ui = ACL_UI.read_text()
        portal = PORTAL.read_text()
        sync = SYNC.read_text()
        service = SERVICE.read_text()
        assert "Selecionar usuário ou grupo" in ui
        assert "Administrador CloudIFF" in ui
        assert "Carregar mais" in ui
        assert "Atualizar lista" in ui
        assert "action/directory-cache-sync" in portal
        assert "_prod_csrf_equal" in portal
        assert "INSERT INTO project_acl" not in sync
        assert "UPDATE project_acl" not in sync
        assert "DELETE FROM project_acl" not in sync
        assert "LoadCredentialEncrypted=authentik_token:" in service
        assert (ROOT / "deploy/setup_directory_cache_auth.sh").is_file()
        assert "CloudIF-Tenants-Admin" in sync
        assert "service_account" in sync


if __name__ == "__main__":
    unittest.main()
