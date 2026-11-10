#!/usr/bin/env python3
"""Derived Authentik directory cache for the CloudIFF project ACL picker.

Authority remains in Authentik/AD and project_acl. This SQLite database is only
an indexed projection used to browse/select identities without synchronous LDAP
queries on every keystroke.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import json
import os
import pathlib
import sqlite3
import time
import threading
import urllib.parse
import urllib.request

CACHE_SCHEMA_VERSION = "1"
ADMIN_GROUP = "cloudif-tenants-admin"
DEFAULT_DB = "/var/lib/cloudif/portal/directory-cache.db"
DEFAULT_AUTHENTIK = "http://10.62.91.2:9000"
DEFAULT_AD_AGENT = "http://10.68.128.252:18097"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
LOCK_PATH = "/run/cloudif/portal-directory-sync.lock"


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _db_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("CLOUDIF_DIRECTORY_CACHE_DB", DEFAULT_DB))


def _connect(readonly: bool = False) -> sqlite3.Connection:
    path = _db_path()
    if readonly:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, timeout=20)
        os.chmod(path, 0o600)
    con.row_factory = sqlite3.Row
    return con


def _init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS identities(
          kind TEXT NOT NULL CHECK(kind IN ('user','group')),
          principal TEXT NOT NULL,
          subject TEXT NOT NULL DEFAULT '',
          display_name TEXT NOT NULL DEFAULT '',
          email TEXT NOT NULL DEFAULT '',
          groups_json TEXT NOT NULL DEFAULT '[]',
          source TEXT NOT NULL DEFAULT 'authentik-cache',
          active INTEGER NOT NULL DEFAULT 1,
          is_admin INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(kind, principal)
        );
        CREATE INDEX IF NOT EXISTS identities_kind_active_idx ON identities(kind, active);
        CREATE INDEX IF NOT EXISTS identities_principal_ci_idx ON identities(lower(principal));
        CREATE INDEX IF NOT EXISTS identities_display_ci_idx ON identities(lower(display_name));
        CREATE INDEX IF NOT EXISTS identities_email_ci_idx ON identities(lower(email));
        CREATE TABLE IF NOT EXISTS meta(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """
    )


def _meta(con: sqlite3.Connection) -> dict[str, str]:
    try:
        return {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM meta")}
    except sqlite3.Error:
        return {}


def _age_seconds(value: str) -> int | None:
    try:
        stamp = _dt.datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=_dt.timezone.utc)
        return max(0, int((_dt.datetime.now(_dt.timezone.utc) - stamp).total_seconds()))
    except Exception:
        return None


def status() -> dict:
    path = _db_path()
    if not path.is_file():
        return {
            "ready": False,
            "cache_exists": False,
            "path": str(path),
            "count": 0,
            "users": 0,
            "groups": 0,
            "last_sync_at": "",
            "age_seconds": None,
            "stale": True,
        }
    try:
        con = _connect(readonly=True)
        try:
            meta = _meta(con)
            users = con.execute("SELECT COUNT(*) FROM identities WHERE kind='user' AND active=1").fetchone()[0]
            groups = con.execute("SELECT COUNT(*) FROM identities WHERE kind='group' AND active=1").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error as exc:
        return {"ready": False, "cache_exists": True, "error": str(exc), "path": str(path), "stale": True}
    age = _age_seconds(meta.get("last_sync_at", ""))
    max_age = max(60, int(os.environ.get("CLOUDIF_DIRECTORY_CACHE_SYNC_SECONDS", "600") or 600) * 2)
    return {
        "ready": bool(users or groups),
        "cache_exists": True,
        "path": str(path),
        "count": users + groups,
        "users": users,
        "groups": groups,
        "last_sync_at": meta.get("last_sync_at", ""),
        "age_seconds": age,
        "stale": age is None or age > max_age,
        "source": meta.get("source", "authentik"),
        "last_duration_ms": int(meta.get("last_duration_ms", "0") or 0),
        "schema_version": meta.get("schema_version", ""),
    }


def _identity_from_row(row: sqlite3.Row) -> dict:
    try:
        groups = json.loads(row["groups_json"] or "[]")
    except Exception:
        groups = []
    return {
        "type": row["kind"],
        "principal": row["principal"],
        "username": row["principal"] if row["kind"] == "user" else "",
        "full_name": row["display_name"],
        "display_name": row["display_name"],
        "email": row["email"],
        "groups": groups if isinstance(groups, list) else [],
        "source": row["source"],
        "subject": row["subject"],
        "is_admin": bool(row["is_admin"]),
        "active": bool(row["active"]),
    }


def search(query: str = "", kind: str = "all", page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    query = str(query or "").strip()
    kind = str(kind or "all").strip().lower()
    if kind not in {"all", "user", "group"}:
        kind = "all"
    try:
        page = max(1, int(page))
    except Exception:
        page = 1
    try:
        page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
    except Exception:
        page_size = DEFAULT_PAGE_SIZE
    st = status()
    if not st.get("ready"):
        return {"ok": True, "query": query, "type": kind, "page": page, "page_size": page_size,
                "count": 0, "total": 0, "items": [], "cache": st}

    where = ["active=1"]
    params: list[object] = []
    if kind != "all":
        where.append("kind=?")
        params.append(kind)
    if query:
        pattern = f"%{query.lower()}%"
        where.append("(lower(principal) LIKE ? OR lower(display_name) LIKE ? OR lower(email) LIKE ?)")
        params.extend([pattern, pattern, pattern])
    clause = " AND ".join(where)
    con = _connect(readonly=True)
    try:
        total = int(con.execute(f"SELECT COUNT(*) FROM identities WHERE {clause}", params).fetchone()[0])
        exact = query.lower()
        offset = (page - 1) * page_size
        rows = con.execute(
            f"""
            SELECT * FROM identities WHERE {clause}
            ORDER BY CASE WHEN lower(principal)=? THEN 0 ELSE 1 END,
                     CASE WHEN kind='user' THEN 0 ELSE 1 END,
                     lower(CASE WHEN display_name='' THEN principal ELSE display_name END),
                     lower(principal)
            LIMIT ? OFFSET ?
            """,
            [*params, exact, page_size, offset],
        ).fetchall()
    finally:
        con.close()
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return {
        "ok": True,
        "query": query,
        "type": kind,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "count": len(rows),
        "total": total,
        "items": [_identity_from_row(r) for r in rows],
        "cache": st,
    }


def _json_request(url: str, token: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "cloudif-directory-cache/1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if int(response.status) != 200:
            raise RuntimeError(f"authentik_http_{response.status}")
        return json.load(response)


def _fetch_paginated(base: str, token: str, path: str, extra: dict | None = None) -> list[dict]:
    """Fetch Authentik pages sequentially with bounded retry.

    Authentik's users endpoint is substantially slower at page_size=100; a
    sequential walk is intentionally preferred over parallel fan-out to avoid
    overloading the identity provider during a cache refresh.
    """
    extra = dict(extra or {})
    page = 1
    out: list[dict] = []
    while True:
        query = urllib.parse.urlencode({"page": page, "page_size": 100, **extra})
        last_error = None
        payload = None
        for attempt in range(2):
            try:
                payload = _json_request(f"{base.rstrip('/')}{path}?{query}", token, timeout=30)
                break
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(1)
        if payload is None:
            raise last_error or RuntimeError("authentik_page_fetch_failed")
        out.extend(payload.get("results") or [])
        pagination = payload.get("pagination") or {}
        nxt = int(pagination.get("next") or 0)
        if not nxt:
            break
        page = nxt
        if page > 10000:
            raise RuntimeError("authentik_pagination_guard")
    return out


def _group_names(user: dict) -> list[str]:
    cached = user.get("_cached_group_names") or []
    if cached:
        return sorted({str(g).strip() for g in cached if str(g).strip()}, key=str.lower)
    groups = []
    for item in user.get("groups_obj") or []:
        if isinstance(item, dict) and item.get("name"):
            groups.append(str(item["name"]).strip())
    return sorted({g for g in groups if g}, key=str.lower)


def _replace_snapshot(users: list[dict], groups: list[dict], duration_ms: int) -> dict:
    now = _utcnow()
    rows = []
    for user in users:
        principal = str(user.get("username") or "").strip()
        if not principal:
            continue
        user_groups = _group_names(user)
        normalized = {g.lower() for g in user_groups}
        raw_name = user.get("name")
        display_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else principal
        raw_email = user.get("email")
        email = raw_email.strip() if isinstance(raw_email, str) else ""
        rows.append((
            "user", principal, str(user.get("uuid") or user.get("pk") or user.get("uid") or ""),
            display_name, email,
            json.dumps(user_groups, ensure_ascii=False, separators=(",", ":")), "authentik-cache",
            1 if user.get("is_active", True) else 0,
            1 if user.get("is_superuser") or ADMIN_GROUP in normalized else 0,
            now,
        ))
    for group in groups:
        principal = str(group.get("name") or "").strip()
        if not principal:
            continue
        rows.append((
            "group", principal, str(group.get("pk") or ""), principal, "", "[]", "authentik-cache", 1, 0, now,
        ))

    con = _connect(readonly=False)
    try:
        _init_schema(con)
        with con:
            con.execute("DELETE FROM identities")
            con.executemany(
                """INSERT INTO identities(kind,principal,subject,display_name,email,groups_json,source,active,is_admin,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            values = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "last_sync_at": now,
                "source": "authentik",
                "last_duration_ms": str(int(duration_ms)),
                "user_count": str(sum(1 for r in rows if r[0] == "user")),
                "group_count": str(sum(1 for r in rows if r[0] == "group")),
            }
            con.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", values.items())
    finally:
        con.close()
    return status()


def sync_from_authentik(blocking: bool = False) -> dict:
    base = os.environ.get("CLOUDIF_DIRECTORY_AUTHENTIK_URL", DEFAULT_AUTHENTIK).strip().rstrip("/")
    token = os.environ.get("CLOUDIF_DIRECTORY_AUTHENTIK_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CLOUDIF_DIRECTORY_AUTHENTIK_TOKEN ausente")
    pathlib.Path(LOCK_PATH).parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_PATH, "a+")
    try:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(lock.fileno(), flags)
        except BlockingIOError:
            return {"ok": True, "sync_in_progress": True, "cache": status()}
        start = time.monotonic()
        # Groups are few and carry direct member PKs; users are fetched without
        # expensive groups_obj expansion and enriched locally from that map.
        groups = _fetch_paginated(base, token, "/api/v3/core/groups/")
        membership: dict[str, list[str]] = {}
        for group in groups:
            name = str(group.get("name") or "").strip()
            if not name:
                continue
            for user_pk in group.get("users") or []:
                membership.setdefault(str(user_pk), []).append(name)
        users = _fetch_paginated(base, token, "/api/v3/core/users/", {"include_groups": "false"})
        for user in users:
            user["_cached_group_names"] = membership.get(str(user.get("pk")), [])
        duration_ms = int((time.monotonic() - start) * 1000)
        st = _replace_snapshot(users, groups, duration_ms)
        return {"ok": True, "sync_in_progress": False, "cache": st}
    finally:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        lock.close()


def start_sync_background() -> dict:
    """Start a best-effort refresh without tying up the Portal request."""
    before = status()
    def runner():
        try:
            sync_from_authentik(blocking=False)
        except Exception:
            # Failure is surfaced through unchanged/stale cache status and the
            # systemd timer logs; interactive requests keep serving old cache.
            pass
    thread = threading.Thread(target=runner, name="cloudif-directory-sync", daemon=True)
    thread.start()
    return {"ok": True, "sync_started": True, "cache": before}


def ad_agent_search(query: str, kind: str = "all", timeout: float = 2.5) -> list[dict]:
    query = str(query or "").strip()
    if len(query) < 2:
        return []
    kind = kind if kind in {"all", "user", "group"} else "all"
    base = os.environ.get("CLOUDIF_AD_AGENT_URL", DEFAULT_AD_AGENT).strip().rstrip("/")
    url = base + "/search?" + urllib.parse.urlencode({"q": query, "type": kind})
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "cloudif-directory-cache/1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.load(response)
    out = []
    for item in payload.get("results") or []:
        principal = str(item.get("name") or "").strip()
        ikind = str(item.get("type") or "user").strip().lower()
        if not principal or ikind not in {"user", "group"}:
            continue
        out.append({
            "type": ikind,
            "principal": principal,
            "username": principal if ikind == "user" else "",
            "full_name": principal,
            "display_name": principal,
            "email": "",
            "groups": [],
            "source": "ad-agent-live",
            "subject": "",
            "is_admin": False,
            "active": True,
        })
    return out


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["sync", "status"])
    args = parser.parse_args()
    if args.action == "sync":
        print(json.dumps(sync_from_authentik(blocking=True), ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(status(), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
