"""health module — business/data layer. No HTML, no permission decisions.

Reads the same sources as the v1: the reconcile/transactions monitor and the
repair agent. Every function returns plain data; views render it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepairItem:
    project: str
    name: str
    tenant: str
    healthy: bool
    state: str
    issues: tuple[str, ...] = ()


def summarize_repairs(items: list[dict]) -> dict[str, int]:
    """Aggregate repair-dashboard items into the ok/warn/bad/total summary."""
    total = len(items)
    ok = sum(1 for i in items if i.get("healthy") is True)
    bad = sum(1 for i in items if i.get("state") in {"unlinked", "unknown"})
    warn = total - ok - bad
    return {"ok": ok, "warn": max(0, warn), "bad": bad, "total": total}


def score(summary: dict[str, int]) -> int:
    total = summary.get("total", 0)
    if not total:
        return 0
    return round(100 * summary.get("ok", 0) / total)
