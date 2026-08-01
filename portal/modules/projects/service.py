"""projects.service — visibilidade de projetos por usuário (fiel à v1).

Reproduz user_visible_projects/tenant_visible do monólito: admin vê tudo; os
demais veem por owner, project_acl (user/group) e tenant_visible (tenant==user
ou tenant_acl). Leitura pura do banco, sem efeitos colaterais. É aqui que a
decisão de acesso é reproduzida — a borda apenas exige autenticação.
"""
from __future__ import annotations

import os
import sqlite3

_DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
_ADMIN_GROUPS = {g.strip().lower() for g in
                 os.environ.get("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin").split(",") if g.strip()}


def _norm(s) -> str:
    return (s or "").strip().lower()


def _is_admin(groups) -> bool:
    cur = {_norm(g) for g in groups}
    return bool(_ADMIN_GROUPS & cur) or "domain admins" in cur


def _tenant_visible(con, tenant, username, group_set, is_admin) -> bool:
    if is_admin:
        return True
    if _norm(tenant) == _norm(username):
        return True
    rows = con.execute("SELECT subject_type, subject FROM tenant_acl WHERE tenant=?", (tenant,)).fetchall()
    for r in rows:
        if r["subject_type"] == "user" and _norm(r["subject"]) == _norm(username):
            return True
        if r["subject_type"] == "group" and _norm(r["subject"]) in group_set:
            return True
    return False


def visible_projects(identity) -> list[dict]:
    username = _norm(identity.username)
    groups = list(identity.groups)
    group_set = {_norm(g) for g in groups}
    is_admin = _is_admin(groups)
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM projects ORDER BY updated_at DESC, name").fetchall()
        if is_admin:
            return [_shape(r) for r in rows]
        out = []
        for p in rows:
            if _norm(p["owner"]) == username:
                out.append(_shape(p)); continue
            ok = False
            acl = con.execute("SELECT subject_type, subject FROM project_acl WHERE slug=?", (p["slug"],)).fetchall()
            for a in acl:
                if a["subject_type"] == "user" and _norm(a["subject"]) == username:
                    ok = True
                if a["subject_type"] == "group" and _norm(a["subject"]) in group_set:
                    ok = True
            if ok or (p["tenant"] and _tenant_visible(con, p["tenant"], username, group_set, is_admin)):
                out.append(_shape(p))
        return out
    finally:
        con.close()


def _shape(r) -> dict:
    keys = ("slug", "name", "tenant", "owner", "description", "repo_url",
            "komodo_status", "status", "updated_at", "repo_name", "stack_name")
    return {k: (r[k] if k in r.keys() else None) for k in keys}


def projects_data(identity) -> dict:
    projs = visible_projects(identity)
    return {
        "username": identity.username,
        "is_admin": _is_admin(list(identity.groups)),
        "count": len(projs),
        "projects": projs,
    }


# --- Ações de escrita (portadas fiéis à v1) -------------------------------

import subprocess as _sp
import datetime as _dt

_FORJA_CLIENT = "/srv/cloudif/bin/cloudif-forja-client.py"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd, timeout=120):
    try:
        r = _sp.run(cmd, text=True, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 999, "", str(e)


def _log_action(con, actor, action, target, rc, out, err):
    con.execute(
        "INSERT INTO action_log(ts,actor,action,target,rc,stdout,stderr) VALUES(?,?,?,?,?,?,?)",
        (_now_iso(), actor, action, target, rc, (out or "")[-8000:], (err or "")[-8000:]),
    )


def project_action(identity, slug: str, op: str) -> dict:
    """check/sync/edit_save — mesma lógica da v1 (forja-client + UPDATE + log)."""
    con = sqlite3.connect(_DB)
    try:
        if op in ("sync", "check"):
            rc, out, err = _run(["bash", "-lc", f"{_FORJA_CLIENT} status"], 30)
            con.execute("UPDATE projects SET komodo_status=?, updated_at=? WHERE slug=?",
                        ("checked" if rc == 0 else "erro", _now_iso(), slug))
            _log_action(con, identity.username, f"project_{op}", slug, rc, out, err)
            con.commit()
            return {"ok": rc == 0, "op": op, "slug": slug, "redirect": "/cloudiff/portal?tab=git"}
        if op == "edit_save":
            return {"ok": False, "error": "edit_save_nao_portado", "slug": slug}
        return {"ok": False, "error": "op_desconhecida", "op": op}
    finally:
        con.close()
