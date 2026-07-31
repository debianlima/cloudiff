#!/usr/bin/env python3
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
from pathlib import Path

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")

ADMIN_GROUP_DEFAULTS = {
    "cloudif-tenants-admin",
    "cloudif-admin",
    "domain admins",
}

MANAGE_ROLES = {
    "owner",
    "dono",
    "proprietario",
    "proprietário",
    "admin",
    "administrator",
    "editor",
    "manage",
    "manager",
}

def _db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=20000")
    return con

def _rows(sql, params=()):
    try:
        con = _db()
        out = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close()
        return out
    except Exception:
        return []

def _tables():
    return [r["name"] for r in _rows("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

def _cols(table):
    try:
        con = _db()
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
        con.close()
        return cols
    except Exception:
        return []

def _pick(cols, candidates):
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in low:
            return low[cand.lower()]
    return ""

def _setting_value(key, default=""):
    for table in ["settings", "portal_settings", "cloudif_settings", "config"]:
        if table not in _tables():
            continue

        cols = _cols(table)
        kcol = _pick(cols, ["key", "name", "setting", "k"])
        vcol = _pick(cols, ["value", "val", "v"])

        if not kcol or not vcol:
            continue

        rows = _rows(f"SELECT {vcol} AS value FROM {table} WHERE {kcol}=? LIMIT 1", (key,))
        if rows and rows[0].get("value") not in [None, ""]:
            return str(rows[0].get("value"))

    return os.environ.get(key, default)

def _setting_list(key, default=""):
    raw = _setting_value(key, default)
    return [x.strip() for x in str(raw).replace("|", ",").split(",") if x.strip()]

def parse_groups(raw):
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or "").replace("|", ",").split(",") if x.strip()]

def user_from_headers(headers):
    groups = parse_groups(headers.get("X-authentik-groups") or headers.get("X-Authentik-Groups") or "")
    username = (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-Forwarded-User")
        or ""
    ).strip().lower()
    email = (
        headers.get("X-authentik-email")
        or headers.get("X-Authentik-Email")
        or ""
    ).strip().lower()

    return {
        "username": username,
        "email": email,
        "groups": groups,
        "admin": is_admin(groups),
    }

def is_admin(groups):
    configured = {x.lower() for x in _setting_list("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin")}
    current = {x.lower() for x in groups}
    return bool((configured | ADMIN_GROUP_DEFAULTS) & current)

def project_row(slug):
    if "projects" not in _tables():
        return {}

    cols = _cols("projects")
    slug_col = _pick(cols, ["slug", "project_slug", "name"])
    if not slug_col:
        return {}

    rows = _rows(f"SELECT * FROM projects WHERE {slug_col}=? LIMIT 1", (slug,))
    return rows[0] if rows else {}

def project_owner(slug):
    row = project_row(slug)
    if not row:
        return ""

    for col in ["owner", "owner_username", "created_by", "creator", "username", "user", "email", "dono"]:
        for key in row:
            if key.lower() == col.lower() and row.get(key):
                return str(row.get(key)).strip().lower()

    return ""

def project_acl_table():
    tables = _tables()
    candidates = []

    for table in tables:
        cols = _cols(table)
        low_table = table.lower()

        project_col = _pick(cols, ["project_slug", "slug", "project", "project_id", "project_name"])
        subject_col = _pick(cols, ["subject", "principal", "member", "identity", "username", "user", "email", "group", "group_name"])
        type_col = _pick(cols, ["subject_type", "principal_type", "member_type", "identity_type", "type", "kind"])
        role_col = _pick(cols, ["role", "permission", "level", "access", "perfil"])

        score = 0
        if any(k in low_table for k in ["acl", "permission", "permiss", "member", "access"]):
            score += 2
        if project_col:
            score += 2
        if subject_col:
            score += 2
        if type_col:
            score += 1
        if role_col:
            score += 1

        if score >= 4:
            candidates.append({
                "score": score,
                "table": table,
                "project_col": project_col,
                "subject_col": subject_col,
                "type_col": type_col,
                "role_col": role_col,
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0] if candidates else {}

def can_manage_project(user, slug):
    if user.get("admin"):
        return True

    username = (user.get("username") or "").strip().lower()
    email = (user.get("email") or "").strip().lower()
    groups = {g.lower() for g in parse_groups(user.get("groups") or [])}

    if not username or not slug:
        return False

    owner = project_owner(slug)
    if owner and owner in {username, email}:
        return True

    cfg = project_acl_table()
    if not cfg:
        return False

    table = cfg["table"]
    pcol = cfg["project_col"]
    scol = cfg["subject_col"]
    tcol = cfg.get("type_col")
    rcol = cfg.get("role_col")

    rows = _rows(f"SELECT * FROM {table} WHERE {pcol}=?", (slug,))

    for r in rows:
        subject = str(r.get(scol) or "").strip().lower()
        stype = str(r.get(tcol) or "").strip().lower() if tcol else ""
        role = str(r.get(rcol) or "access").strip().lower() if rcol else "access"

        match_user = subject in {username, email}
        match_group = subject in groups

        # Se a tabela não tem role, não concede gerenciamento por ACL simples.
        if not rcol:
            continue

        if role not in MANAGE_ROLES:
            continue

        if stype == "user" and match_user:
            return True
        if stype == "group" and match_group:
            return True
        if not stype and (match_user or match_group):
            return True

    return False

def _run(cmd, timeout=18):
    try:
        p = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return 999, "", str(e)

def _normalize_name(raw):
    s = str(raw or "").strip()
    if not s:
        return ""

    # Remove domínio quando vier DOMINIO\\usuario.
    if "\\" in s:
        s = s.split("\\")[-1].strip()

    # Remove campos de passwd/group.
    if ":" in s:
        s = s.split(":")[0].strip()

    # Remove tabs/campos extras.
    s = s.split("\t")[0].strip()

    return s

def _parse_lines(out, principal_type, source):
    items = []

    for line in (out or "").splitlines():
        name = _normalize_name(line)

        if not name:
            continue
        if len(name) > 120:
            continue
        if name.lower().startswith(("warning", "error", "failed", "usage")):
            continue
        if not re.search(r"[A-Za-z0-9_.@ -]", name):
            continue

        items.append({
            "type": principal_type,
            "principal": name,
            "label": name,
            "source": source,
        })

    return items

def _dedup(items):
    out = []
    seen = set()

    for item in items:
        key = (item.get("type", ""), item.get("principal", "").lower())
        if not item.get("principal"):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out

def _filter(items, q):
    ql = str(q or "").strip().lower()
    if not ql:
        return []

    return [
        x for x in items
        if ql in str(x.get("principal", "")).lower()
        or ql in str(x.get("label", "")).lower()
    ]

def _custom_command_results(q, stype):
    items = []

    if stype in ["all", "user"]:
        cmd_tpl = _setting_value("CLOUDIF_AD_SEARCH_USER_CMD", "")
        if cmd_tpl:
            cmd = cmd_tpl.format(q=shlex.quote(q), raw_q=q)
            rc, out, err = _run(["bash", "-lc", cmd])
            if rc == 0 and out:
                items.extend(_parse_lines(out, "user", "custom_user_cmd"))

    if stype in ["all", "group"]:
        cmd_tpl = _setting_value("CLOUDIF_AD_SEARCH_GROUP_CMD", "")
        if cmd_tpl:
            cmd = cmd_tpl.format(q=shlex.quote(q), raw_q=q)
            rc, out, err = _run(["bash", "-lc", cmd])
            if rc == 0 and out:
                items.extend(_parse_lines(out, "group", "custom_group_cmd"))

    return items

def _wbinfo_results(stype):
    items = []

    if not shutil.which("wbinfo"):
        return items

    if stype in ["all", "user"]:
        for cmd in [["wbinfo", "-u"], ["wbinfo", "--domain-users"]]:
            rc, out, err = _run(cmd)
            if rc == 0 and out:
                items.extend(_parse_lines(out, "user", "wbinfo"))
                break

    if stype in ["all", "group"]:
        for cmd in [["wbinfo", "-g"], ["wbinfo", "--domain-groups"]]:
            rc, out, err = _run(cmd)
            if rc == 0 and out:
                items.extend(_parse_lines(out, "group", "wbinfo"))
                break

    return items

def _samba_tool_results(stype):
    items = []

    if not shutil.which("samba-tool"):
        return items

    if stype in ["all", "user"]:
        rc, out, err = _run(["samba-tool", "user", "list"])
        if rc == 0 and out:
            items.extend(_parse_lines(out, "user", "samba-tool"))

    if stype in ["all", "group"]:
        rc, out, err = _run(["samba-tool", "group", "list"])
        if rc == 0 and out:
            items.extend(_parse_lines(out, "group", "samba-tool"))

    return items

def _getent_results(stype):
    items = []

    if not shutil.which("getent"):
        return items

    if stype in ["all", "user"]:
        rc, out, err = _run(["getent", "passwd"])
        if rc == 0 and out:
            items.extend(_parse_lines(out, "user", "getent-passwd"))

    if stype in ["all", "group"]:
        rc, out, err = _run(["getent", "group"])
        if rc == 0 and out:
            items.extend(_parse_lines(out, "group", "getent-group"))

    return items

def _ldapsearch_results(q, stype):
    items = []

    if not shutil.which("ldapsearch"):
        return items

    uri = _setting_value("CLOUDIF_LDAP_URI", os.environ.get("CLOUDIF_LDAP_URI", ""))
    base = _setting_value("CLOUDIF_LDAP_BASE_DN", os.environ.get("CLOUDIF_LDAP_BASE_DN", ""))
    bind = _setting_value("CLOUDIF_LDAP_BIND_DN", os.environ.get("CLOUDIF_LDAP_BIND_DN", ""))
    password = _setting_value("CLOUDIF_LDAP_BIND_PASSWORD", os.environ.get("CLOUDIF_LDAP_BIND_PASSWORD", ""))

    if not uri or not base:
        return items

    filters = []

    if stype in ["all", "user"]:
        filters.append(("user", f"(&(objectClass=user)(|(sAMAccountName=*{q}*)(cn=*{q}*)(mail=*{q}*)))"))

    if stype in ["all", "group"]:
        filters.append(("group", f"(&(objectClass=group)(|(sAMAccountName=*{q}*)(cn=*{q}*)))"))

    for principal_type, filt in filters:
        cmd = ["ldapsearch", "-LLL", "-x", "-H", uri, "-b", base, filt, "sAMAccountName", "cn", "mail"]

        if bind and password:
            cmd[3:3] = ["-D", bind, "-w", password]

        rc, out, err = _run(cmd)
        if rc != 0 or not out:
            continue

        current = {}

        for line in out.splitlines():
            line = line.strip()

            if not line:
                name = current.get("sAMAccountName") or current.get("cn") or current.get("mail")
                if name:
                    items.append({
                        "type": principal_type,
                        "principal": name,
                        "label": name,
                        "source": "ldapsearch",
                    })
                current = {}
                continue

            if ":" in line:
                k, v = line.split(":", 1)
                current[k.strip()] = v.strip()

        if current:
            name = current.get("sAMAccountName") or current.get("cn") or current.get("mail")
            if name:
                items.append({
                    "type": principal_type,
                    "principal": name,
                    "label": name,
                    "source": "ldapsearch",
                })

    return items

def _header_group_results(user, stype):
    items = []

    if stype not in ["all", "group"]:
        return items

    for g in parse_groups(user.get("groups") or []):
        items.append({
            "type": "group",
            "principal": g,
            "label": g,
            "source": "authentik-header",
        })

    return items

def search_ad(q, stype="all", user=None, diagnostics=False):
    q = str(q or "").strip()
    stype = str(stype or "all").strip().lower()

    if stype not in ["all", "user", "group"]:
        stype = "all"

    if len(q) < 2:
        return {
            "ok": True,
            "items": [],
            "diagnostics": {"reason": "query too short"} if diagnostics else {},
        }

    user = user or {}

    diag = {
        "commands": {
            "wbinfo": bool(shutil.which("wbinfo")),
            "samba-tool": bool(shutil.which("samba-tool")),
            "getent": bool(shutil.which("getent")),
            "ldapsearch": bool(shutil.which("ldapsearch")),
        },
        "sources_used": [],
    }

    all_items = []

    for source_name, func in [
        ("custom", lambda: _custom_command_results(q, stype)),
        ("wbinfo", lambda: _wbinfo_results(stype)),
        ("samba-tool", lambda: _samba_tool_results(stype)),
        ("getent", lambda: _getent_results(stype)),
        ("ldapsearch", lambda: _ldapsearch_results(q, stype)),
        ("authentik-header", lambda: _header_group_results(user, stype)),
    ]:
        try:
            found = func()
        except Exception as e:
            diag[source_name + "_error"] = str(e)
            found = []

        if found:
            diag["sources_used"].append(source_name)
            all_items.extend(found)

    all_items = _dedup(all_items)
    filtered = _filter(all_items, q)

    # Relevância: CloudIF/grupos primeiro, depois usuários.
    filtered.sort(key=lambda x: (
        0 if "cloudif" in x.get("principal", "").lower() else 1,
        0 if x.get("type") == "group" else 1,
        x.get("principal", "").lower(),
    ))

    payload = {
        "ok": True,
        "query": q,
        "type": stype,
        "count": len(filtered[:80]),
        "items": filtered[:80],
    }

    if diagnostics:
        diag["total_before_filter"] = len(all_items)
        diag["total_after_filter"] = len(filtered)
        payload["diagnostics"] = diag

    return payload

# CloudIF central RBAC integration
try:
    import cloudif_rbac as _central_rbac
    def can_manage_project(user, slug):
        return _central_rbac.authorize(user, "project.manage", project=slug)
except Exception:
    pass
