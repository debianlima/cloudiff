#!/usr/bin/env python3
"""Build the Portal identity cache from Authentik's read-only API projection.

AD/Samba remains canonical.  This database is derived discovery data only and
never grants project access; project_acl remains the authorization source.
"""
import datetime as dt
import json
import os
import sqlite3
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

API = os.environ.get("AUTHENTIK_API_URL", "http://10.62.91.2:9000").rstrip("/")
CACHE = Path(os.environ.get("CLOUDIF_DIRECTORY_CACHE", "/var/lib/cloudif/portal/directory-cache.db"))
TOKEN_FILE = Path(os.environ.get("CREDENTIALS_DIRECTORY", "/run/credentials/cloudif-directory-cache-sync.service")) / "authentik_token"
PAGE_SIZE = min(max(int(os.environ.get("CLOUDIF_DIRECTORY_PAGE_SIZE", "100")), 20), 500)
ADMIN_GROUP = os.environ.get("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin")
PROFESSOR_GROUP = os.environ.get("CLOUDIF_PROFESSOR_GROUP", "CloudIF-Professor")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def api_get(path, token):
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.load(res)


def all_results(path, token):
    page = 1
    out = []
    while True:
        sep = "&" if "?" in path else "?"
        payload = api_get(path + sep + urllib.parse.urlencode({"page": page, "page_size": PAGE_SIZE}), token)
        out.extend(payload.get("results") or [])
        pagination = payload.get("pagination") or {}
        count = int(pagination.get("count") or len(out))
        total_pages = int(pagination.get("total_pages") or max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE))
        if page >= total_pages:
            break
        page += 1
        if page > 10000:
            raise RuntimeError("pagination safety limit exceeded")
    return out


def group_names(user):
    names = []
    for item in user.get("groups_obj") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            names.append(name)
    return sorted(set(names), key=str.lower)


def build_database(path, users, groups):
    con = sqlite3.connect(path)
    con.executescript("""
    PRAGMA journal_mode=DELETE;
    PRAGMA synchronous=FULL;
    CREATE TABLE identities(
      kind TEXT NOT NULL CHECK(kind IN ('user','group')),
      principal TEXT NOT NULL,
      display_name TEXT NOT NULL,
      email TEXT NOT NULL DEFAULT '',
      stable_subject TEXT NOT NULL DEFAULT '',
      groups_json TEXT NOT NULL DEFAULT '[]',
      is_admin INTEGER NOT NULL DEFAULT 0,
      is_professor INTEGER NOT NULL DEFAULT 0,
      active INTEGER NOT NULL DEFAULT 1,
      source TEXT NOT NULL,
      search_text TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(kind, principal)
    );
    CREATE INDEX idx_directory_kind_active ON identities(kind, active);
    CREATE INDEX idx_directory_search ON identities(search_text);
    CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    stamp = now_iso()
    user_count = 0
    admin_count = 0
    professor_count = 0
    for user in users:
        typ = str(user.get("type") or "").lower()
        if typ in {"service_account", "internal_service_account"}:
            continue
        principal = str(user.get("username") or "").strip()
        if not principal:
            continue
        groups_list = group_names(user)
        admin = int(ADMIN_GROUP in groups_list)
        professor = int(PROFESSOR_GROUP in groups_list)
        active = int(bool(user.get("is_active", True)))
        display = str(user.get("name") or principal).strip() or principal
        email = str(user.get("email") or "").strip()
        subject = str(user.get("uid") or user.get("uuid") or "").strip()
        search_text = " ".join((principal, display, email, " ".join(groups_list))).lower()
        con.execute(
            "INSERT INTO identities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("user", principal, display, email, subject, json.dumps(groups_list, ensure_ascii=False), admin,
             professor, active, "authentik-cache", search_text, stamp),
        )
        user_count += 1
        admin_count += admin
        professor_count += professor
    group_count = 0
    for group in groups:
        principal = str(group.get("name") or "").strip()
        if not principal:
            continue
        search_text = principal.lower()
        con.execute(
            "INSERT OR REPLACE INTO identities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("group", principal, principal, "", str(group.get("pk") or ""), "[]", 0, 0, 1,
             "authentik-cache", search_text, stamp),
        )
        group_count += 1
    meta = {
        "schema_version": "1",
        "synced_at": stamp,
        "source": "authentik",
        "users": str(user_count),
        "groups": str(group_count),
        "admins": str(admin_count),
        "professors": str(professor_count),
    }
    con.executemany("INSERT INTO metadata(key,value) VALUES(?,?)", meta.items())
    con.commit()
    integrity = con.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        con.close()
        raise RuntimeError("directory cache integrity_check failed")
    con.close()
    return meta


def main():
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("empty Authentik credential")
    users = all_results("/api/v3/core/users/", token)
    groups = all_results("/api/v3/core/groups/", token)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    gid = CACHE.parent.stat().st_gid
    fd, tmpname = tempfile.mkstemp(prefix="directory-cache.", suffix=".db", dir=str(CACHE.parent))
    os.close(fd)
    tmp = Path(tmpname)
    try:
        meta = build_database(tmp, users, groups)
        os.chmod(tmp, 0o640)
        os.chown(tmp, 0, gid)
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(tmp, CACHE)
        dirfd = os.open(CACHE.parent, os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        print("DIRECTORY_CACHE_SYNC=PASS users={users} groups={groups} admins={admins} professors={professors} synced_at={synced_at}".format(**meta))
    finally:
        if tmp.exists():
            tmp.unlink()


if __name__ == "__main__":
    main()
