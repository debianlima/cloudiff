import traceback
import shutil
import tempfile
import subprocess
import sqlite3
import base64
#!/usr/bin/env python3
import hmac
import hashlib
import json
import os
import re
import secrets
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ENVFILE = Path("/etc/cloudif/forja-agent.env")
STATE_DIR = Path("/var/lib/cloudif/forja-agent/projects")
EVENT_DIR = Path("/var/lib/cloudif/forja-agent/events")
STATE_DIR.mkdir(parents=True, exist_ok=True)
EVENT_DIR.mkdir(parents=True, exist_ok=True)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")

def read_env():
    data = {}
    if ENVFILE.exists():
        for line in ENVFILE.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    data.update({k: v for k, v in os.environ.items() if k.startswith(("FORJA_", "FORGEJO_", "KOMODO_", "CLOUDIF_"))})
    return data

CFG = read_env()
HOST = CFG.get("FORJA_AGENT_HOST", "0.0.0.0")
PORT = int(CFG.get("FORJA_AGENT_PORT", "18095"))
TOKEN = CFG.get("FORJA_AGENT_TOKEN", "")

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def clean_url(u):
    return (u or "").rstrip("/")

def bool_value(v, default=False):
    if v is None or v == "":
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "sim", "on"}

def jdump(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

def json_response(handler, code, data):
    raw = jdump(data).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(raw)

def state_path(slug):
    return STATE_DIR / f"{slug}.json"

def load_project(slug):
    p = state_path(slug)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception:
        return None

def save_project(project):
    slug = project["project_slug"]
    old = load_project(slug) or {}
    old.update(project)
    old["updated_at"] = now()
    state_path(slug).write_text(jdump(old))
    return old

def http_json(method, url, token="", payload=None, timeout=8, auth_style="forgejo"):
    headers = {
        "Accept": "application/json",
        "User-Agent": "CloudIF-Forja-Agent/4.0",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}" if auth_style == "bearer" else f"token {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body[:1000]}
            return {"ok": 200 <= r.status < 300, "status": r.status, "data": parsed}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body[:1000]}
        return {"ok": False, "status": e.code, "data": parsed}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

def forgejo_api_base():
    url = clean_url(CFG.get("FORGEJO_URL", ""))
    return url + "/api/v1" if url else ""

def forgejo_repo_name(slug):
    slug = safe_slug(slug) if "safe_slug" in globals() else re.sub(r"[^a-z0-9]+", "-", str(slug or "").lower()).strip("-")
    prefix = str(CFG.get("FORGEJO_REPO_PREFIX") or "cloudif-")
    return slug if slug.startswith(prefix) else prefix + slug

def forgejo_legacy_repo_name(slug):
    canonical = forgejo_repo_name(slug)
    prefix = str(CFG.get("FORGEJO_REPO_PREFIX") or "cloudif-")
    return prefix + canonical

def forgejo_status():
    base = forgejo_api_base()
    token = CFG.get("FORGEJO_TOKEN", "")
    if not base:
        return {"ok": False, "message": "FORGEJO_URL vazio."}
    res = http_json("GET", f"{base}/version", token=token, timeout=int(CFG.get("CLOUDIF_INTEGRATION_TIMEOUT", "8")))
    if res["ok"]:
        return {"ok": True, "message": "Forgejo API respondeu.", "data": res.get("data", {})}
    return {"ok": False, "message": f"Forgejo API falhou. Status {res.get('status')}.", "detail": res}

def komodo_status():
    url = clean_url(CFG.get("KOMODO_URL", ""))
    token = CFG.get("KOMODO_TOKEN", "")
    if not url:
        return {"ok": False, "message": "KOMODO_URL vazio."}
    last = None
    for path in ["/api/health", "/health", "/"]:
        res = http_json("GET", url + path, token=token, timeout=5, auth_style="bearer")
        last = res
        if res["ok"]:
            return {"ok": True, "message": f"Komodo respondeu em {path}.", "data": res.get("data", {})}
    return {"ok": False, "message": f"Komodo não respondeu nos endpoints testados. Último status {last.get('status') if last else '-'}."}

def ensure_forgejo_org(owner):
    base = forgejo_api_base()
    token = CFG.get("FORGEJO_TOKEN", "")
    if not owner:
        return {"ok": True, "message": "Sem owner/org."}
    check = http_json("GET", f"{base}/orgs/{urllib.parse.quote(owner)}", token=token, timeout=8)
    if check["ok"]:
        return {"ok": True, "message": "Organização já existe."}
    payload = {
        "username": owner,
        "full_name": "CloudIF",
        "description": "Projetos CloudIF",
        "visibility": "private",
    }
    res = http_json("POST", f"{base}/orgs", token=token, payload=payload, timeout=8)
    return {"ok": bool(res.get("ok")), "message": "Organização criada." if res.get("ok") else "Não foi possível criar organização.", "detail": res}

def ensure_forgejo_repo(project):
    base = forgejo_api_base()
    token = CFG.get("FORGEJO_TOKEN", "")
    if not base:
        return {"ok": False, "message": "FORGEJO_URL vazio."}
    if not token:
        return {"ok": False, "message": "FORGEJO_TOKEN vazio."}

    slug = project["project_slug"]
    owner = project.get("forgejo_owner") or project.get("owner_user") or ((project.get("access") or {}).get("owner") if isinstance(project.get("access"),dict) else "") or ""
    owner_kind = str(project.get("forgejo_owner_kind") or "user").lower()
    repo = forgejo_repo_name(slug)
    root = clean_url(CFG.get("FORGEJO_URL", ""))
    private = bool_value(CFG.get("FORGEJO_PRIVATE"), True)
    auto_init = bool_value(CFG.get("FORGEJO_AUTO_INIT"), True)

    if owner:
        if owner_kind == "user":
            user_check=http_json("GET",f"{base}/users/{urllib.parse.quote(owner)}",token=token,timeout=8)
            if not user_check.get("ok"):
                return {"ok":False,"error":"forgejo_user_not_found","owner":owner,"message":"O usuário solicitante ainda não existe no Forgejo. Faça o primeiro login e tente novamente."}
        else:
            org_result=ensure_forgejo_org(owner)
            if not org_result.get("ok"): return org_result
        check = http_json("GET", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}", token=token, timeout=8)
        if check["ok"]:
            return {"ok": True, "created": False, "owner": owner, "repo": repo, "url": f"{root}/{owner}/{repo}", "message": "Repositório já existe."}

        # Reparo automático de nomes legados com prefixo duplicado.
        legacy = forgejo_legacy_repo_name(slug)
        if legacy != repo:
            legacy_check = http_json("GET", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(legacy)}", token=token, timeout=8)
            if legacy_check.get("ok"):
                renamed = http_json("PATCH", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(legacy)}", token=token, payload={"name": repo}, timeout=20)
                if renamed.get("ok"):
                    return {"ok": True, "created": False, "repaired": True, "old_repo": legacy, "owner": owner, "repo": repo, "url": f"{root}/{owner}/{repo}", "message": "Repositório legado renomeado para o padrão canônico."}

        payload = {
            "name": repo,
            "description": project.get("description") or f"Projeto {project.get('app_name', slug)}",
            "private": private,
            "auto_init": auto_init,
            "default_branch": "main",
        }
        endpoint=f"{base}/admin/users/{urllib.parse.quote(owner)}/repos" if owner_kind=="user" else f"{base}/orgs/{urllib.parse.quote(owner)}/repos"
        res = http_json("POST", endpoint, token=token, payload=payload, timeout=10)
        if res["ok"]:
            data = res.get("data", {})
            return {"ok": True, "created": True, "owner": owner, "repo": repo, "url": data.get("html_url") or f"{root}/{owner}/{repo}", "message": "Repositório criado."}

        return {"ok": False, "message": "Falha ao criar repositório no namespace pessoal solicitado.", "owner":owner, "owner_kind":owner_kind, "detail": res}

    payload = {
        "name": repo,
        "description": project.get("description") or f"Projeto {project.get('app_name', slug)}",
        "private": private,
        "auto_init": auto_init,
        "default_branch": "main",
    }
    res = http_json("POST", f"{base}/user/repos", token=token, payload=payload, timeout=10)
    if res["ok"]:
        data = res.get("data", {})
        return {"ok": True, "created": True, "repo": data.get("full_name") or repo, "url": data.get("html_url") or "", "message": "Repositório criado no usuário do token."}
    if res.get("status") == 409:
        return {"ok": True, "created": False, "repo": repo, "message": "Repositório já existia."}
    return {"ok": False, "message": "Falha ao criar repositório.", "detail": res}


RELEASE_RE = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
MIGRATION_RE = re.compile(r"^[0-9][0-9A-Za-z_.-]*\.sql$")
RELEASE_MAX_MIGRATIONS = 200
RELEASE_MAX_BYTES = 4 * 1024 * 1024


def _release_repo_parts(slug):
    project = load_project(slug) or {}
    forgejo = project.get("forgejo") if isinstance(project.get("forgejo"), dict) else {}
    owner = forgejo.get("owner") or project.get("forgejo_owner") or CFG.get("FORGEJO_OWNER") or "cloudif"
    repo = forgejo.get("repo") or forgejo_repo_name(slug)
    if "/" in repo:
        owner_from_repo, repo = repo.split("/", 1)
        owner = owner or owner_from_repo
    return owner, repo


def _release_api(method, path, payload=None, timeout=30):
    base = forgejo_api_base()
    token = CFG.get("FORGEJO_TOKEN", "")
    if not base or not token:
        return {"ok": False, "status": 0, "error": "forgejo_not_configured", "data": {}}
    return http_json(method, base + path, token=token, payload=payload, timeout=timeout)


def _release_migrations(owner, repo, commit):
    qowner = urllib.parse.quote(owner, safe="")
    qrepo = urllib.parse.quote(repo, safe="")
    ref = urllib.parse.quote(commit, safe="")
    path = f"/repos/{qowner}/{qrepo}/contents/supabase/migrations?ref={ref}"
    listing = _release_api("GET", path, timeout=30)
    if listing.get("status") == 404:
        return {"ok": True, "items": [], "count": 0, "total_bytes": 0}
    if not listing.get("ok") or not isinstance(listing.get("data"), list):
        return {"ok": False, "error": "migration_list_failed", "detail": listing}
    candidates = [x for x in listing["data"] if isinstance(x, dict) and x.get("type") == "file" and MIGRATION_RE.fullmatch(x.get("name", ""))]
    candidates.sort(key=lambda x: x.get("name", ""))
    if len(candidates) > RELEASE_MAX_MIGRATIONS:
        return {"ok": False, "error": "too_many_migrations", "count": len(candidates)}
    items=[]; total=0
    for item in candidates:
        url = item.get("url") or ""
        if not url:
            item_path = urllib.parse.quote("supabase/migrations/" + item["name"], safe="/")
            url = forgejo_api_base() + f"/repos/{qowner}/{qrepo}/contents/{item_path}?ref={ref}"
            token = CFG.get("FORGEJO_TOKEN", "")
            res = http_json("GET", url, token=token, timeout=30)
        else:
            token = CFG.get("FORGEJO_TOKEN", "")
            sep = "&" if "?" in url else "?"
            res = http_json("GET", url + sep + "ref=" + ref, token=token, timeout=30)
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        encoded = (data.get("content") or "").replace("\n", "")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            return {"ok": False, "error": "migration_decode_failed", "name": item.get("name")}
        total += len(raw)
        if total > RELEASE_MAX_BYTES:
            return {"ok": False, "error": "migration_bundle_too_large", "total_bytes": total}
        items.append({
            "name": item["name"],
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content_b64": base64.b64encode(raw).decode(),
        })
    return {"ok": True, "items": items, "count": len(items), "total_bytes": total}


def prepare_project_release(payload):
    slug = str(payload.get("project") or payload.get("project_slug") or "").strip().lower()
    version = str(payload.get("version") or "").strip()
    commit = str(payload.get("commit") or payload.get("commit_sha") or "").strip().lower()
    dry_run = bool_value(payload.get("dry_run"), False)
    notes = str(payload.get("notes") or "")[:12000]
    if not SLUG_RE.fullmatch(slug):
        return 400, {"ok": False, "error": "invalid_project"}
    if not RELEASE_RE.fullmatch(version):
        return 400, {"ok": False, "error": "invalid_version", "expected": "vMAJOR.MINOR.PATCH[-suffix]"}
    if not COMMIT_RE.fullmatch(commit):
        return 400, {"ok": False, "error": "invalid_commit"}
    owner, repo = _release_repo_parts(slug)
    qowner = urllib.parse.quote(owner, safe="")
    qrepo = urllib.parse.quote(repo, safe="")
    qcommit = urllib.parse.quote(commit, safe="")
    check = _release_api("GET", f"/repos/{qowner}/{qrepo}/git/commits/{qcommit}", timeout=30)
    if not check.get("ok"):
        check = _release_api("GET", f"/repos/{qowner}/{qrepo}/commits/{qcommit}", timeout=30)
    if not check.get("ok"):
        return 404, {"ok": False, "error": "commit_not_found", "project": slug, "repo": f"{owner}/{repo}"}
    migrations = _release_migrations(owner, repo, commit)
    if not migrations.get("ok"):
        return 422, {"ok": False, "error": "migration_bundle_failed", "detail": migrations}
    result = {
        "ok": True,
        "dry_run": dry_run,
        "project": slug,
        "owner": owner,
        "repo": repo,
        "version": version,
        "commit": commit,
        "migrations": migrations,
    }
    if dry_run:
        return 200, result
    qversion = urllib.parse.quote(version, safe="")
    existing = _release_api("GET", f"/repos/{qowner}/{qrepo}/releases/tags/{qversion}", timeout=30)
    if existing.get("ok") and isinstance(existing.get("data"), dict):
        release = existing["data"]
        result.update({"release_id": release.get("id"), "release_url": release.get("html_url") or "", "draft": bool(release.get("draft")), "existing": True})
        return 200, result
    body = notes or f"Release {version} preparada pelo CloudIF para o commit {commit}."
    created = _release_api("POST", f"/repos/{qowner}/{qrepo}/releases", {
        "tag_name": version,
        "target_commitish": commit,
        "name": version,
        "body": body,
        "draft": True,
        "prerelease": False,
    }, timeout=45)
    if not created.get("ok") or not isinstance(created.get("data"), dict):
        return 502, {"ok": False, "error": "release_create_failed", "detail": created}
    release = created["data"]
    result.update({"release_id": release.get("id"), "release_url": release.get("html_url") or "", "draft": True, "existing": False})
    save_event("release", slug, {"version": version, "commit": commit, "release_id": release.get("id"), "draft": True, "time": now()})
    return 201, result


def finalize_project_release(payload):
    slug = str(payload.get("project") or payload.get("project_slug") or "").strip().lower()
    version = str(payload.get("version") or "").strip()
    release_id = str(payload.get("release_id") or "").strip()
    notes = str(payload.get("notes") or "")[:12000]
    if not SLUG_RE.fullmatch(slug) or not RELEASE_RE.fullmatch(version):
        return 400, {"ok": False, "error": "invalid_release_identity"}
    owner, repo = _release_repo_parts(slug)
    qowner = urllib.parse.quote(owner, safe="")
    qrepo = urllib.parse.quote(repo, safe="")
    if not release_id.isdigit():
        qversion = urllib.parse.quote(version, safe="")
        existing = _release_api("GET", f"/repos/{qowner}/{qrepo}/releases/tags/{qversion}", timeout=30)
        if not existing.get("ok") or not isinstance(existing.get("data"), dict):
            return 404, {"ok": False, "error": "release_not_found"}
        release_id = str(existing["data"].get("id") or "")
    payload_api = {"tag_name": version, "name": version, "draft": False, "prerelease": False}
    if notes:
        payload_api["body"] = notes
    updated = _release_api("PATCH", f"/repos/{qowner}/{qrepo}/releases/{release_id}", payload_api, timeout=45)
    if not updated.get("ok") or not isinstance(updated.get("data"), dict):
        return 502, {"ok": False, "error": "release_finalize_failed", "detail": updated}
    release = updated["data"]
    save_event("release", slug, {"version": version, "release_id": release_id, "draft": False, "time": now()})
    return 200, {"ok": True, "project": slug, "version": version, "release_id": release_id, "release_url": release.get("html_url") or "", "draft": False}


def ensure_forgejo_webhook(project):
    base = forgejo_api_base()
    token = CFG.get("FORGEJO_TOKEN", "")
    if not token:
        return {"ok": False, "message": "FORGEJO_TOKEN vazio."}

    slug = project["project_slug"]
    owner = project.get("forgejo", {}).get("owner") or project.get("forgejo_owner") or CFG.get("FORGEJO_OWNER") or ""
    repo = project.get("forgejo", {}).get("repo") or forgejo_repo_name(slug)
    if "/" in repo and not owner:
        owner, repo = repo.split("/", 1)

    if not owner:
        return {"ok": False, "message": "Owner do repositório não definido."}

    secret = project.setdefault("forgejo_webhook_secret", secrets.token_urlsafe(32))
    agent_private = clean_url(CFG.get("FORJA_AGENT_PRIVATE_URL") or f"http://127.0.0.1:{PORT}")
    url = f"{agent_private}/webhook/forgejo/{slug}"

    hooks = http_json("GET", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/hooks", token=token, timeout=8)
    existing_id = None
    if hooks.get("ok"):
        for h in hooks.get("data", []):
            cfg = h.get("config", {})
            if cfg.get("url") == url:
                existing_id = h.get("id")
                break

    payload_base = {
        "config": {
            "url": url,
            "content_type": "json",
            "secret": secret,
        },
        "events": ["push", "pull_request", "release"],
        "active": True,
    }

    last = None
    for hook_type in ["forgejo", "gitea"]:
        payload = dict(payload_base)
        payload["type"] = hook_type
        if existing_id:
            res = http_json("PATCH", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/hooks/{existing_id}", token=token, payload=payload, timeout=8)
        else:
            res = http_json("POST", f"{base}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/hooks", token=token, payload=payload, timeout=8)
        last = res
        if res.get("ok"):
            return {"ok": True, "message": "Webhook Forgejo configurado.", "url": url, "id": existing_id or res.get("data", {}).get("id"), "type": hook_type}

    return {"ok": False, "message": "Falha ao configurar webhook Forgejo.", "url": url, "detail": last}

def ensure_komodo_project_webhook(project):
    slug = project["project_slug"]
    token = project.setdefault("komodo_webhook_token", secrets.token_urlsafe(32))
    agent_private = clean_url(CFG.get("FORJA_AGENT_PRIVATE_URL") or f"http://127.0.0.1:{PORT}")
    local_url = f"{agent_private}/webhook/komodo/{slug}?token={urllib.parse.quote(token)}"

    project["komodo_webhook_url"] = local_url

    komodo_admin_token = CFG.get("KOMODO_TOKEN", "")
    api_base = clean_url(CFG.get("KOMODO_API_BASE", ""))
    if not api_base or not komodo_admin_token:
        return {
            "ok": True,
            "created_local": True,
            "created_remote": False,
            "message": "Webhook/token CloudIF-Komodo gerado. API administrativa do Komodo não configurada.",
            "url": local_url,
        }

    payload = {
        "name": f"cloudif-{slug}",
        "project": slug,
        "tenant": project.get("tenant"),
        "url": local_url,
        "token": token,
        "repo": project.get("forgejo", {}).get("url") or project.get("forgejo_expected"),
        "description": project.get("description", ""),
    }

    attempts = [
        "/webhooks",
        "/project/webhooks",
        "/procedure/webhooks",
        "/resources/webhooks",
        "/v1/webhooks",
    ]

    last = None
    for path in attempts:
        res = http_json("POST", api_base + path, token=komodo_admin_token, payload=payload, timeout=8, auth_style="bearer")
        last = res
        if res.get("ok"):
            return {"ok": True, "created_local": True, "created_remote": True, "message": f"Webhook criado no Komodo em {path}.", "url": local_url, "detail": res}

    return {
        "ok": True,
        "created_local": True,
        "created_remote": False,
        "message": "Webhook/token local gerado, mas a API do Komodo não aceitou os endpoints testados.",
        "url": local_url,
        "detail": last,
    }

def trigger_komodo(project):
    # Ação manual: se KOMODO_WEBHOOK_URL existir, chama. Caso contrário, só registra estado.
    hook = clean_url(CFG.get("KOMODO_WEBHOOK_URL", ""))
    token = CFG.get("KOMODO_TOKEN", "")
    slug=str(project.get("project_slug") or project.get("slug") or "").strip().lower()
    forgejo=project.get("forgejo") if isinstance(project.get("forgejo"),dict) else {}
    access=project.get("access") if isinstance(project.get("access"),dict) else {}
    owner=str(project.get("owner_user") or project.get("forgejo_owner") or access.get("owner") or "").strip().lower()
    repo_url=str(forgejo.get("url") or project.get("repo_url") or project.get("forgejo_expected") or "")
    payload = {
        "source": "cloudif-forja-agent",
        "time": now(),
        "project": slug,
        "project_slug": slug,
        "slug": slug,
        "tenant": project.get("tenant"),
        "name": project.get("name") or project.get("app_name") or slug,
        "app_name": project.get("app_name") or project.get("name") or slug,
        "owner_user": owner,
        "access": access,
        "repo_url": repo_url,
        "repo_url_original": repo_url,
        "forgejo": forgejo,
        "supabase_url": project.get("supabase_url"),
        "komodo_webhook_url": project.get("komodo_webhook_url"),
    }
    if not hook:
        return {"ok": True, "executed": False, "message": "KOMODO_WEBHOOK_URL não configurado. Estado do projeto atualizado.", "payload_preview": payload}
    res = http_json("POST", hook, token=token, payload=payload, timeout=10, auth_style="bearer")
    return {"ok": bool(res.get("ok")), "executed": bool(res.get("ok")), "message": "Komodo acionado." if res.get("ok") else "Falha ao acionar Komodo.", "detail": res}

def _cloudif_forgejo_signature_ok(project, raw, headers):
    secret = str(project.get("forgejo_webhook_secret") or "").encode("utf-8")
    if not secret:
        return False
    candidates = [
        headers.get("X-Forgejo-Signature", ""),
        headers.get("X-Gitea-Signature", ""),
        headers.get("X-Hub-Signature-256", ""),
        headers.get("X-Hub-Signature", ""),
    ]
    expected_sha256 = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    expected_sha1 = hmac.new(secret, raw, hashlib.sha1).hexdigest()
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value.startswith("sha256="):
            value = value.split("=", 1)[1]
            expected = expected_sha256
        elif value.startswith("sha1="):
            value = value.split("=", 1)[1]
            expected = expected_sha1
        else:
            expected = expected_sha256
        if value and hmac.compare_digest(value, expected):
            return True
    return False


def _cloudif_komodo_agent_call(path, payload, timeout=60):
    base = clean_url(CFG.get("KOMODO_AGENT_URL") or CFG.get("KOMODO_WEBHOOK_URL", ""))
    if "/komodo/" in base:
        base = base.split("/komodo/", 1)[0]
    token = str(CFG.get("KOMODO_AGENT_TOKEN") or CFG.get("KOMODO_TOKEN") or "")
    return http_json("POST", base + path, token=token, payload=payload, timeout=timeout, auth_style="bearer")


def _cloudif_forgejo_push_worker(slug, delivery, body):
    project = load_project(slug) or {}
    after = str(body.get("after") or "")
    repo = project.get("forgejo") or {}
    payload = {
        "project_slug": slug,
        "project": slug,
        "slug": slug,
        "tenant": project.get("tenant") or "",
        "name": project.get("name") or slug,
        "repo_url": repo.get("url") or project.get("repo_url") or project.get("forgejo_expected") or "",
        "actor": "forgejo-webhook",
        "source": "forgejo-push",
        "commit": after,
    }
    started = now()
    ensure = _cloudif_komodo_agent_call("/komodo/project/ensure", payload, timeout=90)
    pull = _cloudif_komodo_agent_call("/komodo/stack/pull", payload, timeout=90) if ensure.get("ok") else {"ok": False, "skipped": True}
    deploy = _cloudif_komodo_agent_call("/komodo/stack/deploy", payload, timeout=90) if pull.get("ok") else {"ok": False, "skipped": True}
    final = {}
    ready = False
    deadline = time.monotonic() + 420
    while deploy.get("ok") and time.monotonic() < deadline:
        status = _cloudif_komodo_agent_call("/komodo/project/status", payload, timeout=30)
        final = status.get("data") if isinstance(status.get("data"), dict) else {}
        runtime = final.get("runtime") or {}
        stack = final.get("stack") or {}
        deployed = str(stack.get("deployed_hash") or "")
        latest = str(stack.get("latest_hash") or "")
        hash_ok = (not after) or deployed == after[:7] or latest == after[:7]
        if final.get("deploy_status") == "completed" and runtime.get("running") is True and hash_ok:
            ready = True
            break
        time.sleep(5)
    result = {
        "ok": bool(ensure.get("ok") and pull.get("ok") and deploy.get("ok") and ready),
        "delivery": delivery,
        "project_slug": slug,
        "commit": after,
        "started_at": started,
        "finished_at": now(),
        "ensure": ensure,
        "pull": pull,
        "deploy": deploy,
        "final": final,
    }
    save_event("automation", slug, result)
    project["last_forgejo_automation_at"] = now()
    project["last_forgejo_automation_ok"] = result["ok"]
    project["last_forgejo_automation_commit"] = after
    project["last_forgejo_automation_delivery"] = delivery
    project["last_forgejo_automation_status"] = "completed" if result["ok"] else "failed"
    save_project(project)

def ensure_project(project):
    slug = project.get("project_slug", "")
    if not SLUG_RE.match(slug):
        return {"ok": False, "message": "project_slug inválido."}

    old = load_project(slug) or {}
    old.update(project)
    project = old
    project["updated_at"] = now()

    forgejo = ensure_forgejo_repo(project)
    project["forgejo"] = forgejo

    if forgejo.get("ok"):
        wh = ensure_forgejo_webhook(project)
    else:
        wh = {"ok": False, "message": "Webhook não criado porque repositório Forgejo falhou."}
    project["forgejo_webhook"] = wh

    komodo_wh = ensure_komodo_project_webhook(project)
    project["komodo_webhook"] = komodo_wh

    komodo_trigger = trigger_komodo(project)
    project["komodo_trigger"] = komodo_trigger

    project["forja_agent_status"] = "ok" if forgejo.get("ok") and wh.get("ok") else "attention"
    project["finished_at"] = now()

    saved = save_project(project)

    return {"ok": bool(forgejo.get("ok")), "message": "Projeto processado.", "project": saved}

def list_projects():
    out = []
    for p in sorted(STATE_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(errors="ignore")))
        except Exception:
            pass
    return out

def save_event(kind, slug, payload):
    d = EVENT_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{kind}-{int(time.time())}.json"
    path.write_text(jdump(payload))
    return str(path)


# CloudIF v47d auth helper BEGIN
def cloudif_load_env_file(path="/etc/cloudif/forja-agent.env"):
    data = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data

def cloudif_expected_forja_token():
    env = cloudif_load_env_file()
    return env.get("FORJA_AGENT_TOKEN", "")

def cloudif_request_token(handler):
    auth = handler.headers.get("Authorization", "") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return (
        handler.headers.get("X-CloudIF-Agent-Token", "")
        or handler.headers.get("X-Cloudif-Agent-Token", "")
        or handler.headers.get("X-Agent-Token", "")
        or ""
    ).strip()

def cloudif_auth_ok(handler):
    expected = cloudif_expected_forja_token()
    if not expected:
        return False
    got = cloudif_request_token(handler)
    return bool(got) and hmac.compare_digest(got, expected)

def cloudif_send_json(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
# CloudIF v47d auth helper END



# CloudIF v109 auth debug endpoint
def _cloudif_v109_fp(value):
    value = str(value or "").strip()
    if not value:
        return {"len": 0, "sha256_prefix": ""}
    return {
        "len": len(value),
        "sha256_prefix": hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
    }

def _cloudif_v109_debug_payload(handler):
    expected = (
        globals().get("FORJA_AGENT_TOKEN", "")
        or os.environ.get("FORJA_AGENT_TOKEN", "")
        or globals().get("TOKEN", "")
    )

    allowed = (
        globals().get("FORJA_ALLOWED_CLIENT", "")
        or os.environ.get("FORJA_ALLOWED_CLIENT", "")
    )

    got_x = handler.headers.get("X-CloudIF-Token", "")
    got_auth = handler.headers.get("Authorization", "")

    got_bearer = ""
    if got_auth.lower().startswith("bearer "):
        got_bearer = got_auth.split(" ", 1)[1].strip()

    client_ip = handler.client_address[0] if getattr(handler, "client_address", None) else ""

    exp_fp = _cloudif_v109_fp(expected)
    x_fp = _cloudif_v109_fp(got_x)
    bearer_fp = _cloudif_v109_fp(got_bearer)

    return {
        "ok": True,
        "client_ip": client_ip,
        "allowed_client": allowed,
        "client_allowed_match": (not allowed or allowed == client_ip),
        "expected_token": exp_fp,
        "received_x_cloudif_token": x_fp,
        "received_bearer_token": bearer_fp,
        "x_token_matches_expected": exp_fp == x_fp and exp_fp["len"] > 0,
        "bearer_token_matches_expected": exp_fp == bearer_fp and exp_fp["len"] > 0,
        "headers_present": {
            "x_cloudif_token": bool(got_x),
            "authorization": bool(got_auth),
        },
        "diagnosis": "Tokens are not printed. Compare len/sha256_prefix and client_allowed_match."
    }

def _cloudif_v109_send_debug(handler):
    body = json.dumps(_cloudif_v109_debug_payload(handler), ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)




# CloudIF v110 canonical auth override
def _cloudif_v110_expected_token():
    return (
        os.environ.get("FORJA_AGENT_TOKEN", "")
        or globals().get("FORJA_AGENT_TOKEN", "")
        or globals().get("TOKEN", "")
    ).strip()

def _cloudif_v110_allowed_client():
    return (
        os.environ.get("FORJA_ALLOWED_CLIENT", "")
        or globals().get("FORJA_ALLOWED_CLIENT", "")
    ).strip()

def _cloudif_v110_received_token(handler):
    got = (handler.headers.get("X-CloudIF-Token", "") or "").strip()
    if got:
        return got

    auth = (handler.headers.get("Authorization", "") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return ""

def _cloudif_v110_auth_result(handler):
    expected = _cloudif_v110_expected_token()
    received = _cloudif_v110_received_token(handler)
    allowed = _cloudif_v110_allowed_client()
    client_ip = handler.client_address[0] if getattr(handler, "client_address", None) else ""

    if allowed and client_ip != allowed:
        return False, "invalid_client"

    if not expected:
        return False, "server_token_not_configured"

    if not received:
        return False, "missing_token"

    if not hmac.compare_digest(received, expected):
        return False, "invalid_token"

    return True, "ok"

def cloudif_auth_ok(handler):
    ok, reason = _cloudif_v110_auth_result(handler)
    return ok

def _current_token():
    return _cloudif_v110_expected_token()




# CloudIF v114 webhook auth bypass
def _cloudif_v114_is_webhook_path(path):
    path = str(path or "").split("?", 1)[0]
    return path.startswith("/webhook/forgejo/") or path.startswith("/webhook/komodo/")

def _cloudif_v114_webhook_auth_ok(handler):
    """
    Webhooks não usam o mesmo token da hospedagem.
    Forgejo usa secret/assinatura própria; Komodo usa token na query.
    Este bypass apenas impede a autenticação global X-CloudIF-Token de bloquear
    o endpoint. A validação específica continua no handler do webhook.
    """
    return True




# CloudIF v117 — rollback remoto controlado no Forja Agent
def _cloudif_v117_slug(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value

def _cloudif_v117_repo_name(slug):
    slug = _cloudif_v117_slug(slug)
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def _cloudif_v117_send_json(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _cloudif_v117_read_json(handler):
    try:
        size = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        size = 0
    raw = handler.rfile.read(size) if size > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        return {}

def _cloudif_v117_cfg(key, default=""):
    try:
        if "CFG" in globals() and isinstance(CFG, dict):
            return str(CFG.get(key, default) or default)
    except Exception:
        pass
    return str(globals().get(key, default) or default)

def _cloudif_v117_http_json(method, url, token="", payload=None, timeout=30):
    headers = {"Accept": "application/json"}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            return r.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}

def cloudif_v117_project_rollback(handler):
    # Proteção: usa autenticação canônica já corrigida no v110.
    try:
        ok = cloudif_auth_ok(handler)
    except Exception:
        ok = False

    if not ok:
        return _cloudif_v117_send_json(handler, 403, {"ok": False, "error": "invalid_token"})

    payload = _cloudif_v117_read_json(handler)

    slug = _cloudif_v117_slug(payload.get("project_slug") or payload.get("slug") or payload.get("project") or "")
    execute = bool(payload.get("execute") is True or str(payload.get("mode", "")).lower() == "execute")
    confirm = str(payload.get("confirm", ""))

    if not slug:
        return _cloudif_v117_send_json(handler, 400, {"ok": False, "error": "project_slug inválido"})

    expected_confirm = f"ROLLBACK {slug}"
    if execute and confirm != expected_confirm:
        return _cloudif_v117_send_json(handler, 400, {
            "ok": False,
            "error": "confirmacao_invalida",
            "expected_confirm": expected_confirm,
        })

    owner = str(payload.get("owner") or "").strip().lower() or _cloudif_v117_cfg("FORGEJO_OWNER", "cloudif")
    repo = str(payload.get("repo") or "").strip() or _cloudif_v117_repo_name(slug)
    owner_kind = str(payload.get("owner_kind") or "user").strip().lower()
    forgejo_url = _cloudif_v117_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    explicit_repo_url = str(payload.get("repo_url") or "").strip().rstrip("/")
    if explicit_repo_url:
        try:
            parsed=urllib.parse.urlparse(explicit_repo_url);parts=[x for x in parsed.path.split('/') if x]
            if 'git' in parts: parts=parts[parts.index('git')+1:]
            if len(parts)>=2: owner=parts[-2];repo=parts[-1].removesuffix('.git')
        except Exception: pass
    forgejo_token = _cloudif_v117_cfg("FORGEJO_TOKEN", "")

    result = {
        "ok": True,
        "component": "forja-agent",
        "mode": "execute" if execute else "dry-run",
        "project_slug": slug,
        "repo": repo,
        "repo_path": f"{owner}/{repo}",
        "repo_url": explicit_repo_url or f"{forgejo_url}/{owner}/{repo}",
        "owner_kind": owner_kind,
        "forgejo": {
            "attempted": False,
            "deleted": False,
            "status": "dry_run",
        },
        "komodo": {
            "attempted": False,
        },
    }

    # Forgejo delete
    if execute:
        if not forgejo_token:
            result["forgejo"] = {
                "attempted": False,
                "deleted": False,
                "status": "missing_forgejo_token",
            }
        else:
            api = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
            st, data = _cloudif_v117_http_json("DELETE", api, token=forgejo_token)
            result["forgejo"] = {
                "attempted": True,
                "deleted": st in [200, 202, 204],
                "status": st,
                "response": data if st not in [200, 202, 204, 404] else {},
            }
            if st == 404:
                result["forgejo"]["deleted"] = True
                result["forgejo"]["status"] = "already_absent"
    else:
        result["forgejo"] = {
            "attempted": False,
            "deleted": False,
            "status": "dry_run",
            "would_delete": f"{owner}/{repo}",
        }

    # Komodo rollback
    komodo_url = _cloudif_v117_cfg("KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/")
    kpayload = {
        "project_slug": slug,
        "execute": execute,
        "confirm": confirm,
        "source": "forja-agent-v117",
    }

    st, data = _cloudif_v117_http_json("POST", komodo_url + "/komodo/project/rollback", token="", payload=kpayload, timeout=30)
    result["komodo"] = {
        "attempted": True,
        "status": st,
        "response": data,
    }

    result["ok"] = bool(
        (not execute or result["forgejo"].get("deleted") is True or result["forgejo"].get("status") in ["already_absent", "missing_forgejo_token"])
        and st in [200, 201, 202]
    )
    state_path = STATE_DIR / f"{slug}.json"
    result["local_state"] = {
        "path": str(state_path),
        "present": state_path.exists(),
        "removed": False,
    }
    if execute and result["ok"] and state_path.exists():
        state_path.unlink()
        result["local_state"]["removed"] = True

    return _cloudif_v117_send_json(handler, 200 if result["ok"] else 500, result)




# CloudIF v118 — commits, histórico e rollback por arquivo

CLOUDIF_V118_FILEOPS_DB = "/var/lib/cloudif/forja-agent/fileops.db"

def _v118_slug(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value

def _v118_repo_name(slug):
    slug = _v118_slug(slug)
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def _v118_safe_path(path):
    path = str(path or "").strip().replace("\\\\", "/")
    path = path.lstrip("/")
    if not path or ".." in path.split("/"):
        return ""
    return path

def _v118_cfg(key, default=""):
    try:
        if "CFG" in globals() and isinstance(CFG, dict):
            return str(CFG.get(key, default) or default)
    except Exception:
        pass
    return str(globals().get(key, default) or os.environ.get(key, default) or default)

def _v118_send_json(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _v118_read_json(handler):
    try:
        size = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        size = 0
    raw = handler.rfile.read(size) if size > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        return {}

def _v118_auth(handler):
    try:
        return bool(cloudif_auth_ok(handler))
    except Exception:
        expected = _v118_cfg("FORJA_AGENT_TOKEN", "")
        got = handler.headers.get("X-CloudIF-Token", "")
        return bool(expected and got and expected == got)

def _v118_db():
    Path(CLOUDIF_V118_FILEOPS_DB).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CLOUDIF_V118_FILEOPS_DB)
    con.execute("""
        create table if not exists file_events (
            id integer primary key autoincrement,
            ts text not null,
            project_slug text not null,
            repo text not null,
            branch text not null,
            path text not null,
            action text not null,
            status text not null,
            commit_sha text,
            before_sha256 text,
            after_sha256 text,
            before_content text,
            after_content text,
            message text,
            source text,
            raw_response text
        )
    """)
    con.commit()
    return con

def _v118_hash(content):
    if content is None:
        return ""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()

def _v118_now():
    import datetime
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _v118_forgejo_api(method, url, token, payload=None, timeout=30):
    headers = {"Accept": "application/json"}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            return r.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}

def _v118_get_file(owner, repo, path, branch):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    qpath = urllib.parse.quote(path, safe="/")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}?ref={urllib.parse.quote(branch)}"
    st, data = _v118_forgejo_api("GET", url, token)

    if st == 404:
        return {"exists": False, "status": st, "data": data, "sha": "", "content": None}

    if st not in [200]:
        return {"exists": False, "status": st, "data": data, "sha": "", "content": None, "error": True}

    content = data.get("content") or ""
    encoding = data.get("encoding") or "base64"

    decoded = ""
    if encoding == "base64":
        try:
            decoded = base64.b64decode(content.replace("\n", "")).decode("utf-8", "ignore")
        except Exception:
            decoded = ""
    else:
        decoded = str(content)

    return {
        "exists": True,
        "status": st,
        "data": data,
        "sha": data.get("sha") or "",
        "content": decoded,
    }

def _v118_put_file(owner, repo, path, branch, content, message, sha=""):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    qpath = urllib.parse.quote(path, safe="/")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}"

    payload = {
        "branch": branch,
        "message": message,
        "content": base64.b64encode(str(content or "").encode("utf-8")).decode("ascii"),
    }

    if sha:
        payload["sha"] = sha

    return _v118_forgejo_api("PUT", url, token, payload=payload, timeout=45)

def _v118_delete_file(owner, repo, path, branch, message, sha):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    qpath = urllib.parse.quote(path, safe="/")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}"

    payload = {
        "branch": branch,
        "message": message,
        "sha": sha,
    }

    return _v118_forgejo_api("DELETE", url, token, payload=payload, timeout=45)

def _v118_register_event(project_slug, repo, branch, path, action, status, commit_sha, before, after, message, source, raw):
    con = _v118_db()
    before_hash = _v118_hash(before) if before is not None else ""
    after_hash = _v118_hash(after) if after is not None else ""

    con.execute("""
        insert into file_events (
            ts, project_slug, repo, branch, path, action, status,
            commit_sha, before_sha256, after_sha256,
            before_content, after_content, message, source, raw_response
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _v118_now(),
        project_slug,
        repo,
        branch,
        path,
        action,
        status,
        commit_sha or "",
        before_hash,
        after_hash,
        before,
        after,
        message or "",
        source or "",
        json.dumps(raw or {}, ensure_ascii=False),
    ))
    con.commit()
    event_id = con.execute("select last_insert_rowid()").fetchone()[0]
    con.close()
    return event_id

def _v118_trigger_komodo(project_slug, owner, repo, branch, path, commit_sha, action):
    hook = _v118_cfg("KOMODO_WEBHOOK_URL", "").strip()
    if not hook:
        return {"ok": True, "executed": False, "message": "KOMODO_WEBHOOK_URL não configurado."}

    payload = {
        "project_slug": project_slug,
        "slug": project_slug,
        "repo": f"{owner}/{repo}",
        "repo_url": f"https://cloudiff.duckdns.org/git/{owner}/{repo}.git",
        "branch": branch,
        "source": "forja-agent-fileops-v118",
        "file_event": {
            "path": path,
            "commit_sha": commit_sha,
            "action": action,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        hook,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            return {"ok": r.status in [200, 201, 202], "executed": True, "status": r.status, "response": parsed}
    except Exception as e:
        return {"ok": False, "executed": True, "error": str(e)}

def cloudif_v118_file_commit(handler):
    if not _v118_auth(handler):
        return _v118_send_json(handler, 403, {"ok": False, "error": "invalid_token"})

    payload = _v118_read_json(handler)

    slug = _v118_slug(payload.get("project_slug") or payload.get("slug") or "")
    path = _v118_safe_path(payload.get("path") or "")
    branch = str(payload.get("branch") or "main")
    message = str(payload.get("message") or f"CloudIF: update {path}")
    source = str(payload.get("source") or "portal")

    if not slug or not path:
        return _v118_send_json(handler, 400, {"ok": False, "error": "project_slug/path inválidos"})

    if "content_b64" in payload:
        try:
            content = base64.b64decode(str(payload.get("content_b64") or "")).decode("utf-8", "ignore")
        except Exception:
            return _v118_send_json(handler, 400, {"ok": False, "error": "content_b64 inválido"})
    else:
        content = str(payload.get("content") or "")

    owner = _v118_slug(payload.get("owner") or payload.get("repo_owner") or "")
    repo = _v118_slug(payload.get("repo") or "") or _v118_repo_name(slug)
    repo_path = str(payload.get("repo_path") or "").strip().removesuffix('.git')
    if repo_path and '/' in repo_path:
        path_owner,path_repo=repo_path.split('/',1)
        owner=_v118_slug(path_owner) or owner
        repo=_v118_slug(path_repo) or repo
    if not owner:
        return _v118_send_json(handler, 422, {"ok":False,"error":"repo_owner_required","project_slug":slug})

    before = _v118_get_file(owner, repo, path, branch)

    if before.get("error"):
        return _v118_send_json(handler, 502, {"ok": False, "error": "erro_lendo_arquivo", "detail": before})

    before_content = before.get("content")
    sha = before.get("sha") or ""

    st, data = _v118_put_file(owner, repo, path, branch, content, message, sha=sha)

    commit_sha = ""
    if isinstance(data, dict):
        commit_sha = ((data.get("commit") or {}).get("sha")) or data.get("commit_sha") or ""

    ok = st in [200, 201]

    event_id = _v118_register_event(
        slug, repo, branch, path,
        "update" if before.get("exists") else "create",
        "committed" if ok else "failed",
        commit_sha,
        before_content,
        content,
        message,
        source,
        {"status": st, "response": data},
    )

    komodo = {}
    if ok:
        komodo = _v118_trigger_komodo(slug, owner, repo, branch, path, commit_sha, "commit")

    return _v118_send_json(handler, 200 if ok else 502, {
        "ok": ok,
        "project_slug": slug,
        "owner": owner,
        "repo": repo,
        "repo_path": f"{owner}/{repo}",
        "path": path,
        "branch": branch,
        "event_id": event_id,
        "commit_sha": commit_sha,
        "forgejo_status": st,
        "komodo_trigger": komodo,
    })

def cloudif_v118_file_history(handler):
    if not _v118_auth(handler):
        return _v118_send_json(handler, 403, {"ok": False, "error": "invalid_token"})

    parsed = urllib.parse.urlparse(handler.path)
    qs = urllib.parse.parse_qs(parsed.query)

    slug = _v118_slug((qs.get("project_slug") or qs.get("slug") or [""])[0])
    path = _v118_safe_path((qs.get("path") or [""])[0])

    if not slug:
        return _v118_send_json(handler, 400, {"ok": False, "error": "project_slug inválido"})

    con = _v118_db()
    con.row_factory = sqlite3.Row

    if path:
        rows = con.execute("""
            select id, ts, project_slug, repo, branch, path, action, status,
                   commit_sha, before_sha256, after_sha256, message, source
            from file_events
            where project_slug=? and path=?
            order by id desc limit 50
        """, (slug, path)).fetchall()
    else:
        rows = con.execute("""
            select id, ts, project_slug, repo, branch, path, action, status,
                   commit_sha, before_sha256, after_sha256, message, source
            from file_events
            where project_slug=?
            order by id desc limit 100
        """, (slug,)).fetchall()

    con.close()

    return _v118_send_json(handler, 200, {
        "ok": True,
        "project_slug": slug,
        "path": path,
        "events": [dict(r) for r in rows],
    })

def cloudif_v118_file_rollback(handler):
    if not _v118_auth(handler):
        return _v118_send_json(handler, 403, {"ok": False, "error": "invalid_token"})

    payload = _v118_read_json(handler)

    slug = _v118_slug(payload.get("project_slug") or payload.get("slug") or "")
    path = _v118_safe_path(payload.get("path") or "")
    branch = str(payload.get("branch") or "main")
    source = str(payload.get("source") or "portal")
    target_event_id = payload.get("target_event_id")

    if not slug or not path:
        return _v118_send_json(handler, 400, {"ok": False, "error": "project_slug/path inválidos"})

    owner = _v118_cfg("FORGEJO_OWNER", "cloudif")
    repo = _v118_repo_name(slug)

    con = _v118_db()
    con.row_factory = sqlite3.Row

    target = None

    if target_event_id:
        target = con.execute("""
            select * from file_events
            where project_slug=? and path=? and id=?
        """, (slug, path, int(target_event_id))).fetchone()
    else:
        latest = con.execute("""
            select * from file_events
            where project_slug=? and path=?
            order by id desc limit 1
        """, (slug, path)).fetchone()

        if latest:
            target = latest

    con.close()

    if not target:
        return _v118_send_json(handler, 404, {"ok": False, "error": "histórico não encontrado"})

    target = dict(target)

    # Rollback padrão: volta para before_content do último evento.
    rollback_content = target.get("before_content")

    current = _v118_get_file(owner, repo, path, branch)
    if current.get("error"):
        return _v118_send_json(handler, 502, {"ok": False, "error": "erro_lendo_arquivo_atual", "detail": current})

    current_content = current.get("content")
    current_sha = current.get("sha") or ""

    message = str(payload.get("message") or f"CloudIF: rollback {path} para evento {target.get('id')}")

    if rollback_content is None:
        if not current_sha:
            return _v118_send_json(handler, 400, {"ok": False, "error": "arquivo atual ausente; nada para remover"})
        st, data = _v118_delete_file(owner, repo, path, branch, message, current_sha)
        after_content = None
    else:
        st, data = _v118_put_file(owner, repo, path, branch, rollback_content, message, sha=current_sha)
        after_content = rollback_content

    commit_sha = ""
    if isinstance(data, dict):
        commit_sha = ((data.get("commit") or {}).get("sha")) or data.get("commit_sha") or ""

    ok = st in [200, 201]

    event_id = _v118_register_event(
        slug, repo, branch, path,
        "rollback",
        "rolled_back" if ok else "failed",
        commit_sha,
        current_content,
        after_content,
        message,
        source,
        {"status": st, "response": data, "target_event": target.get("id")},
    )

    komodo = {}
    if ok:
        komodo = _v118_trigger_komodo(slug, repo, branch, path, commit_sha, "rollback")

    return _v118_send_json(handler, 200 if ok else 502, {
        "ok": ok,
        "project_slug": slug,
        "repo": repo,
        "path": path,
        "branch": branch,
        "rollback_event_id": event_id,
        "target_event_id": target.get("id"),
        "commit_sha": commit_sha,
        "forgejo_status": st,
        "komodo_trigger": komodo,
    })




# CloudIF v119 — FileOps robusto com fallback Git CLI

def _v119_mask(value):
    token = _v118_cfg("FORGEJO_TOKEN", "") if "_v118_cfg" in globals() else ""
    service_user = _v118_cfg("FORGEJO_SERVICE_USER", "cloudif-bot") if "_v118_cfg" in globals() else "cloudif-bot"
    s = str(value or "")
    if token:
        s = s.replace(token, "***TOKEN_OCULTO***")
    if service_user:
        s = s.replace(service_user + ":", service_user + ":***")
    return s

def _v119_forgejo_repo_git_url(owner, repo):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    user = _v118_cfg("FORGEJO_SERVICE_USER", "cloudif-bot") or "cloudif-bot"

    parsed = urllib.parse.urlparse(forgejo_url)
    if parsed.scheme not in ["http", "https"]:
        raise RuntimeError("FORGEJO_URL inválida para git clone")

    user_q = urllib.parse.quote(user, safe="")
    token_q = urllib.parse.quote(token, safe="")
    netloc = f"{user_q}:{token_q}@{parsed.netloc}"
    base = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path.rstrip("/"), "", "", ""))

    return f"{base}/{owner}/{repo}.git"

def _v119_run(cmd, cwd=None, timeout=90):
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "returncode": r.returncode,
            "stdout": _v119_mask(r.stdout),
            "stderr": _v119_mask(r.stderr),
        }
    except Exception as e:
        return {
            "returncode": 999,
            "stdout": "",
            "stderr": _v119_mask(str(e)),
        }

def _v119_git_commit_file(owner, repo, path, branch, content, message, delete=False):
    token = _v118_cfg("FORGEJO_TOKEN", "")
    if not token:
        return 0, {"error": "FORGEJO_TOKEN vazio; fallback git indisponível"}

    branch = branch or "main"
    tmp = tempfile.mkdtemp(prefix="cloudif-fileops-")

    try:
        url = _v119_forgejo_repo_git_url(owner, repo)

        clone = _v119_run(["git", "clone", "--depth", "1", "--branch", branch, url, tmp], timeout=120)

        if clone["returncode"] != 0:
            clone = _v119_run(["git", "clone", url, tmp], timeout=120)

        if clone["returncode"] != 0:
            return 0, {"error": "git clone falhou", "detail": clone}

        _v119_run(["git", "config", "user.name", "CloudIF Bot"], cwd=tmp)
        _v119_run(["git", "config", "user.email", "cloudif-bot@cloudiff.local"], cwd=tmp)

        checkout = _v119_run(["git", "checkout", "-B", branch], cwd=tmp)
        if checkout["returncode"] != 0:
            return 0, {"error": "git checkout -B falhou", "detail": checkout}

        file_path = Path(tmp) / path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        existed_before = file_path.exists()
        before_content = file_path.read_text(errors="ignore") if existed_before else None

        if delete:
            if file_path.exists():
                file_path.unlink()
            else:
                return 404, {"error": "arquivo não existe para delete", "git_fallback": True}
        else:
            file_path.write_text(str(content or ""), encoding="utf-8")

        add = _v119_run(["git", "add", "-A", path], cwd=tmp)
        if add["returncode"] != 0:
            return 0, {"error": "git add falhou", "detail": add}

        status = _v119_run(["git", "status", "--porcelain", "--", path], cwd=tmp)
        if not (status.get("stdout") or "").strip():
            head = _v119_run(["git", "rev-parse", "HEAD"], cwd=tmp)
            sha = (head.get("stdout") or "").strip()
            return 200, {
                "ok": True,
                "git_fallback": True,
                "message": "sem alterações",
                "commit": {"sha": sha},
                "existed_before": existed_before,
                "before_content": before_content,
            }

        commit = _v119_run(["git", "commit", "-m", message], cwd=tmp, timeout=120)
        if commit["returncode"] != 0:
            return 0, {"error": "git commit falhou", "detail": commit}

        push = _v119_run(["git", "push", "origin", f"HEAD:{branch}"], cwd=tmp, timeout=120)
        if push["returncode"] != 0:
            return 0, {"error": "git push falhou", "detail": push}

        head = _v119_run(["git", "rev-parse", "HEAD"], cwd=tmp)
        sha = (head.get("stdout") or "").strip()

        return 201, {
            "ok": True,
            "git_fallback": True,
            "commit": {"sha": sha},
            "existed_before": existed_before,
            "before_content": before_content,
            "push": push,
        }

    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass

def _v119_repo_default_branch(owner, repo):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    st, data = _v118_forgejo_api("GET", url, token)
    if st == 200 and isinstance(data, dict):
        return data.get("default_branch") or data.get("default_branch_name") or "main"
    return "main"

def _v118_put_file(owner, repo, path, branch, content, message, sha=""):
    """
    v119 override:
    1. tenta API contents;
    2. se API falhar com 422/404/409/0, usa git clone/commit/push.
    """
    branch = branch or _v119_repo_default_branch(owner, repo) or "main"
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    qpath = urllib.parse.quote(path, safe="/")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}"

    attempts = []

    payloads = []

    base = {
        "message": message,
        "content": base64.b64encode(str(content or "").encode("utf-8")).decode("ascii"),
    }

    if sha:
        p1 = dict(base)
        p1["branch"] = branch
        p1["sha"] = sha
        payloads.append(("api_update_branch", p1))

        p2 = dict(base)
        p2["sha"] = sha
        payloads.append(("api_update_no_branch", p2))
    else:
        p1 = dict(base)
        p1["branch"] = branch
        payloads.append(("api_create_branch", p1))

        p2 = dict(base)
        payloads.append(("api_create_no_branch", p2))

        p3 = dict(base)
        p3["branch"] = branch
        p3["new_branch"] = branch
        payloads.append(("api_create_new_branch", p3))

    last_st, last_data = 0, {}

    for label, payload in payloads:
        st, data = _v118_forgejo_api("PUT", url, token, payload=payload, timeout=45)
        attempts.append({"label": label, "status": st, "response": data})
        last_st, last_data = st, data
        if st in [200, 201]:
            if isinstance(data, dict):
                data["attempts"] = attempts
            return st, data

    git_st, git_data = _v119_git_commit_file(owner, repo, path, branch, content, message, delete=False)
    if isinstance(git_data, dict):
        git_data["api_attempts"] = attempts

    if git_st in [200, 201]:
        return git_st, git_data

    return last_st, {
        "error": "api_contents_e_git_fallback_falharam",
        "api_last_response": last_data,
        "api_attempts": attempts,
        "git_status": git_st,
        "git_response": git_data,
    }

def _v118_delete_file(owner, repo, path, branch, message, sha):
    """
    v119 override para delete com fallback Git CLI.
    """
    branch = branch or _v119_repo_default_branch(owner, repo) or "main"
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = _v118_cfg("FORGEJO_TOKEN", "")
    qpath = urllib.parse.quote(path, safe="/")
    url = f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}"

    payload = {
        "branch": branch,
        "message": message,
        "sha": sha,
    }

    st, data = _v118_forgejo_api("DELETE", url, token, payload=payload, timeout=45)
    if st in [200, 201, 202, 204]:
        return st, data

    git_st, git_data = _v119_git_commit_file(owner, repo, path, branch, "", message, delete=True)
    if isinstance(git_data, dict):
        git_data["api_delete_status"] = st
        git_data["api_delete_response"] = data

    if git_st in [200, 201]:
        return git_st, git_data

    return st, {
        "error": "api_delete_e_git_fallback_falharam",
        "api_response": data,
        "git_status": git_st,
        "git_response": git_data,
    }

def cloudif_v118_file_rollback(handler):
    """
    v119 override: rollback ignora eventos failed.
    Usa apenas último evento committed/rolled_back, a menos que target_event_id seja informado.
    """
    if not _v118_auth(handler):
        return _v118_send_json(handler, 403, {"ok": False, "error": "invalid_token"})

    payload = _v118_read_json(handler)

    slug = _v118_slug(payload.get("project_slug") or payload.get("slug") or "")
    path = _v118_safe_path(payload.get("path") or "")
    branch = str(payload.get("branch") or "main")
    source = str(payload.get("source") or "portal")
    target_event_id = payload.get("target_event_id")

    if not slug or not path:
        return _v118_send_json(handler, 400, {"ok": False, "error": "project_slug/path inválidos"})

    owner = _v118_cfg("FORGEJO_OWNER", "cloudif")
    repo = _v118_repo_name(slug)

    con = _v118_db()
    con.row_factory = sqlite3.Row

    if target_event_id:
        target = con.execute("""
            select * from file_events
            where project_slug=? and path=? and id=? and status in ('committed','rolled_back')
        """, (slug, path, int(target_event_id))).fetchone()
    else:
        target = con.execute("""
            select * from file_events
            where project_slug=? and path=? and status in ('committed','rolled_back')
            order by id desc limit 1
        """, (slug, path)).fetchone()

    con.close()

    if not target:
        return _v118_send_json(handler, 404, {
            "ok": False,
            "error": "histórico válido não encontrado",
            "message": "Não há evento committed/rolled_back para usar como rollback.",
        })

    target = dict(target)
    rollback_content = target.get("before_content")

    current = _v118_get_file(owner, repo, path, branch)
    if current.get("error"):
        return _v118_send_json(handler, 502, {"ok": False, "error": "erro_lendo_arquivo_atual", "detail": current})

    current_content = current.get("content")
    current_sha = current.get("sha") or ""

    message = str(payload.get("message") or f"CloudIF: rollback {path} para evento {target.get('id')}")

    if rollback_content is None:
        if not current_sha:
            return _v118_send_json(handler, 400, {"ok": False, "error": "arquivo atual ausente; nada para remover"})
        st, data = _v118_delete_file(owner, repo, path, branch, message, current_sha)
        after_content = None
    else:
        st, data = _v118_put_file(owner, repo, path, branch, rollback_content, message, sha=current_sha)
        after_content = rollback_content

    commit_sha = ""
    if isinstance(data, dict):
        commit_sha = ((data.get("commit") or {}).get("sha")) or data.get("commit_sha") or ""

    ok = st in [200, 201, 202, 204]

    event_id = _v118_register_event(
        slug, repo, branch, path,
        "rollback",
        "rolled_back" if ok else "failed",
        commit_sha,
        current_content,
        after_content,
        message,
        source,
        {"status": st, "response": data, "target_event": target.get("id")},
    )

    komodo = {}
    if ok:
        komodo = _v118_trigger_komodo(slug, repo, branch, path, commit_sha, "rollback")

    return _v118_send_json(handler, 200 if ok else 502, {
        "ok": ok,
        "project_slug": slug,
        "repo": repo,
        "path": path,
        "branch": branch,
        "rollback_event_id": event_id,
        "target_event_id": target.get("id"),
        "commit_sha": commit_sha,
        "forgejo_status": st,
        "komodo_trigger": komodo,
    })




# CloudIF v120 — correção Forgejo Contents API: POST cria, PUT atualiza
def _v120_forgejo_contents_url(owner, repo, path):
    forgejo_url = _v118_cfg("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    qpath = urllib.parse.quote(path, safe="/")
    return f"{forgejo_url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/{qpath}"

def _v118_put_file(owner, repo, path, branch, content, message, sha=""):
    """
    v120 override:
    - arquivo novo: POST /contents/path sem sha
    - arquivo existente: PUT /contents/path com sha
    - fallback: Git CLI v119
    """
    branch = branch or (_v119_repo_default_branch(owner, repo) if "_v119_repo_default_branch" in globals() else "main") or "main"
    token = _v118_cfg("FORGEJO_TOKEN", "")
    url = _v120_forgejo_contents_url(owner, repo, path)

    payload = {
        "branch": branch,
        "message": message,
        "content": base64.b64encode(str(content or "").encode("utf-8")).decode("ascii"),
    }

    if sha:
        method = "PUT"
        payload["sha"] = sha
        label = "api_update_put_with_sha"
    else:
        method = "POST"
        label = "api_create_post_no_sha"

    attempts = []

    st, data = _v118_forgejo_api(method, url, token, payload=payload, timeout=45)
    attempts.append({"label": label, "method": method, "status": st, "response": data})

    if st in [200, 201]:
        if isinstance(data, dict):
            data["attempts"] = attempts
        return st, data

    # Fallback adicional: se create via POST respondeu conflito, tenta ler sha e atualizar.
    if not sha and st in [409, 422]:
        current = _v118_get_file(owner, repo, path, branch)
        current_sha = current.get("sha") or ""
        if current_sha:
            payload2 = dict(payload)
            payload2["sha"] = current_sha
            st2, data2 = _v118_forgejo_api("PUT", url, token, payload=payload2, timeout=45)
            attempts.append({
                "label": "api_fallback_update_after_get_sha",
                "method": "PUT",
                "status": st2,
                "response": data2,
            })
            if st2 in [200, 201]:
                if isinstance(data2, dict):
                    data2["attempts"] = attempts
                return st2, data2

    # Fallback final: git clone/commit/push do v119.
    if "_v119_git_commit_file" in globals():
        git_st, git_data = _v119_git_commit_file(owner, repo, path, branch, content, message, delete=False)
        if isinstance(git_data, dict):
            git_data["api_attempts"] = attempts

        if git_st in [200, 201]:
            return git_st, git_data

        return st, {
            "error": "api_contents_e_git_fallback_falharam",
            "api_attempts": attempts,
            "git_status": git_st,
            "git_response": git_data,
        }

    return st, {
        "error": "api_contents_falhou_sem_fallback_git",
        "api_attempts": attempts,
    }

def _v118_delete_file(owner, repo, path, branch, message, sha):
    """
    v120 override:
    delete pela API precisa de DELETE com sha.
    Se falhar, usa fallback Git CLI.
    """
    branch = branch or (_v119_repo_default_branch(owner, repo) if "_v119_repo_default_branch" in globals() else "main") or "main"
    token = _v118_cfg("FORGEJO_TOKEN", "")
    url = _v120_forgejo_contents_url(owner, repo, path)

    payload = {
        "branch": branch,
        "message": message,
        "sha": sha,
    }

    st, data = _v118_forgejo_api("DELETE", url, token, payload=payload, timeout=45)

    if st in [200, 201, 202, 204]:
        return st, data

    if "_v119_git_commit_file" in globals():
        git_st, git_data = _v119_git_commit_file(owner, repo, path, branch, "", message, delete=True)
        if isinstance(git_data, dict):
            git_data["api_delete_status"] = st
            git_data["api_delete_response"] = data

        if git_st in [200, 201]:
            return git_st, git_data

        return st, {
            "error": "api_delete_e_git_fallback_falharam",
            "api_response": data,
            "git_status": git_st,
            "git_response": git_data,
        }

    return st, data




# CloudIF v121 — wrapper seguro para FileOps
def _cloudif_v121_send_exception(handler, where, exc):
    tb = traceback.format_exc()
    try:
        body = json.dumps({
            "ok": False,
            "error": "fileops_exception",
            "where": where,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback_tail": tb[-4000:],
        }, ensure_ascii=False, indent=2).encode("utf-8")

        handler.send_response(500)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except Exception:
        raise

def cloudif_v121_file_commit_safe(handler):
    try:
        return cloudif_v118_file_commit(handler)
    except Exception as exc:
        return _cloudif_v121_send_exception(handler, "cloudif_v118_file_commit", exc)

def cloudif_v121_file_rollback_safe(handler):
    try:
        return cloudif_v118_file_rollback(handler)
    except Exception as exc:
        return _cloudif_v121_send_exception(handler, "cloudif_v118_file_rollback", exc)

def cloudif_v121_file_debug(handler):
    try:
        parsed = urllib.parse.urlparse(handler.path)
        qs = urllib.parse.parse_qs(parsed.query)

        slug = _v118_slug((qs.get("project_slug") or qs.get("slug") or [""])[0])
        path = _v118_safe_path((qs.get("path") or [""])[0])
        branch = (qs.get("branch") or ["main"])[0]

        owner = _v118_cfg("FORGEJO_OWNER", "cloudif")
        repo = _v118_repo_name(slug) if slug else ""

        info = {
            "ok": True,
            "project_slug": slug,
            "path": path,
            "branch": branch,
            "owner": owner,
            "repo": repo,
            "functions": {
                "_v118_put_file": "_v118_put_file" in globals(),
                "_v120_forgejo_contents_url": "_v120_forgejo_contents_url" in globals(),
                "_v119_git_commit_file": "_v119_git_commit_file" in globals(),
                "cloudif_v118_file_commit": "cloudif_v118_file_commit" in globals(),
            },
        }

        if slug and path:
            try:
                current = _v118_get_file(owner, repo, path, branch)
                safe_current = dict(current)
                if safe_current.get("content"):
                    safe_current["content_preview"] = safe_current.get("content", "")[:300]
                    safe_current["content"] = "***OMITIDO***"
                info["current_file"] = safe_current
            except Exception as e:
                info["current_file_error"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback_tail": traceback.format_exc()[-2000:],
                }

            try:
                con = _v118_db()
                con.row_factory = sqlite3.Row
                rows = con.execute("""
                    select id, ts, project_slug, repo, branch, path, action, status,
                           commit_sha, before_sha256, after_sha256, message, source, raw_response
                    from file_events
                    where project_slug=? and path=?
                    order by id desc limit 8
                """, (slug, path)).fetchall()
                con.close()
                events = []
                for r in rows:
                    d = dict(r)
                    raw = d.get("raw_response") or ""
                    d["raw_response_preview"] = raw[:1200]
                    d.pop("raw_response", None)
                    events.append(d)
                info["recent_events"] = events
            except Exception as e:
                info["events_error"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback_tail": traceback.format_exc()[-2000:],
                }

        return _v118_send_json(handler, 200, info)
    except Exception as exc:
        return _cloudif_v121_send_exception(handler, "cloudif_v121_file_debug", exc)




# CloudIF v122 — serialização segura para eventos FileOps
def _cloudif_v122_json_safe(obj, max_depth=6, max_str=2000, _seen=None):
    if _seen is None:
        _seen = set()

    oid = id(obj)

    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        # mascara tokens comuns
        s = obj
        try:
            token = _v118_cfg("FORGEJO_TOKEN", "")
            if token:
                s = s.replace(token, "***TOKEN_OCULTO***")
        except Exception:
            pass
        if len(s) > max_str:
            return s[:max_str] + "...[TRUNCADO]"
        return s

    if isinstance(obj, bytes):
        return f"<bytes {len(obj)}>"

    if oid in _seen:
        return "<circular_ref>"

    if max_depth <= 0:
        return "<max_depth>"

    if isinstance(obj, dict):
        _seen.add(oid)
        out = {}
        for k, v in obj.items():
            ks = str(k)

            # evita salvar blobs/conteúdo bruto gigante
            if ks.lower() in ["content", "token", "secret", "authorization", "password"]:
                out[ks] = "***OMITIDO***"
                continue

            # a origem do bug: attempts[].response pode apontar para o próprio objeto
            if ks == "response" and isinstance(v, dict):
                out[ks] = {
                    "keys": sorted([str(x) for x in v.keys()])[:50],
                    "message": v.get("message"),
                    "url": v.get("url"),
                    "sha": v.get("sha"),
                    "commit_sha": ((v.get("commit") or {}).get("sha") if isinstance(v.get("commit"), dict) else v.get("commit_sha")),
                    "status": v.get("status"),
                }
                continue

            out[ks] = _cloudif_v122_json_safe(v, max_depth=max_depth-1, max_str=max_str, _seen=_seen)

        _seen.discard(oid)
        return out

    if isinstance(obj, (list, tuple, set)):
        _seen.add(oid)
        arr = []
        for i, v in enumerate(list(obj)[:100]):
            arr.append(_cloudif_v122_json_safe(v, max_depth=max_depth-1, max_str=max_str, _seen=_seen))
        if len(obj) > 100:
            arr.append(f"...[{len(obj)-100} itens omitidos]")
        _seen.discard(oid)
        return arr

    return str(obj)

def _cloudif_v122_json_dumps_safe(obj):
    try:
        return json.dumps(_cloudif_v122_json_safe(obj), ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "serialization_error": type(e).__name__,
            "message": str(e),
            "traceback_tail": traceback.format_exc()[-1500:],
        }, ensure_ascii=False)

def _v118_register_event(project_slug, repo, branch, path, action, status, commit_sha, before, after, message, source, raw):
    """
    v122 override:
    registra auditoria sem quebrar o commit por erro de serialização.
    """
    con = _v118_db()
    before_hash = _v118_hash(before) if before is not None else ""
    after_hash = _v118_hash(after) if after is not None else ""

    raw_json = _cloudif_v122_json_dumps_safe(raw or {})

    con.execute("""
        insert into file_events (
            ts, project_slug, repo, branch, path, action, status,
            commit_sha, before_sha256, after_sha256,
            before_content, after_content, message, source, raw_response
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _v118_now(),
        project_slug,
        repo,
        branch,
        path,
        action,
        status,
        commit_sha or "",
        before_hash,
        after_hash,
        before,
        after,
        message or "",
        source or "",
        raw_json,
    ))

    con.commit()
    event_id = con.execute("select last_insert_rowid()").fetchone()[0]
    con.close()
    return event_id


# CloudIF workspace archive read-only BEGIN
_CLOUDIF_ARCHIVE_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
_CLOUDIF_ARCHIVE_REF_RE = re.compile(r'^[A-Za-z0-9._/-]{1,128}$')
_CLOUDIF_ARCHIVE_MAX = 20 * 1024 * 1024

def cloudif_workspace_archive(handler, qs):
    if not cloudif_auth_ok(handler):
        return cloudif_send_json(handler, 403, {'ok': False, 'error': 'invalid_token'})
    slug = str((qs.get('slug') or [''])[0]).strip()
    ref = str((qs.get('ref') or ['main'])[0]).strip()
    if not _CLOUDIF_ARCHIVE_SLUG_RE.fullmatch(slug) or not _CLOUDIF_ARCHIVE_REF_RE.fullmatch(ref) or '..' in ref or ref.startswith('/') or ref.endswith('/'):
        return cloudif_send_json(handler, 400, {'ok': False, 'error': 'invalid_request'})
    project = load_project(slug)
    if not project:
        return cloudif_send_json(handler, 404, {'ok': False, 'error': 'project_not_found'})
    owner = str(project.get('forgejo', {}).get('owner') or project.get('forgejo_owner') or CFG.get('FORGEJO_OWNER') or 'cloudif').strip()
    repo = str(project.get('forgejo', {}).get('repo') or forgejo_repo_name(slug)).strip()
    if '/' in repo:
        ro, rr = repo.split('/', 1); owner = ro or owner; repo = rr
    if not _CLOUDIF_ARCHIVE_SLUG_RE.fullmatch(owner) or not _CLOUDIF_ARCHIVE_SLUG_RE.fullmatch(repo):
        return cloudif_send_json(handler, 409, {'ok': False, 'error': 'invalid_repo_mapping'})
    base = forgejo_api_base().rstrip('/')
    token = CFG.get('FORGEJO_TOKEN', '')
    if not base or not token:
        return cloudif_send_json(handler, 503, {'ok': False, 'error': 'forgejo_not_configured'})
    url = f"{base}/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}/archive/{urllib.parse.quote(ref, safe='')}.tar.gz"
    req = urllib.request.Request(url, headers={'Authorization': 'token ' + token, 'Accept': 'application/gzip', 'User-Agent': 'cloudif-forja-agent/archive'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read(_CLOUDIF_ARCHIVE_MAX + 1)
            ctype = r.headers.get('Content-Type', '')
    except urllib.error.HTTPError as e:
        return cloudif_send_json(handler, 404 if e.code == 404 else 502, {'ok': False, 'error': 'archive_unavailable', 'upstream_status': e.code})
    except Exception:
        return cloudif_send_json(handler, 502, {'ok': False, 'error': 'archive_unavailable'})
    if len(raw) > _CLOUDIF_ARCHIVE_MAX:
        return cloudif_send_json(handler, 413, {'ok': False, 'error': 'archive_too_large'})
    if len(raw) < 2 or raw[:2] != b'\x1f\x8b':
        return cloudif_send_json(handler, 502, {'ok': False, 'error': 'invalid_archive'})
    digest = hashlib.sha256(raw).hexdigest()
    handler.send_response(200)
    handler.send_header('Content-Type', 'application/gzip')
    handler.send_header('Cache-Control', 'private, no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-CloudIF-Project', slug)
    handler.send_header('X-CloudIF-Ref', ref)
    handler.send_header('X-CloudIF-SHA256', digest)
    handler.send_header('Content-Length', str(len(raw)))
    handler.end_headers();handler.wfile.write(raw)
# CloudIF workspace archive read-only END


_PROPOSAL_PATH_RE = re.compile(r'^site/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.html$')
_PROPOSAL_SHA_RE = re.compile(r'^[a-f0-9]{64}$')

def _proposal_api(method, path, payload=None, timeout=45):
    base = forgejo_api_base().rstrip('/')
    token = CFG.get('FORGEJO_TOKEN','')
    return http_json(method, base + path, token=token, payload=payload, timeout=timeout)

def _proposal_repo(project, slug):
    owner = str((project.get('forgejo') or {}).get('owner') or project.get('forgejo_owner') or project.get('forgejo_org') or CFG.get('FORGEJO_OWNER') or 'cloudif').strip()
    repo = str((project.get('forgejo') or {}).get('repo') or project.get('repo') or project.get('repo_name') or forgejo_repo_name(slug)).strip()
    if '/' in repo:
        ro, rr = repo.split('/',1); owner = ro or owner; repo = rr
    if not SLUG_RE.fullmatch(owner) or not SLUG_RE.fullmatch(repo):
        raise ValueError('invalid_repo_mapping')
    return owner, repo

def cloudif_proposal_list(handler, qs):
    allowed={'slug','state','limit'}
    if set(qs)-allowed:
        return json_response(handler,400,{'ok':False,'error':'invalid_query'})
    slug=str((qs.get('slug') or [''])[0]).strip()
    state=str((qs.get('state') or ['open'])[0]).strip()
    limit_raw=str((qs.get('limit') or ['20'])[0]).strip()
    if not SLUG_RE.fullmatch(slug) or state not in {'open','closed','all'}:
        return json_response(handler,400,{'ok':False,'error':'invalid_query'})
    try:limit=int(limit_raw)
    except Exception:return json_response(handler,400,{'ok':False,'error':'invalid_query'})
    if not (1<=limit<=50):return json_response(handler,400,{'ok':False,'error':'invalid_query'})
    project=load_project(slug)
    if not project:return json_response(handler,404,{'ok':False,'error':'project_not_found'})
    owner,repo=_proposal_repo(project,slug)
    qowner=urllib.parse.quote(owner,safe='');qrepo=urllib.parse.quote(repo,safe='')
    query=urllib.parse.urlencode({'state':state,'limit':limit,'page':1})
    upstream=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/pulls?{query}')
    if not upstream.get('ok'):
        return json_response(handler,502,{'ok':False,'error':'forgejo_unavailable','upstream_status':upstream.get('status')})
    rows=[]
    for pr in (upstream.get('data') or [])[:limit]:
        rows.append({
            'number':pr.get('number'),'title':pr.get('title'),'state':pr.get('state'),
            'draft':bool(pr.get('draft')),'head':(pr.get('head') or {}).get('ref'),
            'base':(pr.get('base') or {}).get('ref'),'author':(pr.get('user') or {}).get('login'),
            'created_at':pr.get('created_at'),'updated_at':pr.get('updated_at'),
            'html_url':pr.get('html_url'),'mergeable':pr.get('mergeable'),
        })
    return json_response(handler,200,{'ok':True,'project_slug':slug,'repo':f'{owner}/{repo}','state':state,'count':len(rows),'proposals':rows,'read_only':True})

def _proposal_number(data):
    try:n=int(data.get('number'))
    except Exception:raise ValueError('invalid_number')
    if not (1<=n<=2147483647):raise ValueError('invalid_number')
    return n

def _proposal_detail(slug, number):
    project=load_project(slug)
    if not project:return None,None,None,{'ok':False,'status':404,'error':'project_not_found'}
    owner,repo=_proposal_repo(project,slug)
    qo=urllib.parse.quote(owner,safe='');qr=urllib.parse.quote(repo,safe='')
    r=_proposal_api('GET',f'/repos/{qo}/{qr}/pulls/{number}')
    if not r.get('ok'):
        return owner,repo,None,{'ok':False,'status':404 if r.get('status')==404 else 502,'error':'proposal_not_found' if r.get('status')==404 else 'forgejo_unavailable'}
    return owner,repo,r.get('data') or {},None

def _controlled_pr(pr):
    head_obj=pr.get('head') or {}
    head_ref=str(head_obj.get('ref') or '')
    head_label=str(head_obj.get('label') or '')
    head=head_ref if head_ref.startswith('cloudif-proposal-') else head_label
    base=str((pr.get('base') or {}).get('ref') or '')
    return base=='main' and head.startswith('cloudif-proposal-'),head,base

def cloudif_proposal_close(handler,data):
    if set(data)!={'project_slug','number','trace_id','requested_by'}:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    slug=str(data.get('project_slug') or '').strip();trace=str(data.get('trace_id') or '').strip();requested_by=str(data.get('requested_by') or '').strip()
    if not SLUG_RE.fullmatch(slug) or not trace or not requested_by:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    try:number=_proposal_number(data)
    except ValueError:return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    owner,repo,pr,err=_proposal_detail(slug,number)
    if err:return json_response(handler,err['status'],{'ok':False,'error':err['error']})
    controlled,branch,base=_controlled_pr(pr)
    if not controlled:return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
    if pr.get('state')=='closed':
        return json_response(handler,200,{'ok':True,'project_slug':slug,'number':number,'state':'closed','branch':branch,'already_closed':True,'branch_deleted':False,'trace_id':trace})
    if pr.get('state')!='open':return json_response(handler,409,{'ok':False,'error':'proposal_not_open'})
    if not str(pr.get('title') or '').startswith('WIP: '):return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
    qo=urllib.parse.quote(owner,safe='');qr=urllib.parse.quote(repo,safe='')
    r=_proposal_api('PATCH',f'/repos/{qo}/{qr}/pulls/{number}',{'state':'closed'})
    if not r.get('ok'):return json_response(handler,502,{'ok':False,'error':'proposal_close_failed','upstream_status':r.get('status')})
    out=r.get('data') or {}
    if out.get('state')!='closed':return json_response(handler,502,{'ok':False,'error':'proposal_close_not_confirmed'})
    result={'ok':True,'project_slug':slug,'repo':f'{owner}/{repo}','number':number,'state':'closed','branch':branch,'base':base,'already_closed':False,'branch_deleted':False,'requested_by':requested_by,'trace_id':trace}
    save_event('proposal-close',slug,{**result,'time':now()})
    return json_response(handler,200,result)

def cloudif_proposal_delete_branch(handler,data):
    if set(data)!={'project_slug','number','trace_id','requested_by'}:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    slug=str(data.get('project_slug') or '').strip();trace=str(data.get('trace_id') or '').strip();requested_by=str(data.get('requested_by') or '').strip()
    if not SLUG_RE.fullmatch(slug) or not trace or not requested_by:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    try:number=_proposal_number(data)
    except ValueError:return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    owner,repo,pr,err=_proposal_detail(slug,number)
    if err:return json_response(handler,err['status'],{'ok':False,'error':err['error']})
    controlled,branch,base=_controlled_pr(pr)
    if not controlled or branch=='main':return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
    if pr.get('state')!='closed' and not bool(pr.get('merged')):
        return json_response(handler,409,{'ok':False,'error':'proposal_must_be_closed_or_merged'})
    qo=urllib.parse.quote(owner,safe='');qr=urllib.parse.quote(repo,safe='');qb=urllib.parse.quote(branch,safe='')
    existing=_proposal_api('GET',f'/repos/{qo}/{qr}/branches/{qb}')
    if existing.get('status')==404:
        return json_response(handler,200,{'ok':True,'project_slug':slug,'number':number,'branch':branch,'branch_deleted':False,'already_absent':True,'trace_id':trace})
    if not existing.get('ok'):return json_response(handler,502,{'ok':False,'error':'branch_lookup_failed','upstream_status':existing.get('status')})
    deleted=_proposal_api('DELETE',f'/repos/{qo}/{qr}/branches/{qb}')
    if not deleted.get('ok') and deleted.get('status') not in (200,204):return json_response(handler,502,{'ok':False,'error':'branch_delete_failed','upstream_status':deleted.get('status')})
    confirm=_proposal_api('GET',f'/repos/{qo}/{qr}/branches/{qb}')
    if confirm.get('status')!=404:return json_response(handler,502,{'ok':False,'error':'branch_delete_not_confirmed'})
    result={'ok':True,'project_slug':slug,'repo':f'{owner}/{repo}','number':number,'branch':branch,'base':base,'branch_deleted':True,'already_absent':False,'requested_by':requested_by,'trace_id':trace}
    save_event('proposal-branch-delete',slug,{**result,'time':now()})
    return json_response(handler,200,result)


_PROPOSAL_COMMIT_RE = re.compile(r'^[a-f0-9]{40}$')
_PROPOSAL_APPROVAL_RE = re.compile(r'^apr_[a-f0-9]{20}$')

def cloudif_proposal_action(handler, data):
    common={'project_slug','proposal_number','action','trace_id','approval_id','requested_by'}
    action=str(data.get('action') or '').strip()
    allowed=common|({'expected_head_sha'} if action=='merge' else set())
    if set(data)!=allowed:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    slug=str(data.get('project_slug') or '').strip()
    trace=str(data.get('trace_id') or '').strip()
    approval_id=str(data.get('approval_id') or '').strip()
    requested_by=str(data.get('requested_by') or '').strip()
    try:number=int(data.get('proposal_number'))
    except Exception:return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    if not SLUG_RE.fullmatch(slug) or action not in {'close','delete-branch','merge'} or number<1 or not requested_by or not trace:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    if action=='merge':
        expected=str(data.get('expected_head_sha') or '').strip()
        if not _PROPOSAL_COMMIT_RE.fullmatch(expected) or not _PROPOSAL_APPROVAL_RE.fullmatch(approval_id):
            return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    elif not approval_id:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    project=load_project(slug)
    if not project:return json_response(handler,404,{'ok':False,'error':'project_not_found'})
    owner,repo=_proposal_repo(project,slug)
    qowner=urllib.parse.quote(owner,safe='');qrepo=urllib.parse.quote(repo,safe='')
    prr=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/pulls/{number}')
    if not prr.get('ok'):
        return json_response(handler,404 if prr.get('status')==404 else 502,{'ok':False,'error':'proposal_not_found' if prr.get('status')==404 else 'forgejo_unavailable'})
    pr=prr.get('data') or {}
    controlled,head,base=_controlled_pr(pr)
    state=str(pr.get('state') or '')
    draft=bool(pr.get('draft'))
    merged=bool(pr.get('merged'))
    if not controlled:
        return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
    qbranch=urllib.parse.quote(head,safe='')
    event={'project_slug':slug,'proposal_number':number,'action':action,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace,'repo':f'{owner}/{repo}','head':head,'base':base,'time':now()}
    if action=='close':
        if state=='closed':
            return json_response(handler,200,{'ok':True,'action':'close','project_slug':slug,'proposal_number':number,'state':'closed','draft':draft,'head':head,'base':base,'already_closed':True,'branch_deleted':False,'main_modified':False,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace})
        if state!='open' or merged:
            return json_response(handler,409,{'ok':False,'error':'proposal_not_open'})
        if not str(pr.get('title') or '').startswith('WIP: '):return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
        changed=_proposal_api('PATCH',f'/repos/{qowner}/{qrepo}/pulls/{number}',{'state':'closed'})
        if not changed.get('ok'):
            return json_response(handler,502,{'ok':False,'error':'proposal_close_failed','upstream_status':changed.get('status')})
        out=changed.get('data') or {}
        result={'ok':True,'action':'close','project_slug':slug,'proposal_number':number,'state':out.get('state'),'draft':bool(out.get('draft')),'head':head,'base':base,'already_closed':False,'branch_deleted':False,'main_modified':False,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace}
    elif action=='delete-branch':
        if state=='open' and not merged:
            return json_response(handler,409,{'ok':False,'error':'proposal_still_open'})
        existing=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/branches/{qbranch}')
        if existing.get('status')==404:
            return json_response(handler,200,{'ok':True,'action':'delete-branch','project_slug':slug,'proposal_number':number,'state':state,'draft':draft,'head':head,'base':base,'branch_deleted':False,'already_absent':True,'main_modified':False,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace})
        if not existing.get('ok'):
            return json_response(handler,502,{'ok':False,'error':'branch_lookup_failed','upstream_status':existing.get('status')})
        deleted=_proposal_api('DELETE',f'/repos/{qowner}/{qrepo}/branches/{qbranch}')
        if not deleted.get('ok') and deleted.get('status') not in (200,204):
            return json_response(handler,502,{'ok':False,'error':'branch_delete_failed','upstream_status':deleted.get('status')})
        verify=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/branches/{qbranch}')
        if verify.get('status')!=404:
            return json_response(handler,502,{'ok':False,'error':'branch_delete_not_confirmed'})
        result={'ok':True,'action':'delete-branch','project_slug':slug,'proposal_number':number,'state':state,'draft':draft,'head':head,'base':base,'branch_deleted':True,'already_absent':False,'main_modified':False,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace}
    else:
        expected=str(data.get('expected_head_sha') or '')
        head_sha=str((pr.get('head') or {}).get('sha') or '')
        if not hmac.compare_digest(head_sha,expected):
            return json_response(handler,409,{'ok':False,'error':'head_sha_mismatch','actual_head_sha':head_sha})
        if merged:
            return json_response(handler,200,{'ok':True,'action':'merge','project_slug':slug,'proposal_number':number,'state':'closed','merged':True,'already_merged':True,'draft':draft,'head':head,'base':base,'head_sha':head_sha,'branch_deleted':False,'main_modified':True,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace})
        if state!='open':return json_response(handler,409,{'ok':False,'error':'proposal_not_open'})
        if not draft:return json_response(handler,409,{'ok':False,'error':'proposal_not_draft'})
        original_title=str(pr.get('title') or '')
        if not original_title.startswith('WIP: '):return json_response(handler,409,{'ok':False,'error':'proposal_not_controlled'})
        ready_title=original_title[5:].strip() if original_title.startswith('WIP: ') else original_title
        updated=_proposal_api('PATCH',f'/repos/{qowner}/{qrepo}/pulls/{number}',{'title':ready_title})
        ready=updated.get('data') or {}
        if not updated.get('ok') or bool(ready.get('draft')) or ready.get('state')!='open':
            _proposal_api('PATCH',f'/repos/{qowner}/{qrepo}/pulls/{number}',{'title':original_title})
            return json_response(handler,502,{'ok':False,'error':'proposal_ready_failed','upstream_status':updated.get('status')})
        merged_res=_proposal_api('POST',f'/repos/{qowner}/{qrepo}/pulls/{number}/merge',{'Do':'merge','head_commit_id':expected,'delete_branch_after_merge':False,'force_merge':False,'merge_when_checks_succeed':False},timeout=60)
        if not merged_res.get('ok'):
            _proposal_api('PATCH',f'/repos/{qowner}/{qrepo}/pulls/{number}',{'title':original_title})
            return json_response(handler,409 if merged_res.get('status') in {405,409,423} else 502,{'ok':False,'error':'proposal_merge_failed','upstream_status':merged_res.get('status'),'draft_restored':True})
        merged_check=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/pulls/{number}/merge')
        detail=_proposal_api('GET',f'/repos/{qowner}/{qrepo}/pulls/{number}')
        vpr=detail.get('data') or {}
        if merged_check.get('status')!=204 or not detail.get('ok') or not bool(vpr.get('merged')) or vpr.get('state')!='closed':
            return json_response(handler,502,{'ok':False,'error':'proposal_merge_not_confirmed'})
        result={'ok':True,'action':'merge','project_slug':slug,'proposal_number':number,'state':'closed','merged':True,'already_merged':False,'merged_at':vpr.get('merged_at'),'draft':bool(vpr.get('draft')),'head':head,'base':base,'head_sha':head_sha,'merge_commit_sha':str(vpr.get('merge_commit_sha') or ''),'branch_deleted':False,'main_modified':True,'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace}
    save_event('proposal-action',slug,{**event,'result':result})
    return json_response(handler,200,result)

def cloudif_proposal_merge_route(handler,data):
    expected={'project_slug','number','expected_head_sha','approval_id','requested_by','trace_id'}
    if set(data)!=expected:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    normalized={'project_slug':data['project_slug'],'proposal_number':data['number'],'action':'merge','expected_head_sha':data['expected_head_sha'],'approval_id':data['approval_id'],'requested_by':data['requested_by'],'trace_id':data['trace_id']}
    return cloudif_proposal_action(handler,normalized)


def cloudif_proposal_create(handler, data):
    allowed={'project_slug','base_branch','path','expected_sha256','find','replace','title','body','trace_id','approval_id','requested_by'}
    if set(data)-allowed:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    slug=str(data.get('project_slug') or '').strip();base=str(data.get('base_branch') or 'main').strip();path=str(data.get('path') or '').strip();expected=str(data.get('expected_sha256') or '').strip();find_text=str(data.get('find') or '');replace_text=str(data.get('replace') or '');title=str(data.get('title') or '').strip();body=str(data.get('body') or '').strip();trace=str(data.get('trace_id') or '').strip();approval_id=str(data.get('approval_id') or '').strip();requested_by=str(data.get('requested_by') or '').strip()
    if not SLUG_RE.fullmatch(slug) or base!='main' or not _PROPOSAL_PATH_RE.fullmatch(path) or not _PROPOSAL_SHA_RE.fullmatch(expected):
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    if not (1<=len(find_text)<=512) or len(replace_text)>1024 or not (4<=len(title)<=160) or len(body)>4000 or not approval_id or not requested_by:
        return json_response(handler,400,{'ok':False,'error':'invalid_request'})
    project=load_project(slug)
    if not project:return json_response(handler,404,{'ok':False,'error':'project_not_found'})
    owner,repo=_proposal_repo(project,slug)
    before=_v118_get_file(owner,repo,path,base)
    if not before.get('exists'):return json_response(handler,404,{'ok':False,'error':'file_not_found'})
    content=str(before.get('content') or '');actual=hashlib.sha256(content.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(actual,expected):return json_response(handler,409,{'ok':False,'error':'hash_mismatch','actual_sha256':actual})
    if content.count(find_text)!=1:return json_response(handler,409,{'ok':False,'error':'match_count'})
    updated=content.replace(find_text,replace_text,1);after_sha=hashlib.sha256(updated.encode('utf-8')).hexdigest()
    branch='cloudif-proposal-'+hashlib.sha256((slug+path+expected+trace+secrets.token_hex(8)).encode()).hexdigest()[:20]
    qowner=urllib.parse.quote(owner,safe='');qrepo=urllib.parse.quote(repo,safe='');qbranch=urllib.parse.quote(branch,safe='')
    created=False;pr=None
    try:
        b=_proposal_api('POST',f'/repos/{qowner}/{qrepo}/branches',{'new_branch_name':branch,'old_branch_name':base})
        if not b.get('ok'):return json_response(handler,502,{'ok':False,'error':'branch_create_failed','upstream_status':b.get('status')})
        created=True
        st,commit=_v118_put_file(owner,repo,path,branch,updated,'CloudIF: proposta '+title,sha=before.get('sha') or '')
        if st not in (200,201):raise RuntimeError('commit_failed')
        draft_title=title if title.startswith('WIP: ') else 'WIP: '+title
        prr=_proposal_api('POST',f'/repos/{qowner}/{qrepo}/pulls',{'base':base,'head':branch,'title':draft_title,'body':body,'draft':True})
        if not prr.get('ok'):raise RuntimeError('pull_request_failed')
        pr=prr.get('data') or {}
        if not bool(pr.get('draft')):raise RuntimeError('draft_not_confirmed')
        result={'ok':True,'project_slug':slug,'repo':f'{owner}/{repo}','base_branch':base,'branch':branch,'path':path,'before_sha256':actual,'after_sha256':after_sha,'commit_sha':((commit.get('commit') or {}).get('sha') if isinstance(commit,dict) else '') or '', 'pull_request':{'number':pr.get('number'),'title':pr.get('title'),'draft':bool(pr.get('draft')),'state':pr.get('state'),'html_url':pr.get('html_url')},'approval_id':approval_id,'requested_by':requested_by,'trace_id':trace,'main_modified':False}
        save_event('proposal',slug,{**result,'time':now()})
        return json_response(handler,201,result)
    except Exception as e:
        if created and not pr:
            _proposal_api('DELETE',f'/repos/{qowner}/{qrepo}/branches/{qbranch}')
        return json_response(handler,502,{'ok':False,'error':str(e)[:120],'branch_cleaned':created and not pr})


class Handler(BaseHTTPRequestHandler):

    def authorized(self):

        ok, reason = _cloudif_v110_auth_result(self)

        return ok


    def do_HEAD(self):
        if self.path.startswith("/health"):
            return json_response(self, 200, {"ok": True, "service": "cloudif-forja-agent-v4"})
        return json_response(self, 404, {"ok": False})

    def do_GET(self):

        _cloudif_v121_path = self.path.split("?", 1)[0]
        if _cloudif_v121_path == "/project/file/debug":
            return cloudif_v121_file_debug(self)


        _cloudif_v118_path = self.path.split("?", 1)[0]
        if _cloudif_v118_path == "/project/file/history":
            return cloudif_v118_file_history(self)

        path = self.path.split('?', 1)[0]

        _cloudif_v109_path = self.path.split("?", 1)[0]
        # CloudIF v114 do_POST webhook preauth
        _cloudif_v114_webhook_request = _cloudif_v114_is_webhook_path(self.path)
        if _cloudif_v109_path == "/auth/debug":
            return _cloudif_v109_send_debug(self)

        # CloudIF v47d: autenticação padronizada por FORJA_AGENT_TOKEN
        if self.path in ["/status", "/project/ensure"] or self.path.startswith("/project/") :
            if not (_cloudif_v114_is_webhook_path(self.path) or cloudif_auth_ok(self)):
                return cloudif_send_json(self, 403, {"ok": False, "error": "invalid_token"})

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/project/archive":
            return cloudif_workspace_archive(self, qs)

        if parsed.path == "/project/proposals":
            return cloudif_proposal_list(self, qs)

        if parsed.path == "/health":
            return json_response(self, 200, {"ok": True, "service": "cloudif-forja-agent-v4", "time": now()})

        if not (_cloudif_v114_is_webhook_path(self.path) or self.authorized()):
            return json_response(self, 403, {"ok": False, "error": "invalid_token"})

        if parsed.path == "/status":
            return json_response(self, 200, {"ok": True, "forgejo": forgejo_status(), "komodo": komodo_status()})

        if parsed.path == "/projects":
            return json_response(self, 200, {"ok": True, "projects": list_projects()})

        if parsed.path == "/project/status":
            slug = qs.get("slug", [""])[0]
            project = load_project(slug)
            return json_response(self, 200 if project else 404, {"ok": bool(project), "project": project})

        return json_response(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self):

        _cloudif_v118_path = self.path.split("?", 1)[0]
        if _cloudif_v118_path == "/project/file/commit":
            return cloudif_v121_file_commit_safe(self)
        if _cloudif_v118_path == "/project/file/rollback":
            return cloudif_v121_file_rollback_safe(self)


        _cloudif_v117_path = self.path.split("?", 1)[0]
        if _cloudif_v117_path == "/project/rollback":
            return cloudif_v117_project_rollback(self)

        path = self.path.split('?', 1)[0]
        # CloudIF v47d: autenticação padronizada por FORJA_AGENT_TOKEN
        if self.path in ["/status", "/project/ensure"] or self.path.startswith("/project/") :
            if not (_cloudif_v114_is_webhook_path(self.path) or cloudif_auth_ok(self)):
                return cloudif_send_json(self, 403, {"ok": False, "error": "invalid_token"})

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"

        if path.startswith("/webhook/forgejo/"):
            slug = path.rsplit("/", 1)[-1]
            project = load_project(slug)
            if not project:
                return json_response(self, 404, {"ok": False, "error": "project_not_found"})
            if not _cloudif_forgejo_signature_ok(project, raw, self.headers):
                return json_response(self, 403, {"ok": False, "error": "invalid_webhook_signature"})
            try:
                webhook_body = json.loads(raw.decode("utf-8", "ignore") or "{}")
            except Exception:
                return json_response(self, 400, {"ok": False, "error": "invalid_webhook_json"})
            event = self.headers.get("X-Forgejo-Event") or self.headers.get("X-Gitea-Event") or "unknown"
            delivery = self.headers.get("X-Forgejo-Delivery") or self.headers.get("X-Gitea-Delivery") or ""
            save_event("forgejo", slug, {"headers": {"event": event, "delivery": delivery}, "body": raw.decode("utf-8", "ignore")[:5000], "time": now(), "signature_verified": True})
            project["last_forgejo_event_at"] = now()
            project["last_forgejo_event"] = event
            project["last_forgejo_delivery"] = delivery
            project["last_forgejo_signature_verified"] = True
            save_project(project)
            is_main_push = event == "push" and str(webhook_body.get("ref") or "") == "refs/heads/main"
            if is_main_push:
                threading.Thread(target=_cloudif_forgejo_push_worker, args=(slug, delivery, webhook_body), daemon=True).start()
                return json_response(self, 202, {"ok": True, "queued": True, "message": "Push validado; deploy automático enfileirado."})
            return json_response(self, 200, {"ok": True, "queued": False, "message": "Evento validado; nenhuma implantação necessária."})

        if path.startswith("/webhook/komodo/"):
            slug = path.rsplit("/", 1)[-1]
            qs = urllib.parse.parse_qs(parsed.query)
            project = load_project(slug)
            if not project:
                return json_response(self, 404, {"ok": False, "error": "project_not_found"})
            got = qs.get("token", [""])[0] or self.headers.get("X-CloudIF-Komodo-Token", "")
            expected = project.get("komodo_webhook_token", "")
            if not expected or not hmac.compare_digest(got, expected):
                return json_response(self, 403, {"ok": False, "error": "invalid_project_token"})
            save_event("komodo", slug, {"headers": dict(self.headers), "body": raw.decode("utf-8", "ignore")[:5000], "time": now()})
            project["last_komodo_event_at"] = now()
            project["komodo_runtime_status"] = "event-received"
            save_project(project)
            return json_response(self, 200, {"ok": True, "message": "Evento Komodo recebido."})

        if not (_cloudif_v114_is_webhook_path(self.path) or self.authorized()):
            return json_response(self, 403, {"ok": False, "error": "invalid_token"})

        try:
            data = json.loads(raw.decode() or "{}")
        except Exception as e:
            return json_response(self, 400, {"ok": False, "error": "invalid_json", "detail": str(e)})

        if path == "/project/proposal/merge":
            return cloudif_proposal_merge_route(self, data)
        if path == "/project/proposal/close":
            return cloudif_proposal_close(self, data)
        if path == "/project/proposal/delete-branch":
            return cloudif_proposal_delete_branch(self, data)
        if path == "/project/proposal/create":
            return cloudif_proposal_create(self, data)

        if path == "/project/proposal/action":
            return cloudif_proposal_action(self, data)

        if path == "/project/release/prepare":
            code, result = prepare_project_release(data)
            return json_response(self, code, result)

        if path == "/project/release/finalize":
            code, result = finalize_project_release(data)
            return json_response(self, code, result)

        if path == "/project/membership/reconcile":
            result=reconcile_project_membership(data)
            return json_response(self, 200 if result.get("ok") else 422, result)

        if path == "/project/ensure":
            return json_response(self, 200, ensure_project(data))

        if path == "/forgejo/ensure-repo":
            data["forgejo"] = ensure_forgejo_repo(data)
            data["forgejo_webhook"] = ensure_forgejo_webhook(data) if data["forgejo"].get("ok") else {"ok": False}
            saved = save_project(data)
            return json_response(self, 200, {"ok": bool(data["forgejo"].get("ok")), "project": saved})

        if path == "/forgejo/ensure-webhook":
            data["forgejo_webhook"] = ensure_forgejo_webhook(data)
            saved = save_project(data)
            return json_response(self, 200, {"ok": bool(data["forgejo_webhook"].get("ok")), "project": saved})

        if path == "/komodo/ensure-webhook":
            data["komodo_webhook"] = ensure_komodo_project_webhook(data)
            saved = save_project(data)
            return json_response(self, 200, {"ok": bool(data["komodo_webhook"].get("ok")), "project": saved})

        if path == "/komodo/trigger":
            data["komodo_trigger"] = trigger_komodo(data)
            saved = save_project(data)
            return json_response(self, 200, {"ok": bool(data["komodo_trigger"].get("ok")), "project": saved})

        return json_response(self, 404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        print(f"[{now()}] {self.client_address[0]} {fmt % args}", flush=True)

# CloudIFF v143 — colaboradores do Forgejo reconciliados pela ACL central

def reconcile_project_membership(payload):
    slug=safe_slug(payload.get('project') or payload.get('project_slug') or payload.get('slug') or '')
    if not slug:return {'ok':False,'error':'invalid_project'}
    project=load_project(slug) or {}
    access=payload.get('access') if isinstance(payload.get('access'),dict) else {}
    owner=str(access.get('owner') or payload.get('owner_user') or project.get('owner_user') or project.get('forgejo_owner') or ((project.get('forgejo') or {}).get('owner') if isinstance(project.get('forgejo'),dict) else '') or '').strip().lower()
    repo=str(payload.get('repo') or ((project.get('forgejo') or {}).get('repo') if isinstance(project.get('forgejo'),dict) else '') or forgejo_repo_name(slug)).strip()
    if '/' in repo:
        repo_owner,repo_name=repo.split('/',1);owner=owner or repo_owner;repo=repo_name
    if not owner:return {'ok':False,'error':'repo_owner_missing'}
    acl=access.get('acl') if isinstance(access.get('acl'),list) else []
    desired=set()
    ignored_groups=[]
    for item in acl:
        kind=str(item.get('type') or '').strip().lower();subject=str(item.get('subject') or '').strip().lower()
        if kind=='user' and subject and subject!=owner:desired.add(subject)
        elif kind=='group' and subject:ignored_groups.append(subject)
    previous={str(x).strip().lower() for x in (project.get('managed_collaborators') or []) if str(x).strip()}
    base=forgejo_api_base();token=CFG.get('FORGEJO_TOKEN','')
    if not base or not token:return {'ok':False,'error':'forgejo_credentials_missing'}
    qowner=urllib.parse.quote(owner,safe='');qrepo=urllib.parse.quote(repo,safe='')
    added=[];existing=[];removed=[];errors=[]
    for username in sorted(desired):
        quser=urllib.parse.quote(username,safe='')
        check=http_json('GET',f'{base}/repos/{qowner}/{qrepo}/collaborators/{quser}',token=token,timeout=15)
        if check.get('ok'):
            existing.append(username);continue
        result=http_json('PUT',f'{base}/repos/{qowner}/{qrepo}/collaborators/{quser}',token=token,payload={'permission':'write'},timeout=20)
        if result.get('ok'):added.append(username)
        else:errors.append({'username':username,'operation':'add','status':result.get('status'),'detail':result.get('data') or result.get('error')})
    for username in sorted(previous-desired):
        quser=urllib.parse.quote(username,safe='')
        result=http_json('DELETE',f'{base}/repos/{qowner}/{qrepo}/collaborators/{quser}',token=token,timeout=20)
        if result.get('ok') or result.get('status')==404:removed.append(username)
        else:errors.append({'username':username,'operation':'remove','status':result.get('status'),'detail':result.get('data') or result.get('error')})
    if not errors:
        project.update({'project_slug':slug,'owner_user':owner,'forgejo_owner':owner,'managed_collaborators':sorted(desired),'membership_reconciled_at':now()})
        save_project(project)
    return {'ok':not errors,'project':slug,'repo':owner+'/'+repo,'owner':owner,'desired_users':sorted(desired),'added':added,'existing':existing,'removed':removed,'ignored_groups':ignored_groups,'errors':errors}
# CloudIFF v143 END


if __name__ == "__main__":
    print(f"[{now()}] CloudIF Forja Agent v4 ouvindo em {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
