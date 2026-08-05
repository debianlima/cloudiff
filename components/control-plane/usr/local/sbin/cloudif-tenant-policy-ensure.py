#!/usr/bin/env python3
"""Apply and verify the initial availability policy of a newly-created tenant."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--hours", type=int, required=True)
    parser.add_argument("--portal-db", default="/var/lib/cloudif/portal/cloudif-portal.db")
    args = parser.parse_args()

    tenant = args.tenant.strip().lower()
    if not TENANT_RE.fullmatch(tenant):
        raise SystemExit("invalid_tenant")
    if not 1 <= args.hours <= 24:
        raise SystemExit("invalid_hours")

    db_path = Path(args.portal_db)
    if not db_path.is_file():
        raise SystemExit("portal_db_not_found")

    now = dt.datetime.now(dt.timezone.utc)
    until = now + dt.timedelta(hours=args.hours)
    now_text = now.isoformat(timespec="seconds")
    until_text = until.isoformat(timespec="seconds")

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(
            """CREATE TABLE IF NOT EXISTS tenant_policy(
                 tenant TEXT PRIMARY KEY,
                 always_alive INTEGER DEFAULT 0,
                 keepalive_until TEXT,
                 max_hours INTEGER DEFAULT 6,
                 updated_at TEXT
               )"""
        )
        con.execute(
            """INSERT INTO tenant_policy(
                 tenant,always_alive,keepalive_until,max_hours,updated_at
               ) VALUES(?,?,?,?,?)
               ON CONFLICT(tenant) DO UPDATE SET
                 always_alive=excluded.always_alive,
                 keepalive_until=excluded.keepalive_until,
                 max_hours=excluded.max_hours,
                 updated_at=excluded.updated_at""",
            (tenant, 0, until_text, args.hours, now_text),
        )
        con.commit()
        row = con.execute(
            "SELECT tenant,always_alive,keepalive_until,max_hours,updated_at "
            "FROM tenant_policy WHERE tenant=?",
            (tenant,),
        ).fetchone()
    finally:
        con.close()

    if not row:
        raise SystemExit("policy_not_persisted")
    result = dict(row)
    verified = (
        result["tenant"] == tenant
        and int(result["always_alive"] or 0) == 0
        and int(result["max_hours"] or 0) == args.hours
        and str(result["keepalive_until"] or "") == until_text
    )
    if not verified:
        raise SystemExit("policy_verification_failed")

    print(json.dumps({
        "ok": True,
        "tenant": tenant,
        "mode": "timed",
        "hours": args.hours,
        "keepalive_until": until_text,
        "verified": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
