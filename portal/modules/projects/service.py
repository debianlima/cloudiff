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
from portal.core.project_visibility import (
    is_admin_groups as _is_admin,
    norm as _norm,
    tenant_visible as _tenant_visible,
    visible_projects as _core_visible_projects,
)


def visible_projects(identity) -> list[dict]:
    return _core_visible_projects(identity, _DB)


def projects_data(identity) -> dict:
    from portal.core.security import csrf_token
    projs = visible_projects(identity)
    return {
        "username": identity.username,
        "is_admin": _is_admin(list(identity.groups)),
        "count": len(projs),
        "projects": projs,
        "csrf": csrf_token(identity),
        "tenant_opts": _tenant_options(identity),
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


def project_action(identity, slug: str, op: str, fields: dict | None = None) -> dict:
    """check/sync/edit_save — mesma lógica da v1 (forja-client + UPDATE + log)."""
    fields = fields or {}
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
            con.execute(
                "UPDATE projects SET name=?, description=?, repo_url=?, "
                "komodo_status=?, updated_at=? WHERE slug=?",
                (fields.get("name"), fields.get("description"), fields.get("repo_url"),
                 fields.get("komodo_status"), _now_iso(), slug))
            _log_action(con, identity.username, "project_edit_save", slug, 0, "Projeto atualizado.", "")
            con.commit()
            return {"ok": True, "op": op, "slug": slug, "redirect": "/cloudiff/portal?tab=projetos"}
        return {"ok": False, "error": "op_desconhecida", "op": op}
    finally:
        con.close()


import re as _re

def _slugify(s: str) -> str:
    s = _norm(s)
    s = _re.sub(r"[^a-z0-9._-]+", "-", s)
    s = s.strip(".-_")
    return s[:63] or "projeto"


def create_project(identity, name: str, tenant: str, description: str) -> dict:
    """Cria o REGISTRO do projeto (fiel a v1: nao provisiona infra aqui).

    Reproduz /action/create_project da v1: valida tenant_visible, insere em
    projects (upsert por slug) e concede project_acl ao dono. O provisionamento
    pesado (repo/stack) e outro fluxo, disparado depois.
    """
    tenant = (tenant or "").strip()
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "nome_obrigatorio"}
    slug = _slugify(name)
    groups = list(identity.groups)
    group_set = {_norm(g) for g in groups}
    is_admin = _is_admin(groups)
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    try:
        if tenant and not _tenant_visible(con, tenant, identity.username, group_set, is_admin):
            return {"ok": False, "error": "sem_permissao_no_tenant", "status": 403}
        con.execute(
            "INSERT INTO projects(slug,name,tenant,owner,description,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
            "name=excluded.name, tenant=excluded.tenant, description=excluded.description, "
            "updated_at=excluded.updated_at",
            (slug, name, tenant, identity.username, description, _now_iso(), _now_iso()))
        con.execute("INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)",
                    (slug, "user", identity.username))
        _log_action(con, identity.username, "create_project", slug, 0, f"tenant={tenant}", "")
        con.commit()
        return {"ok": True, "slug": slug, "redirect": "/cloudiff/portal?tab=projetos"}
    finally:
        con.close()


# --- Tenants visíveis (para o formulário de criar projeto) -----------------

import csv as _csv

_BASE = os.environ.get("CLOUDIF_BASE", "/srv/cloudif")


def _tenants_registry() -> list[dict]:
    path = os.path.join(_BASE, "registry", "tenants.csv")
    rows = []
    try:
        with open(path, errors="ignore") as f:
            for r in _csv.DictReader(f):
                if r.get("tenant"):
                    rows.append(r)
    except Exception:
        pass
    return rows


def visible_tenants(identity) -> list[str]:
    groups = list(identity.groups)
    group_set = {_norm(g) for g in groups}
    is_admin = _is_admin(groups)
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    try:
        out = []
        for t in _tenants_registry():
            name = t.get("tenant") or ""
            if name and _tenant_visible(con, name, identity.username, group_set, is_admin):
                out.append(name)
        return out
    finally:
        con.close()


def _tenant_options(identity) -> str:
    import html as _html
    allow_git_only = os.environ.get("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", "1") not in ("0", "false", "False")
    opts = ""
    if allow_git_only:
        opts += '<option value="">Sem banco: somente Git/Komodo</option>'
    for name in visible_tenants(identity):
        e = _html.escape(name, quote=True)
        opts += f'<option value="{e}">{e}</option>'
    return opts
