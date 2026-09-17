"""Canonical project visibility shared by Portal v2 modules.

This is the read-only equivalent of the legacy ``user_visible_projects`` rule:
admin sees all; other identities see projects they own, project ACL entries for
user/group, or projects whose tenant is visible through tenant ACL.
"""
from __future__ import annotations

import os
import sqlite3


def norm(value) -> str:
    return (value or "").strip().lower()


def admin_groups() -> set[str]:
    return {g.strip().lower() for g in os.environ.get("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin").split(",") if g.strip()}


def is_admin_groups(groups) -> bool:
    current = {norm(group) for group in groups}
    return bool(admin_groups() & current) or "domain admins" in current


def tenant_visible(con: sqlite3.Connection, tenant, username, group_set, is_admin) -> bool:
    if is_admin:
        return True
    if norm(tenant) == norm(username):
        return True
    rows = con.execute("SELECT subject_type, subject FROM tenant_acl WHERE tenant=?", (tenant,)).fetchall()
    for row in rows:
        if row["subject_type"] == "user" and norm(row["subject"]) == norm(username):
            return True
        if row["subject_type"] == "group" and norm(row["subject"]) in group_set:
            return True
    return False


def shape_project(row) -> dict:
    keys = ("slug", "name", "tenant", "owner", "description", "repo_url",
            "komodo_status", "status", "updated_at", "repo_name", "stack_name")
    return {key: (row[key] if key in row.keys() else None) for key in keys}


def visible_projects(identity, db_path: str) -> list[dict]:
    username = norm(identity.username)
    groups = list(identity.groups)
    group_set = {norm(group) for group in groups}
    is_admin = is_admin_groups(groups)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM projects ORDER BY updated_at DESC, name").fetchall()
        if is_admin:
            return [shape_project(row) for row in rows]
        out = []
        for project in rows:
            if norm(project["owner"]) == username:
                out.append(shape_project(project)); continue
            allowed = False
            acl = con.execute("SELECT subject_type, subject FROM project_acl WHERE slug=?", (project["slug"],)).fetchall()
            for entry in acl:
                if entry["subject_type"] == "user" and norm(entry["subject"]) == username:
                    allowed = True
                if entry["subject_type"] == "group" and norm(entry["subject"]) in group_set:
                    allowed = True
            if allowed or (project["tenant"] and tenant_visible(con, project["tenant"], username, group_set, is_admin)):
                out.append(shape_project(project))
        return out
    finally:
        con.close()
