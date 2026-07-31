#!/usr/bin/env bash
set -Eeuo pipefail

DB="/var/lib/cloudif/portal/cloudif-portal.db"
JOBDIR="/srv/cloudif/jobs"
mkdir -p "$JOBDIR"

python3 - <<'PY'
import json
import sqlite3
import time
from pathlib import Path

DB="/var/lib/cloudif/portal/cloudif-portal.db"
JOBDIR=Path("/srv/cloudif/jobs")

con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row

cols=[r[1] for r in con.execute("PRAGMA table_info(projects)")]

def pick(names):
    low={c.lower():c for c in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return ""

slug_col=pick(["slug","project_slug"])
name_col=pick(["name","title"])
desc_col=pick(["description","descr","summary"])
tenant_col=pick(["tenant","tenant_slug","db_tenant"])

if not slug_col:
    raise SystemExit("Tabela projects sem coluna slug.")

rows=con.execute("SELECT * FROM projects ORDER BY 1").fetchall()
con.close()

for r in rows:
    d=dict(r)
    slug=d.get(slug_col) or ""
    if not slug:
        continue

    job={
        "action":"reprovision_project",
        "slug":slug,
        "name":d.get(name_col) if name_col else slug,
        "description":d.get(desc_col) if desc_col else "",
        "tenant":d.get(tenant_col) if tenant_col else "",
        "db_mode":"link" if (tenant_col and d.get(tenant_col)) else "skip",
        "create_repo":"1",
        "setup_komodo":"1",
        "user":{"username":"system-requeue","email":"","groups":["CloudIF-Tenants-Admin"]},
        "created_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    f=JOBDIR / f"project-provision-{int(time.time())}-{slug}.json"
    f.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f)
PY
