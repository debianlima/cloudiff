#!/usr/bin/env python3
import datetime, os, sqlite3, subprocess, sys

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
BASE = os.environ.get("CLOUDIF_BASE", "/srv/cloudif")

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def run(cmd, timeout=120):
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

def main():
    if not os.path.exists(DB):
        return 0
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        select tenant, always_alive, keepalive_until
        from tenant_policy
        where coalesce(always_alive,0)=0
          and keepalive_until is not null
          and keepalive_until <> ''
    """).fetchall()

    for r in rows:
        tenant = r["tenant"]
        until = r["keepalive_until"]
        try:
            dt = datetime.datetime.fromisoformat(until.replace("Z","+00:00"))
        except Exception:
            continue

        if dt > now():
            continue

        tdir = os.path.join(BASE, "tenants", tenant)
        if not os.path.isdir(tdir):
            continue

        print(f"[TTL] expirou tenant={tenant}, parando containers")
        rc = run(["bash", "-lc", f"cd {tdir!r} && docker compose --env-file .env stop"], 180)
        con.execute("""
            insert into action_log(ts, actor, action, target, rc, stdout, stderr)
            values(datetime('now'), 'ttl-janitor', 'stop-expired-tenant', ?, ?, ?, ?)
        """, (tenant, rc.returncode, rc.stdout[-4000:], rc.stderr[-4000:]))
        con.execute("update tenant_policy set keepalive_until=null where tenant=?", (tenant,))
        con.commit()
    con.close()

if __name__ == "__main__":
    raise SystemExit(main())
