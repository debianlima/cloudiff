#!/usr/bin/env python3
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
from pathlib import Path

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")

ADMIN_GROUPS_DEFAULT = {
    "cloudif-tenants-admin",
    "cloudif-admin",
    "domain admins",
}

MANAGE_ROLES = {
    "owner", "dono", "proprietario", "proprietário",
    "admin", "administrator", "editor", "manage", "manager",
    "access", "member"
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

def setting_value(key, default=""):
    env = os.environ.get(key)
    if env not in [None, ""]:
        return env

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

    return default

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
    current = {g.lower() for g in parse_groups(groups)}
    configured = {g.lower() for g in parse_groups(setting_value("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin"))}
    return bool(current & (configured | ADMIN_GROUPS_DEFAULT))

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

    for wanted in ["owner", "owner_username", "created_by", "creator", "username", "user", "email", "dono"]:
        for k, v in row.items():
            if k.lower() == wanted and v:
                return str(v).strip().lower()

    rows = _rows("SELECT subject FROM project_acl WHERE slug=? AND subject_type='user' ORDER BY id LIMIT 1", (slug,))
    if rows:
        return str(rows[0].get("subject") or "").strip().lower()

    return ""

def can_manage_project(user, slug):
    if user.get("admin"):
        return True

    username = (user.get("username") or "").strip().lower()
    email = (user.get("email") or "").strip().lower()
    groups = {g.lower() for g in parse_groups(user.get("groups"))}

    if not username or not slug:
        return False

    owner = project_owner(slug)
    if owner and owner in {username, email}:
        return True

    if "project_acl" in _tables():
        rows = _rows("SELECT subject_type, subject FROM project_acl WHERE slug=?", (slug,))
        for r in rows:
            stype = str(r.get("subject_type") or "").lower()
            subject = str(r.get("subject") or "").lower()

            if stype == "user" and subject in {username, email}:
                return True
            if stype == "group" and subject in groups:
                return True

    return False

def _run(cmd, timeout=18):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return 999, "", str(e)

def _normalize_name(raw):
    s = str(raw or "").strip()

    if not s:
        return ""

    if "\\" in s:
        s = s.split("\\")[-1].strip()

    if ":" in s:
        s = s.split(":")[0].strip()

    s = s.split("\t")[0].strip()

    if not s:
        return ""

    if s.lower().startswith(("warning", "error", "failed", "usage", "server:", "date:", "content-")):
        return ""

    if len(s) > 120:
        return ""

    return s

def _make_item(name, kind, source, extra=None):
    name = _normalize_name(name)
    if not name:
        return None

    return {
        "type": kind,
        "principal": name,
        "label": name,
        "source": source,
        **(extra or {}),
    }

def _parse_line_items(text, kind, source):
    items = []
    for line in (text or "").splitlines():
        item = _make_item(line, kind, source)
        if item:
            items.append(item)
    return items

def _dedup(items):
    out = []
    seen = set()

    for item in items:
        key = (item.get("type"), str(item.get("principal", "")).lower())
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
        or ql in str(x.get("mail", "")).lower()
        or ql in str(x.get("cn", "")).lower()
    ]

def _domain_to_base(domain):
    domain = str(domain or "").strip().strip(".").lower()
    parts = [p for p in domain.split(".") if p]
    if not parts:
        return ""
    return ",".join("DC=" + p for p in parts)

def _discover_domains(user=None):
    domains = []

    for key in ["CLOUDIF_AD_DOMAIN", "CLOUDIF_LDAP_DOMAIN", "CLOUDIF_DOMAIN", "CLOUDIF_REALM"]:
        v = setting_value(key, "")
        if v:
            domains.append(v.lower())

    try:
        krb = Path("/etc/krb5.conf").read_text(errors="ignore")
        m = re.search(r"default_realm\s*=\s*([A-Za-z0-9_.-]+)", krb, re.I)
        if m:
            domains.append(m.group(1).lower())
    except Exception:
        pass

    if user and user.get("email") and "@" in user.get("email"):
        domains.append(user["email"].split("@", 1)[1].lower())

    for cmd in [["hostname", "-d"], ["bash", "-lc", "awk '/^search /{print $2}' /etc/resolv.conf | head -n1"]]:
        rc, out, err = _run(cmd, timeout=5)
        if rc == 0 and out.strip():
            domains.append(out.strip().lower())

    clean = []
    seen = set()

    for d in domains:
        d = d.strip().strip(".").lower()
        if not d or d in seen or d == "localdomain":
            continue
        seen.add(d)
        clean.append(d)

    return clean

def _discover_ldap_uris(domains):
    uris = []

    configured = setting_value("CLOUDIF_LDAP_URI", "") or setting_value("LDAP_URI", "")
    if configured:
        uris.extend(parse_groups(configured))

    host = setting_value("CLOUDIF_AD_HOST", "") or setting_value("CLOUDIF_LDAP_HOST", "")
    if host:
        uris.append("ldap://" + host)

    for domain in domains:
        # DNS SRV via dig.
        if shutil.which("dig"):
            rc, out, err = _run(["bash", "-lc", f"dig +short SRV _ldap._tcp.{shlex.quote(domain)} 2>/dev/null"], timeout=8)
            if rc == 0 and out:
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        port = parts[2]
                        target = parts[3].rstrip(".")
                        uris.append(f"ldap://{target}:{port}")

        # DNS SRV via host.
        if shutil.which("host"):
            rc, out, err = _run(["bash", "-lc", f"host -t SRV _ldap._tcp.{shlex.quote(domain)} 2>/dev/null"], timeout=8)
            if rc == 0 and out:
                for line in out.splitlines():
                    m = re.search(r"has SRV record\s+\d+\s+\d+\s+(\d+)\s+([A-Za-z0-9_.-]+)", line)
                    if m:
                        uris.append(f"ldap://{m.group(2).rstrip('.')}:{m.group(1)}")

        uris.append("ldap://" + domain)

    out = []
    seen = set()

    for uri in uris:
        uri = uri.strip()
        if not uri or uri in seen:
            continue
        seen.add(uri)
        out.append(uri)

    return out

def _ldapsearch_one(uri, base, filt, attrs):
    if not shutil.which("ldapsearch"):
        return 127, "", "ldapsearch não instalado"

    bind_dn = setting_value("CLOUDIF_LDAP_BIND_DN", "") or setting_value("LDAP_BIND_DN", "")
    bind_pw = setting_value("CLOUDIF_LDAP_BIND_PASSWORD", "") or setting_value("LDAP_BIND_PASSWORD", "")

    attempts = []

    if bind_dn and bind_pw:
        attempts.append(["ldapsearch", "-LLL", "-x", "-H", uri, "-D", bind_dn, "-w", bind_pw, "-b", base, filt] + attrs)

    # Anonymous bind.
    attempts.append(["ldapsearch", "-LLL", "-x", "-H", uri, "-b", base, filt] + attrs)

    # Kerberos/GSSAPI, se a máquina tiver ticket/config.
    attempts.append(["ldapsearch", "-LLL", "-Y", "GSSAPI", "-H", uri, "-b", base, filt] + attrs)

    last = (999, "", "")

    for cmd in attempts:
        rc, out, err = _run(cmd, timeout=18)
        last = (rc, out, err)

        if rc == 0 and out.strip():
            return rc, out, err

    return last

def _parse_ldif(text, kind, source):
    items = []
    cur = {}

    def flush():
        if not cur:
            return
        name = cur.get("sAMAccountName") or cur.get("uid") or cur.get("cn") or cur.get("mail")
        item = _make_item(name, kind, source, {
            "cn": cur.get("cn", ""),
            "mail": cur.get("mail", ""),
        })
        if item:
            items.append(item)

    for line in (text or "").splitlines():
        line = line.rstrip()

        if not line:
            flush()
            cur = {}
            continue

        if ":" not in line:
            continue

        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()

        if k in ["sAMAccountName", "uid", "cn", "mail"]:
            cur[k] = v

    flush()
    return items

def _ldap_results(q, stype, user, diag):
    domains = _discover_domains(user)
    uris = _discover_ldap_uris(domains)
    items = []

    diag["ldap_domains"] = domains
    diag["ldap_uris"] = uris
    diag["ldap_errors"] = []

    bases = []

    configured_base = setting_value("CLOUDIF_LDAP_BASE_DN", "") or setting_value("LDAP_BASE_DN", "")
    if configured_base:
        bases.append(configured_base)

    for d in domains:
        b = _domain_to_base(d)
        if b:
            bases.append(b)

    bases = list(dict.fromkeys(bases))

    if not uris or not bases:
        diag["ldap_errors"].append("Sem CLOUDIF_LDAP_URI/CLOUDIF_LDAP_BASE_DN e sem descoberta DNS/realm suficiente.")
        return items

    safe_q = re.sub(r"[*()\\\x00]", "", q)

    filters = []
    if stype in ["all", "user"]:
        filters.append(("user", f"(&(|(objectClass=user)(objectClass=person))(|(sAMAccountName=*{safe_q}*)(uid=*{safe_q}*)(cn=*{safe_q}*)(mail=*{safe_q}*)))"))
    if stype in ["all", "group"]:
        filters.append(("group", f"(&(|(objectClass=group)(objectClass=groupOfNames)(objectClass=posixGroup))(|(sAMAccountName=*{safe_q}*)(cn=*{safe_q}*)))"))

    attrs = ["sAMAccountName", "uid", "cn", "mail"]

    for uri in uris:
        for base in bases:
            for kind, filt in filters:
                rc, out, err = _ldapsearch_one(uri, base, filt, attrs)

                if rc == 0 and out:
                    found = _parse_ldif(out, kind, "ldapsearch")
                    if found:
                        diag["ldap_success"] = {"uri": uri, "base": base}
                        items.extend(found)
                else:
                    msg = f"{uri} base={base} kind={kind} rc={rc} err={(err or '').strip()[:200]}"
                    diag["ldap_errors"].append(msg)

    return items

def _wbinfo_results(stype):
    items = []
    if not shutil.which("wbinfo"):
        return items

    if stype in ["all", "user"]:
        rc, out, err = _run(["wbinfo", "-u"])
        if rc == 0:
            items.extend(_parse_line_items(out, "user", "wbinfo"))

    if stype in ["all", "group"]:
        rc, out, err = _run(["wbinfo", "-g"])
        if rc == 0:
            items.extend(_parse_line_items(out, "group", "wbinfo"))

    return items

def _samba_tool_results(stype):
    items = []
    if not shutil.which("samba-tool"):
        return items

    if stype in ["all", "user"]:
        rc, out, err = _run(["samba-tool", "user", "list"])
        if rc == 0:
            items.extend(_parse_line_items(out, "user", "samba-tool"))

    if stype in ["all", "group"]:
        rc, out, err = _run(["samba-tool", "group", "list"])
        if rc == 0:
            items.extend(_parse_line_items(out, "group", "samba-tool"))

    return items

def _getent_results(stype):
    items = []
    if not shutil.which("getent"):
        return items

    if stype in ["all", "user"]:
        rc, out, err = _run(["getent", "passwd"])
        if rc == 0:
            items.extend(_parse_line_items(out, "user", "getent-passwd"))

    if stype in ["all", "group"]:
        rc, out, err = _run(["getent", "group"])
        if rc == 0:
            items.extend(_parse_line_items(out, "group", "getent-group"))

    return items

def _sqlite_acl_results(stype):
    items = []

    if stype in ["all", "user", "group"] and "project_acl" in _tables():
        for r in _rows("SELECT DISTINCT subject_type, subject FROM project_acl ORDER BY subject_type, subject"):
            kind = str(r.get("subject_type") or "principal")
            if stype != "all" and kind != stype:
                continue
            item = _make_item(r.get("subject"), kind, "project_acl")
            if item:
                items.append(item)

    if stype in ["all", "user", "group"] and "tenant_acl" in _tables():
        for r in _rows("SELECT DISTINCT subject_type, subject FROM tenant_acl ORDER BY subject_type, subject"):
            kind = str(r.get("subject_type") or "principal")
            if stype != "all" and kind != stype:
                continue
            item = _make_item(r.get("subject"), kind, "tenant_acl")
            if item:
                items.append(item)

    return items

def _authentik_header_results(user, stype):
    items = []

    if stype in ["all", "group"]:
        for g in parse_groups(user.get("groups")):
            item = _make_item(g, "group", "authentik-header")
            if item:
                items.append(item)

    if stype in ["all", "user"]:
        for u in [user.get("username"), user.get("email")]:
            item = _make_item(u, "user", "authentik-header")
            if item:
                items.append(item)

    return items

def search(q, stype="all", user=None, diagnostics=False):
    q = str(q or "").strip()
    stype = str(stype or "all").lower().strip()
    user = user or {}

    if stype not in ["all", "user", "group"]:
        stype = "all"

    diag = {
        "commands": {
            "wbinfo": bool(shutil.which("wbinfo")),
            "samba-tool": bool(shutil.which("samba-tool")),
            "getent": bool(shutil.which("getent")),
            "ldapsearch": bool(shutil.which("ldapsearch")),
            "dig": bool(shutil.which("dig")),
            "host": bool(shutil.which("host")),
        },
        "sources_used": [],
    }

    if len(q) < 2:
        payload = {"ok": True, "query": q, "type": stype, "count": 0, "items": []}
        if diagnostics:
            payload["diagnostics"] = {**diag, "reason": "query too short"}
        return payload

    sources = [
        ("ldapsearch", lambda: _ldap_results(q, stype, user, diag)),
        ("wbinfo", lambda: _wbinfo_results(stype)),
        ("samba-tool", lambda: _samba_tool_results(stype)),
        ("getent", lambda: _getent_results(stype)),
        ("project_acl/tenant_acl", lambda: _sqlite_acl_results(stype)),
        ("authentik-header", lambda: _authentik_header_results(user, stype)),
    ]

    items = []

    for name, fn in sources:
        try:
            found = fn()
        except Exception as e:
            diag[name + "_error"] = str(e)
            found = []

        if found:
            diag["sources_used"].append(name)
            items.extend(found)

    items = _dedup(items)
    filtered = _filter(items, q)

    filtered.sort(key=lambda x: (
        0 if x.get("source") == "ldapsearch" else 1,
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
        diag["total_before_filter"] = len(items)
        diag["total_after_filter"] = len(filtered)
        payload["diagnostics"] = diag

    return payload



# CloudIF v87 — enriquecimento de resultados para dropdown de permissões

def _v87_extract_cn_from_dn(value):
    value = str(value or "").strip()
    m = re.search(r"CN=([^,]+)", value, re.I)
    if m:
        return m.group(1).strip()
    return value

def _make_item(name, kind, source, extra=None):
    extra = extra or {}
    name = _normalize_name(name)

    if not name:
        return None

    full_name = (
        extra.get("full_name")
        or extra.get("displayName")
        or extra.get("display_name")
        or extra.get("cn")
        or name
    )

    mail = extra.get("mail") or extra.get("email") or ""

    groups = extra.get("groups") or []
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.replace("|", ",").split(",") if g.strip()]

    return {
        "type": kind,
        "principal": name,
        "username": name if kind == "user" else "",
        "label": name,
        "full_name": full_name,
        "mail": mail,
        "email": mail,
        "groups": groups,
        "source": source,
    }

def _parse_ldif(text, kind, source):
    items = []
    cur = {}

    def add_value(k, v):
        if k == "memberOf":
            cur.setdefault("memberOf", []).append(v)
        else:
            cur[k] = v

    def flush():
        if not cur:
            return

        groups = [_v87_extract_cn_from_dn(x) for x in cur.get("memberOf", []) if x]

        principal = (
            cur.get("sAMAccountName")
            or cur.get("uid")
            or cur.get("cn")
            or cur.get("mail")
        )

        item = _make_item(principal, kind, source, {
            "cn": cur.get("cn", ""),
            "full_name": cur.get("displayName") or cur.get("name") or cur.get("cn") or principal,
            "mail": cur.get("mail", ""),
            "groups": groups,
        })

        if item:
            items.append(item)

    current_key = None

    for raw in (text or "").splitlines():
        line = raw.rstrip("\n")

        if not line:
            flush()
            cur = {}
            current_key = None
            continue

        # Continuação de linha LDIF.
        if line.startswith(" ") and current_key:
            if current_key == "memberOf":
                cur.setdefault("memberOf", [])
                if cur["memberOf"]:
                    cur["memberOf"][-1] += line.strip()
            else:
                cur[current_key] = str(cur.get(current_key, "")) + line.strip()
            continue

        if ":" not in line:
            continue

        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        current_key = k

        if k in ["sAMAccountName", "uid", "cn", "name", "displayName", "mail", "memberOf"]:
            add_value(k, v)

    flush()
    return items

def _ldap_results(q, stype, user, diag):
    domains = _discover_domains(user)
    uris = _discover_ldap_uris(domains)
    items = []

    diag["ldap_domains"] = domains
    diag["ldap_uris"] = uris
    diag["ldap_errors"] = []

    bases = []

    configured_base = setting_value("CLOUDIF_LDAP_BASE_DN", "") or setting_value("LDAP_BASE_DN", "")
    if configured_base:
        bases.append(configured_base)

    for d in domains:
        b = _domain_to_base(d)
        if b:
            bases.append(b)

    bases = list(dict.fromkeys(bases))

    if not uris or not bases:
        diag["ldap_errors"].append("Sem CLOUDIF_LDAP_URI/CLOUDIF_LDAP_BASE_DN e sem descoberta DNS/realm suficiente.")
        return items

    safe_q = re.sub(r"[*()\\\x00]", "", q)

    filters = []
    if stype in ["all", "user"]:
        filters.append(("user", f"(&(|(objectClass=user)(objectClass=person))(|(sAMAccountName=*{safe_q}*)(uid=*{safe_q}*)(cn=*{safe_q}*)(mail=*{safe_q}*)(displayName=*{safe_q}*)))"))
    if stype in ["all", "group"]:
        filters.append(("group", f"(&(|(objectClass=group)(objectClass=groupOfNames)(objectClass=posixGroup))(|(sAMAccountName=*{safe_q}*)(cn=*{safe_q}*)(displayName=*{safe_q}*)))"))

    attrs = ["sAMAccountName", "uid", "cn", "name", "displayName", "mail", "memberOf"]

    for uri in uris:
        for base in bases:
            for kind, filt in filters:
                rc, out, err = _ldapsearch_one(uri, base, filt, attrs)

                if rc == 0 and out:
                    found = _parse_ldif(out, kind, "ldapsearch")
                    if found:
                        diag["ldap_success"] = {"uri": uri, "base": base}
                        items.extend(found)
                else:
                    msg = f"{uri} base={base} kind={kind} rc={rc} err={(err or '').strip()[:200]}"
                    diag["ldap_errors"].append(msg)

    return items

def _authentik_header_results(user, stype):
    items = []

    groups = parse_groups(user.get("groups"))

    if stype in ["all", "group"]:
        for g in groups:
            item = _make_item(g, "group", "authentik-header", {
                "full_name": g,
                "groups": [],
            })
            if item:
                items.append(item)

    if stype in ["all", "user"]:
        username = user.get("username") or ""
        email = user.get("email") or ""

        item = _make_item(username or email, "user", "authentik-header", {
            "full_name": username or email,
            "mail": email,
            "groups": groups,
        })
        if item:
            items.append(item)

    return items




# CloudIF v90 — busca de novos usuários/grupos SEM usar project_acl/tenant_acl
#
# Importante:
# - project_acl e tenant_acl são permissões já cadastradas.
# - Elas NÃO devem alimentar a busca de novos usuários/grupos.
# - A busca usa diretório real: tela clássica /ad-search, LDAP/Samba/getent e headers Authentik.

import re as _v90_re
import shlex as _v90_shlex
import urllib.parse as _v90_urlparse
from html.parser import HTMLParser as _v90_HTMLParser

def _sqlite_acl_results(stype):
    # Desativado de propósito no v90.
    # As tabelas project_acl/tenant_acl são usadas para listar permissões atuais,
    # não para procurar usuários/grupos novos no AD.
    return []

class _V90ADSearchHTMLParser(_v90_HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_cell = False
        self.cell = []
        self.row = []
        self.rows = []
        self.texts = []

    def handle_starttag(self, tag, attrs):
        if tag in ["td", "th"]:
            self.in_cell = True
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ["td", "th"]:
            value = " ".join("".join(self.cell).split())
            self.row.append(value)
            self.in_cell = False
            self.cell = []

        if tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []

    def handle_data(self, data):
        data = data or ""
        clean = " ".join(data.split())
        if clean:
            self.texts.append(clean)
        if self.in_cell:
            self.cell.append(data)

def _v90_classic_html_to_items(html, source="classic-ad-search"):
    parser = _V90ADSearchHTMLParser()
    try:
        parser.feed(html or "")
    except Exception:
        return []

    items = []

    # Formato clássico observado:
    # Tipo | Nome | Membros
    for row in parser.rows:
        if len(row) < 2:
            continue

        first = (row[0] or "").strip().lower()
        if first in ["tipo", "type"]:
            continue

        if first in ["user", "usuario", "usuário", "users"]:
            kind = "user"
            name = row[1].strip()
        elif first in ["group", "grupo", "groups"]:
            kind = "group"
            name = row[1].strip()
        else:
            continue

        if not name or len(name) > 120:
            continue

        groups = []
        members = row[2].strip() if len(row) >= 3 else ""

        if members and members.lower() not in ["-", "membros", "members"]:
            groups = [
                x.strip()
                for x in _v90_re.split(r"[,;|]", members)
                if x.strip() and len(x.strip()) <= 120
            ][:20]

        item = _make_item(name, kind, source, {
            "full_name": name,
            "groups": groups,
        })

        if item:
            items.append(item)

    # Fallback: linhas de texto próximas de nomes tipo iff123 ou CloudIF-...
    if not items:
        for txt in parser.texts:
            t = txt.strip()
            if not t:
                continue
            if len(t) > 80:
                continue

            lower = t.lower()
            if lower in ["resultado da busca ad", "busca", "tipo", "nome", "membros", "pesquisar"]:
                continue

            if _v90_re.match(r"^iff[0-9A-Za-z_.-]+$", t):
                item = _make_item(t, "user", source, {"full_name": t})
                if item:
                    items.append(item)

            elif t.startswith("CloudIF-"):
                item = _make_item(t, "group", source, {"full_name": t})
                if item:
                    items.append(item)

    return _dedup(items)

def _classic_ad_search_results(q, stype, user, diag):
    """
    Reaproveita a busca clássica real do portal, mas converte o HTML em itens JSON.
    Isso evita usar project_acl como fonte da busca.
    """
    q = str(q or "").strip()
    stype = str(stype or "all").strip().lower()

    if len(q) < 2:
        return []

    username = (user or {}).get("username") or ""
    email = (user or {}).get("email") or ""
    groups = "|".join(parse_groups((user or {}).get("groups") or []))

    headers = []
    if username:
        headers += ["-H", f"X-authentik-username: {username}"]
        headers += ["-H", f"X-Authentik-Username: {username}"]
        headers += ["-H", f"X-Forwarded-User: {username}"]
    if email:
        headers += ["-H", f"X-authentik-email: {email}"]
        headers += ["-H", f"X-Authentik-Email: {email}"]
    if groups:
        headers += ["-H", f"X-authentik-groups: {groups}"]
        headers += ["-H", f"X-Authentik-Groups: {groups}"]

    urls = [
        "http://127.0.0.1:18094/ad-search?" + _v90_urlparse.urlencode({"q": q, "type": stype}),
        "http://127.0.0.1:18094/cloudiff/portal/ad-search?" + _v90_urlparse.urlencode({"q": q, "type": stype}),
    ]

    all_items = []
    errors = []

    for url in urls:
        cmd = ["curl", "-sS", "-i", "--max-time", "12"]
        for i in range(0, len(headers), 2):
            cmd += [headers[i], headers[i+1]]
        cmd.append(url)

        rc, out, err = _run(cmd, timeout=15)

        if rc != 0:
            errors.append(f"{url}: rc={rc} err={err[:160]}")
            continue

        header, body = "", out

        if "\r\n\r\n" in out:
            header, body = out.split("\r\n\r\n", 1)
        elif "\n\n" in out:
            header, body = out.split("\n\n", 1)

        if "403 Forbidden" in header or "Restrito a admin" in body:
            errors.append(f"{url}: 403/restrito")
            continue

        if "Resultado da busca AD" not in body and "<table" not in body:
            errors.append(f"{url}: resposta não parece resultado AD clássico")
            continue

        found = _v90_classic_html_to_items(body, "classic-ad-search")

        if found:
            all_items.extend(found)
            diag.setdefault("classic_ad_search_success", []).append(url)

    if errors:
        diag["classic_ad_search_errors"] = errors[:10]

    return _dedup(all_items)

def search(q, stype="all", user=None, diagnostics=False):
    q = str(q or "").strip()
    stype = str(stype or "all").lower().strip()
    user = user or {}

    if stype not in ["all", "user", "group"]:
        stype = "all"

    diag = {
        "commands": {
            "wbinfo": bool(shutil.which("wbinfo")),
            "samba-tool": bool(shutil.which("samba-tool")),
            "getent": bool(shutil.which("getent")),
            "ldapsearch": bool(shutil.which("ldapsearch")),
            "dig": bool(shutil.which("dig")),
            "host": bool(shutil.which("host")),
        },
        "sources_used": [],
        "sqlite_acl_disabled_for_search": True,
        "note": "project_acl/tenant_acl são ignorados na busca; usados apenas para listar permissões atuais."
    }

    if len(q) < 2:
        payload = {"ok": True, "query": q, "type": stype, "count": 0, "items": []}
        if diagnostics:
            payload["diagnostics"] = {**diag, "reason": "query too short"}
        return payload

    sources = [
        ("classic-ad-search", lambda: _classic_ad_search_results(q, stype, user, diag)),
        ("ldapsearch", lambda: _ldap_results(q, stype, user, diag)),
        ("wbinfo", lambda: _wbinfo_results(stype)),
        ("samba-tool", lambda: _samba_tool_results(stype)),
        ("getent", lambda: _getent_results(stype)),
        ("authentik-header", lambda: _authentik_header_results(user, stype)),
    ]

    items = []

    for name, fn in sources:
        try:
            found = fn()
        except Exception as e:
            diag[name + "_error"] = str(e)
            found = []

        if found:
            diag["sources_used"].append(name)
            items.extend(found)

    items = _dedup(items)
    filtered = _filter(items, q)

    filtered.sort(key=lambda x: (
        0 if x.get("source") == "classic-ad-search" else 1,
        0 if x.get("source") == "ldapsearch" else 1,
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
        diag["total_before_filter"] = len(items)
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
