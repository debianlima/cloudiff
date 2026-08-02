"""Read-only data for the academic overview."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from portal.core.rbac import is_global

_DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")


def _fmt_bytes(n) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return "-"


def _role_text(identity) -> str:
    groups = {g.lower() for g in identity.groups}
    if "cloudif-tenants-admin" in groups:
        return "administrar a plataforma e acompanhar a comunidade acadêmica"
    if "cloudif-professor" in groups:
        return "acompanhar seus projetos e orientar as atividades acadêmicas"
    return "organizar seus projetos, sites e bancos de dados"


def _age_seconds(value: str | None) -> int | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - stamp).total_seconds()))
    except (TypeError, ValueError):
        return None


def server_metrics() -> dict:
    nodes, total_mem, used_mem, total_disk, used_disk = [], 0, 0, 0, 0
    try:
        con = sqlite3.connect(_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT node, ok, payload, updated_at FROM node_metrics_cache ORDER BY node"
        ).fetchall()
        con.close()
    except Exception:
        rows = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            payload = {}
        mem = payload.get("memory", {}) or {}
        disk = payload.get("disk_root", {}) or {}
        total_memory, used_memory = mem.get("total") or 0, mem.get("used") or 0
        total_storage, used_storage = disk.get("size") or 0, disk.get("used") or 0
        age = _age_seconds(row["updated_at"])
        healthy_payload = payload.get("ok") is True and total_memory > 0 and total_storage > 0
        online = bool(row["ok"]) and healthy_payload and age is not None and age <= 900
        total_mem += total_memory
        used_mem += used_memory
        total_disk += total_storage
        used_disk += used_storage
        nodes.append({
            "node": row["node"], "online": online, "stale": age is None or age > 900,
            "error": str(payload.get("error") or ""), "updated_at": row["updated_at"],
            "mem_used": used_memory, "mem_total": total_memory,
            "mem_pct": round(100 * used_memory / total_memory) if total_memory else 0,
            "disk_used": used_storage, "disk_total": total_storage,
            "disk_pct": round(100 * used_storage / total_storage) if total_storage else 0,
        })
    return {
        "nodes": nodes,
        "online_count": sum(1 for node in nodes if node["online"]),
        "node_count": len(nodes),
        "agg_mem": f"{_fmt_bytes(used_mem)} / {_fmt_bytes(total_mem)}",
        "agg_disk": f"{_fmt_bytes(used_disk)} / {_fmt_bytes(total_disk)}",
        "fmt": _fmt_bytes,
    }


def _visible_projects(con: sqlite3.Connection, username: str) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT DISTINCT p.*
        FROM projects p
        LEFT JOIN project_acl a ON a.slug=p.slug
        WHERE lower(coalesce(p.owner,''))=lower(?)
           OR (a.subject_type='user' AND lower(a.subject)=lower(?))
        ORDER BY lower(coalesce(p.name,p.slug)), p.slug
        """, (username, username)
    ).fetchall()


def academic_resources(identity) -> dict:
    projects, sites, tenants = [], [], {}
    other_sites = other_databases = 0
    try:
        con = sqlite3.connect(_DB)
        con.row_factory = sqlite3.Row
        projects = _visible_projects(con, identity.username)
        slugs = [row["slug"] for row in projects]
        if slugs:
            marks = ",".join("?" for _ in slugs)
            sites = [dict(row) for row in con.execute(
                f"""SELECT pp.project_slug, pp.stable_hostname, pp.version_hostname,
                           pp.status, pp.published_at, p.name, p.owner
                    FROM project_publications pp JOIN projects p ON p.slug=pp.project_slug
                    WHERE pp.is_active=1 AND pp.project_slug IN ({marks})
                    ORDER BY lower(coalesce(p.name,p.slug))""", slugs
            )]
        for project in projects:
            tenant = (project["tenant"] or "").strip()
            if tenant:
                item = tenants.setdefault(tenant, {"tenant": tenant, "projects": [], "primary": False})
                item["projects"].append(project["slug"])
        if slugs:
            marks = ",".join("?" for _ in slugs)
            for row in con.execute(
                f"SELECT project, tenant, is_primary FROM project_tenants WHERE project IN ({marks})", slugs
            ):
                tenant = (row["tenant"] or "").strip()
                if not tenant:
                    continue
                item = tenants.setdefault(tenant, {"tenant": tenant, "projects": [], "primary": False})
                if row["project"] not in item["projects"]:
                    item["projects"].append(row["project"])
                item["primary"] = item["primary"] or bool(row["is_primary"])
        for row in con.execute(
            "SELECT tenant FROM tenant_acl WHERE subject_type='user' AND lower(subject)=lower(?)",
            (identity.username,),
        ):
            tenant = (row["tenant"] or "").strip()
            if tenant:
                tenants.setdefault(tenant, {"tenant": tenant, "projects": [], "primary": False})
        if is_global(identity):
            other_sites = con.execute(
                "SELECT count(*) FROM project_publications WHERE is_active=1 AND project_slug NOT IN "
                "(SELECT slug FROM projects WHERE lower(coalesce(owner,''))=lower(?))",
                (identity.username,),
            ).fetchone()[0]
            own_tenants = set(tenants)
            all_tenants = {(row[0] or "").strip() for row in con.execute(
                "SELECT DISTINCT tenant FROM projects WHERE coalesce(tenant,'')<>''"
            )}
            all_tenants.update((row[0] or "").strip() for row in con.execute(
                "SELECT DISTINCT tenant FROM project_tenants WHERE coalesce(tenant,'')<>''"
            ))
            other_databases = len({tenant for tenant in all_tenants if tenant and tenant not in own_tenants})
        con.close()
    except Exception:
        pass
    return {
        "projects": [dict(row) for row in projects],
        "sites": sites,
        "databases": sorted(tenants.values(), key=lambda item: item["tenant"].lower()),
        "can_view_others": is_global(identity),
        "other_sites": other_sites,
        "other_databases": other_databases,
    }


def aggregate_servers(nodes: list[dict]) -> dict:
    return {
        "ram_used": sum(float(node.get("ram_used") or 0) for node in nodes),
        "ram_total": sum(float(node.get("ram_total") or 0) for node in nodes),
        "disk_used": sum(float(node.get("disk_used") or 0) for node in nodes),
        "disk_total": sum(float(node.get("disk_total") or 0) for node in nodes),
        "online": sum(1 for node in nodes if node.get("online") is True),
        "count": len(nodes),
    }


def overview_data(identity) -> dict:
    return {
        "username": identity.username,
        "email": identity.email,
        "role_text": _role_text(identity),
        "metrics": server_metrics(),
        "resources": academic_resources(identity),
    }
