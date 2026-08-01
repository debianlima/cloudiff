"""overview.service — dados reais da Visão geral (lidos, sem efeitos colaterais).

Fonte das métricas: tabela node_metrics_cache do banco do portal (atualizada
pelos agentes), NÃO o arquivo cloudif-server-metrics.json (que ficava defasado).
"""
from __future__ import annotations

import json
import os
import sqlite3

_DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")


def _fmt_bytes(n) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return (f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}")
        n /= 1024
    return "-"


def _role_text(identity) -> str:
    groups = {g.lower() for g in identity.groups}
    if "cloudif-tenants-admin" in groups:
        return "administrar a plataforma"
    if "cloudif-professor" in groups:
        return "conduzir seus projetos"
    return "acompanhar seus projetos"


def server_metrics() -> dict:
    """Lê node_metrics_cache e devolve cards + agregados, no formato da v1."""
    nodes, total_mem, used_mem, total_disk, used_disk = [], 0, 0, 0, 0
    try:
        con = sqlite3.connect(_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT node, ok, payload, updated_at "
                           "FROM node_metrics_cache ORDER BY node").fetchall()
        con.close()
    except Exception:
        rows = []
    for r in rows:
        try:
            p = json.loads(r["payload"] or "{}")
        except Exception:
            p = {}
        mem = p.get("memory", {}) or {}
        disk = p.get("disk_root", {}) or {}
        tm, um = mem.get("total") or 0, mem.get("used") or 0
        td, ud = disk.get("size") or 0, disk.get("used") or 0
        total_mem += tm; used_mem += um; total_disk += td; used_disk += ud
        nodes.append({
            "node": r["node"], "online": bool(r["ok"]), "updated_at": r["updated_at"],
            "mem_used": um, "mem_total": tm,
            "mem_pct": round(100 * um / tm) if tm else 0,
            "disk_used": ud, "disk_total": td,
            "disk_pct": round(100 * ud / td) if td else 0,
            "disk_label": disk.get("pcent") or "",
        })
    return {
        "nodes": nodes,
        "agg_mem": f"{_fmt_bytes(used_mem)} / {_fmt_bytes(total_mem)}",
        "agg_disk": f"{_fmt_bytes(used_disk)} / {_fmt_bytes(total_disk)}",
        "fmt": _fmt_bytes,
    }


def overview_data(identity) -> dict:
    return {
        "username": identity.username,
        "role_text": _role_text(identity),
        "metrics": server_metrics(),
    }
