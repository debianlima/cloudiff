"""Read project/tenant ownership without coupling to one portal DB schema."""
from __future__ import annotations

from collections import OrderedDict
import sqlite3


def load_resource_ownership(db_path: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return deterministic project and tenant owners across compatible schemas."""
    projects: dict[str, str] = {}
    tenant_candidates: dict[str, list[str]] = {}
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        tables = {row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        if "projects" in tables:
            for row in con.execute("SELECT * FROM projects"):
                keys = set(row.keys())
                slug = str(row["slug"] or "").strip() if "slug" in keys else ""
                owner = str(
                    (row["owner"] if "owner" in keys else "")
                    or (row["created_by"] if "created_by" in keys else "")
                    or ""
                ).strip()
                tenant = str(row["tenant"] or "").strip() if "tenant" in keys else ""
                if slug and owner:
                    projects[slug] = owner
                    if tenant:
                        tenant_candidates.setdefault(tenant, []).append(owner)

        if "project_tenants" in tables:
            for row in con.execute("SELECT * FROM project_tenants"):
                keys = set(row.keys())
                project = next(
                    (
                        str(row[key] or "").strip()
                        for key in ("project", "project_slug", "slug")
                        if key in keys and row[key]
                    ),
                    "",
                )
                tenant = str(row["tenant"] or "").strip() if "tenant" in keys else ""
                owner = projects.get(project, "")
                if owner and tenant:
                    tenant_candidates.setdefault(tenant, []).append(owner)

        if "tenant_acl" in tables:
            for row in con.execute("SELECT * FROM tenant_acl"):
                keys = set(row.keys())
                if "subject_type" not in keys or str(row["subject_type"] or "") != "user":
                    continue
                tenant = str(row["tenant"] or "").strip() if "tenant" in keys else ""
                subject = str(row["subject"] or "").strip() if "subject" in keys else ""
                if tenant and subject:
                    tenant_candidates.setdefault(tenant, []).append(subject)
    except (OSError, sqlite3.Error):
        return projects, {}
    finally:
        if con is not None:
            con.close()

    tenants: dict[str, str] = {}
    for tenant, candidates in tenant_candidates.items():
        unique = list(OrderedDict.fromkeys(item for item in candidates if item))
        if unique:
            tenants[tenant] = unique[0]
    return projects, tenants
