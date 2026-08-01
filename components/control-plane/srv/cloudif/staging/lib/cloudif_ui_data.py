#!/usr/bin/env python3
import os
import sqlite3
import urllib.parse
from pathlib import Path

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
PUBLIC_HOST = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")

def db_rows(sql, params=()):
    try:
        con = sqlite3.connect(DB, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=15000")
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close()
        return rows
    except Exception:
        return []

def discover_projects():
    queries = [
        "SELECT slug, name, tenant, repo_url, komodo_status FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, title AS name, tenant, repo_url, komodo_status FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, name, tenant, repo_url FROM projects ORDER BY slug LIMIT 100",
        "SELECT slug, name FROM projects ORDER BY slug LIMIT 100",
    ]
    for q in queries:
        rows = db_rows(q)
        if rows:
            integrations = {r.get("project"): r for r in db_rows("SELECT project, komodo_stack_id, komodo_stack_name, server_name FROM project_integrations")}
            for row in rows:
                extra = integrations.get(row.get("slug")) or {}
                row.update({k: v for k, v in extra.items() if v not in (None, "")})
            return rows
    return []

def discover_tenants():
    queries = [
        "SELECT tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY tenant",
        "SELECT name AS tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY name",
        "SELECT slug AS tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY slug",
    ]
    for q in queries:
        rows = db_rows(q)
        if rows:
            return rows

    base = Path("/srv/cloudif/tenants")
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir():
                out.append({
                    "tenant": d.name,
                    "kong_http_port": "",
                    "always_alive": "",
                    "enabled": "",
                })
    return out

def public_studio_url(tenant):
    tenant = tenant or ""
    return f"https://{tenant}.{PUBLIC_HOST}/project/default"

def deploy_url(project, tenant):
    return (
        "/cloudiff/portal/deploy/"
        + "?project=" + urllib.parse.quote(project or "")
        + "&tenant=" + urllib.parse.quote(tenant or "")
    )

def tab_url(tab, **params):
    q = {"tab": tab}
    q.update({k: v for k, v in params.items() if v is not None and v != ""})
    return "/cloudiff/portal/?" + urllib.parse.urlencode(q)

def project_counts():
    projects = discover_projects()
    tenants = discover_tenants()
    return {
        "projects": len(projects),
        "tenants": len(tenants),
        "projects_with_db": sum(1 for p in projects if p.get("tenant")),
        "projects_with_git": sum(1 for p in projects if p.get("repo_url")),
        "projects_with_deploy": sum(1 for p in projects if p.get("komodo_status") or p.get("repo_url")),
    }



# CloudIF v71 — helpers técnicos para Informações de Hardware

def safe_file_exists(path):
    try:
        return Path(path).exists()
    except Exception:
        return False

def technical_inventory():
    projects = discover_projects()
    tenants = discover_tenants()

    files = {
        "portal_service": "/etc/systemd/system/cloudif-admin-portal.service",
        "deploy_service": "/etc/systemd/system/cloudif-deploy-panel.service",
        "portal_script": "/usr/local/sbin/cloudif-admin-portal.py",
        "deploy_script": "/usr/local/sbin/cloudif-deploy-panel.py",
        "router_conf": "/srv/cloudif/router/conf.d/default.conf",
        "portal_db": DB,
        "project_integrate": "/srv/cloudif/bin/cloudif-project-integrate.sh",
        "ui_data": "/srv/cloudif/lib/cloudif_ui_data.py",
        "ui_components": "/srv/cloudif/lib/cloudif_ui_components.py",
        "ui_pages": "/srv/cloudif/lib/cloudif_ui_pages.py",
        "ui_modular": "/srv/cloudif/lib/cloudif_ui_modular.py",
        "git_komodo_module": "/srv/cloudif/lib/cloudif_git_komodo_module.py",
    }

    return {
        "projects": len(projects),
        "tenants": len(tenants),
        "projects_with_db": sum(1 for p in projects if p.get("tenant")),
        "projects_with_git": sum(1 for p in projects if p.get("repo_url")),
        "projects_with_deploy": sum(1 for p in projects if p.get("komodo_status") or p.get("repo_url")),
        "files": {k: safe_file_exists(v) for k, v in files.items()},
        "paths": files,
    }




# CloudIF v72 — métricas agregadas dos servidores/agentes

def _cloudif_metric_gb(value):
    if value is None or value == "":
        return None

    try:
        if isinstance(value, str):
            v = value.strip().upper().replace(",", ".")
            v = v.replace("GB", "").replace("G", "").strip()
            v = v.replace("MB", "").replace("M", "").strip()
            v = v.replace("%", "").strip()
            value = float(v)
        else:
            value = float(value)
    except Exception:
        return None

    # Se vier em bytes, converte para GB.
    if value > 1024 * 1024:
        return value / (1024 ** 3)

    return value

def _cloudif_metric_num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ".").replace("%", "").strip())
    except Exception:
        return default

def _cloudif_dig(data, *paths):
    for path in paths:
        cur = data
        ok = True

        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break

        if ok and cur not in [None, ""]:
            return cur

    return None

def _cloudif_metric_records(obj):
    if isinstance(obj, list):
        return obj

    if not isinstance(obj, dict):
        return []

    for key in ["servers", "nodes", "agents", "machines", "hosts", "data"]:
        val = obj.get(key)

        if isinstance(val, list):
            return val

        if isinstance(val, dict):
            out = []
            for name, rec in val.items():
                if isinstance(rec, dict):
                    x = dict(rec)
                    x.setdefault("name", name)
                    out.append(x)
            return out

    # Formato: {"forja": {...}, "hospedagem": {...}}
    if obj and all(isinstance(v, dict) for v in obj.values()):
        out = []
        for name, rec in obj.items():
            x = dict(rec)
            x.setdefault("name", name)
            out.append(x)
        return out

    # Formato de um único servidor.
    if any(k in obj for k in ["hostname", "host", "name", "ram_used_gb", "disk_used_gb", "containers"]):
        return [obj]

    return []

def _cloudif_normalize_server(rec):
    if not isinstance(rec, dict):
        return None

    name = (
        rec.get("name")
        or rec.get("host")
        or rec.get("hostname")
        or rec.get("server")
        or rec.get("machine")
    )

    if not name:
        return None

    online = rec.get("online")
    status = str(rec.get("status") or ("online" if online is True else "offline" if online is False else "unknown")).lower()

    ram_used = _cloudif_metric_gb(_cloudif_dig(
        rec,
        "ram_used_gb",
        "memory_used_gb",
        "mem_used_gb",
        "ram.used_gb",
        "memory.used_gb",
        "mem.used_gb",
        "ram.used",
        "memory.used",
        "mem.used",
        "ram_used_bytes",
        "memory_used_bytes",
        "mem_used_bytes"
    ))

    ram_total = _cloudif_metric_gb(_cloudif_dig(
        rec,
        "ram_total_gb",
        "memory_total_gb",
        "mem_total_gb",
        "ram.total_gb",
        "memory.total_gb",
        "mem.total_gb",
        "ram.total",
        "memory.total",
        "mem.total",
        "ram_total_bytes",
        "memory_total_bytes",
        "mem_total_bytes"
    ))

    disk_used = _cloudif_metric_gb(_cloudif_dig(
        rec,
        "disk_used_gb",
        "storage_used_gb",
        "disk.used_gb",
        "storage.used_gb",
        "disk.used",
        "storage.used",
        "disk_used_bytes",
        "storage_used_bytes"
    ))

    disk_total = _cloudif_metric_gb(_cloudif_dig(
        rec,
        "disk_total_gb",
        "storage_total_gb",
        "disk.total_gb",
        "storage.total_gb",
        "disk.total",
        "storage.total",
        "disk_total_bytes",
        "storage_total_bytes"
    ))

    disk_percent = _cloudif_metric_num(_cloudif_dig(
        rec,
        "disk_percent",
        "disk_pct",
        "disk.percent",
        "storage.percent"
    ))

    if disk_percent is None and disk_used is not None and disk_total:
        disk_percent = round((disk_used / disk_total) * 100)

    containers = _cloudif_metric_num(_cloudif_dig(
        rec,
        "containers",
        "container_count",
        "docker_containers",
        "docker.containers",
        "containers_total"
    ), 0)

    updated_at = (
        rec.get("updated_at")
        or rec.get("updated")
        or rec.get("time")
        or rec.get("timestamp")
        or rec.get("collected_at")
        or ""
    )

    return {
        "name": str(name),
        "status": status,
        "ram_used_gb": ram_used,
        "ram_total_gb": ram_total,
        "disk_used_gb": disk_used,
        "disk_total_gb": disk_total,
        "disk_percent": disk_percent,
        "containers": int(containers or 0),
        "updated_at": str(updated_at),
    }

def _cloudif_metric_sources():
    import glob
    import os

    sources = []

    env_path = os.environ.get("CLOUDIF_AGENTS_METRICS_JSON")
    if env_path:
        sources.append(env_path)

    sources.extend([
        "/var/lib/cloudif/portal/cloudif-server-metrics.json",
        "/var/lib/cloudif/portal/server-metrics.json",
        "/var/lib/cloudif/portal/agents-status.json",
        "/var/lib/cloudif/portal/agents.json",
        "/var/lib/cloudif/agents/status.json",
        "/var/lib/cloudif/agents/metrics.json",
        "/srv/cloudif/cache/cloudif-server-metrics.json",
        "/srv/cloudif/cache/agents-status.json",
        "/srv/cloudif/cache/agents.json",
        "/srv/cloudif/state/agents-status.json",
        "/srv/cloudif/state/server-metrics.json",
    ])

    for pattern in [
        "/var/lib/cloudif/agents/*.json",
        "/var/lib/cloudif/portal/*agent*.json",
        "/var/lib/cloudif/portal/*server*.json",
        "/srv/cloudif/cache/*agent*.json",
        "/srv/cloudif/cache/*server*.json",
        "/srv/cloudif/state/*.json",
    ]:
        sources.extend(glob.glob(pattern))

    # Preserva ordem e remove duplicados.
    out = []
    seen = set()
    for s in sources:
        if s and s not in seen and Path(s).exists():
            out.append(s)
            seen.add(s)

    return out

def server_metrics():
    import json

    selected_source = ""
    servers = []

    for source in _cloudif_metric_sources():
        try:
            raw = Path(source).read_text(errors="ignore")
            obj = json.loads(raw)
            records = _cloudif_metric_records(obj)
            normalized = []

            for rec in records:
                item = _cloudif_normalize_server(rec)
                if item:
                    normalized.append(item)

            if normalized:
                servers = normalized
                selected_source = source
                break
        except Exception:
            continue

    ram_used = sum(x["ram_used_gb"] or 0 for x in servers)
    ram_total = sum(x["ram_total_gb"] or 0 for x in servers)
    disk_used = sum(x["disk_used_gb"] or 0 for x in servers)
    disk_total = sum(x["disk_total_gb"] or 0 for x in servers)

    return {
        "source": selected_source,
        "servers": servers,
        "aggregate": {
            "ram_used_gb": ram_used,
            "ram_total_gb": ram_total,
            "disk_used_gb": disk_used,
            "disk_total_gb": disk_total,
        }
    }
