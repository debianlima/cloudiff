#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LOG = Path("/var/log/cloudif/project-provision.log")
BASE = Path("/srv/cloudif/provisioning/projects")
ENV_FILES = [
    "/etc/cloudif/forja-agent-client.env",
    "/etc/cloudif/provision.env",
    "/etc/default/cloudif-admin-portal",
    "/srv/cloudif/provision.env",
    "/srv/cloudif/config/provision.env",
    "/root/cloudif-provision.env",
]

def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + " " + str(msg) + "\n")

def load_env_files():
    for path in ENV_FILES:
        p = Path(path)
        if not p.exists():
            continue
        for raw in p.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and (k not in os.environ or not str(os.environ.get(k) or '').strip()):
                os.environ[k] = v

def env(k, default=""):
    return os.environ.get(k, default)

def slugify(v, dash=True):
    v = str(v or "").strip().lower()
    v = (
        v.replace("á","a").replace("à","a").replace("ã","a").replace("â","a")
         .replace("é","e").replace("ê","e")
         .replace("í","i")
         .replace("ó","o").replace("õ","o").replace("ô","o")
         .replace("ú","u")
         .replace("ç","c")
    )
    if dash:
        v = re.sub(r"[^a-z0-9]+", "-", v).strip("-")
    else:
        v = re.sub(r"[^a-z0-9]+", "", v)
    return v or "projeto"

def run(cmd, input_text=None, timeout=180):
    log("RUN " + " ".join(cmd))
    try:
        p = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if p.stdout:
            log("STDOUT " + p.stdout[-3000:])
        if p.stderr:
            log("STDERR " + p.stderr[-3000:])
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        log("TIMEOUT " + " ".join(cmd))
        return 124, "", "timeout"
    except Exception as e:
        log("ERROR " + repr(e))
        return 999, "", repr(e)

def http_json(method, url, token="", data=None, extra_headers=None, timeout=30):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    if extra_headers:
        headers.update(extra_headers)

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            return r.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed, raw
    except Exception as e:
        return 0, {"error": str(e)}, str(e)

PORTAL_DB = "/var/lib/cloudif/portal/cloudif-portal.db"

def _cloudif_project_access(slug, job=None):
    owner=''; acl=[]
    try:
        c=sqlite3.connect(PORTAL_DB);c.row_factory=sqlite3.Row
        row=c.execute('select owner from projects where slug=?',(slug,)).fetchone()
        if row: owner=str(row['owner'] or '').strip().lower()
        acl=[{'type':str(r['subject_type'] or ''),'subject':str(r['subject'] or '').strip()} for r in c.execute('select subject_type,subject from project_acl where slug=?',(slug,)).fetchall() if str(r['subject'] or '').strip()]
        c.close()
    except Exception: pass
    user=(job or {}).get('user') if isinstance((job or {}).get('user'),dict) else {}
    owner=owner or str((job or {}).get('owner') or user.get('username') or (job or {}).get('requested_by') or '').strip().lower()
    if not owner: raise RuntimeError('project_owner_missing')
    return {'owner':owner,'acl':acl}

def report_init(job):
    slug = slugify(job.get("slug") or job.get("name"))
    d = BASE / slug
    d.mkdir(parents=True, exist_ok=True)
    return {
        "ok": False,
        "slug": slug,
        "tenant": job.get("tenant") or "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "finished_at": "",
        "components": {
            "forgejo": {"ok": False, "status": "pending", "actions": []},
            "komodo": {"ok": False, "status": "pending", "actions": []},
            "supabase": {"ok": False, "status": "pending", "actions": []},
        },
        "files": {},
        "errors": [],
    }

def save_report(report):
    slug = report["slug"]
    d = BASE / slug
    d.mkdir(parents=True, exist_ok=True)
    path = d / "provision-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def forgejo(job, report):
    comp = report["components"]["forgejo"]
    url = env("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    org = env("FORGEJO_ORG", "cloudif").strip() or "cloudif"
    token = env("FORGEJO_TOKEN") or env("GITEA_TOKEN")
    slug = report["slug"]

    repo_url = f"{url}/{org}/{slug}"
    comp["url"] = repo_url
    comp["organization"] = org
    comp["repository"] = slug

    if not token:
        comp["status"] = "missing_token"
        comp["actions"].append({
            "name": "forgejo_repository",
            "ok": False,
            "message": "FORGEJO_TOKEN vazio. Repositório não foi criado.",
        })
        return

    api = url + "/api/v1"

    st, data, raw = http_json("GET", f"{api}/repos/{urllib.parse.quote(org)}/{urllib.parse.quote(slug)}", token=token)

    if st == 200:
        comp["actions"].append({"name": "forgejo_repository", "ok": True, "message": "Repositório já existia."})
    elif st == 404:
        payload = {
            "name": slug,
            "description": job.get("description") or f"Projeto CloudIF {slug}",
            "private": True,
            "auto_init": True,
        }

        st2, data2, raw2 = http_json("POST", f"{api}/orgs/{urllib.parse.quote(org)}/repos", token=token, data=payload)

        if st2 not in [200, 201]:
            # fallback: cria no usuário do token
            st2, data2, raw2 = http_json("POST", f"{api}/user/repos", token=token, data=payload)

        if st2 in [200, 201]:
            repo_url = data2.get("html_url") or repo_url
            comp["url"] = repo_url
            comp["actions"].append({"name": "forgejo_repository", "ok": True, "message": "Repositório criado.", "status": st2})
        else:
            comp["status"] = "error"
            comp["actions"].append({
                "name": "forgejo_repository",
                "ok": False,
                "status": st2,
                "message": "Falha ao criar repositório.",
                "detail": data2,
            })
            return
    else:
        comp["status"] = "error"
        comp["actions"].append({
            "name": "forgejo_repository_check",
            "ok": False,
            "status": st,
            "message": "Falha ao consultar repositório.",
            "detail": data,
        })
        return

    webhook_url = (
        env("CLOUDIF_DEPLOY_WEBHOOK_URL")
        or env("FORGEJO_WEBHOOK_URL")
        or ""
    )

    if not webhook_url:
        comp["actions"].append({
            "name": "cloudif-forgejo-push",
            "ok": False,
            "message": "URL de webhook não configurada. Defina CLOUDIF_DEPLOY_WEBHOOK_URL.",
        })
    else:
        hook_payload = {
            "type": "gitea",
            "config": {
                "url": webhook_url,
                "content_type": "json",
            },
            "events": ["push", "create", "release"],
            "active": True,
        }

        st3, data3, raw3 = http_json("POST", f"{api}/repos/{urllib.parse.quote(org)}/{urllib.parse.quote(slug)}/hooks", token=token, data=hook_payload)

        if st3 in [200, 201]:
            comp["actions"].append({
                "name": "cloudif-forgejo-push",
                "ok": True,
                "message": "Webhook Git criado.",
                "url": webhook_url,
            })
        elif st3 == 409:
            comp["actions"].append({
                "name": "cloudif-forgejo-push",
                "ok": True,
                "message": "Webhook Git já existia.",
                "url": webhook_url,
            })
        else:
            comp["actions"].append({
                "name": "cloudif-forgejo-push",
                "ok": False,
                "status": st3,
                "message": "Falha ao criar webhook Git.",
                "detail": data3,
            })

    comp["status"] = "done"
    comp["ok"] = any(a.get("ok") for a in comp["actions"] if a.get("name") == "forgejo_repository")



# CloudIF v100 — integração via Forja Agent, antes do fallback FORGEJO_TOKEN local

def _v100_forja_agent_request(job, report):
    agent_url = env("FORJA_AGENT_URL", "http://10.62.91.2:18095").rstrip("/")
    token = env("FORJA_AGENT_TOKEN", "")
    slug = report["slug"]
    tenant = report.get("tenant") or ""

    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])

    if not token:
        comp["actions"].append({
            "name": "forja_agent_auth",
            "ok": False,
            "message": "FORJA_AGENT_TOKEN vazio. Agent não foi usado.",
        })
        return False

    headers = {
        "X-CloudIF-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "action": "provision_project",
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant,
        "forgejo_org": env("FORGEJO_ORG", "cloudif"),
        "repo": slug,
        "create_repo": True,
        "ensure_webhook": True,
        "webhook_url": env("CLOUDIF_DEPLOY_WEBHOOK_URL", ""),
        "user": job.get("user") or {},
        "komodo": {
            "url": env("KOMODO_URL", "https://komodoiff.duckdns.org"),
            "containers": [
                f"{slug}-app",
                f"{slug}-worker",
                f"{slug}-proxy",
            ] + ([f"{tenant}-supabase"] if tenant else []),
        },
    }

    endpoints = [
        "/api/project/provision",
        "/api/projects/provision",
        "/api/forgejo/project",
        "/api/forgejo/repository",
        "/project/provision",
        "/projects/provision",
        "/forgejo/repository",
        "/provision",
    ]

    for ep in endpoints:
        st, data, raw = http_json(
            "POST",
            agent_url + ep,
            token="",
            data=payload,
            extra_headers=headers,
            timeout=35,
        )

        if st in [200, 201, 202]:
            comp["status"] = "done_via_forja_agent"
            comp["ok"] = True
            comp["actions"].append({
                "name": "forja_agent_provision",
                "ok": True,
                "message": f"Forja Agent aceitou provisionamento em {ep}.",
                "endpoint": ep,
            })

            # Tenta aproveitar campos retornados pelo agent.
            if isinstance(data, dict):
                repo_url = (
                    data.get("repo_url")
                    or data.get("html_url")
                    or data.get("url")
                    or ((data.get("repository") or {}).get("html_url") if isinstance(data.get("repository"), dict) else "")
                )
                if repo_url:
                    comp["url"] = repo_url

                org = data.get("org") or data.get("organization")
                if org:
                    comp["organization"] = org

                repo_name = data.get("repo") or data.get("repository_name")
                if repo_name:
                    comp["repository"] = repo_name

                hooks = data.get("webhooks") or data.get("hooks") or []
                if hooks:
                    comp["actions"].append({
                        "name": "forja_agent_webhooks",
                        "ok": True,
                        "message": f"Forja Agent retornou {len(hooks)} webhook(s).",
                    })

            return True

        if st in [401, 403]:
            comp["actions"].append({
                "name": "forja_agent_auth",
                "ok": False,
                "message": f"Forja Agent recusou autenticação em {ep}.",
                "status": st,
            })
            return False

    comp["actions"].append({
        "name": "forja_agent_probe",
        "ok": False,
        "message": "Forja Agent respondeu, mas nenhum endpoint conhecido aceitou o provisionamento.",
        "agent_url": agent_url,
    })
    return False

_original_forgejo_v100 = forgejo

def forgejo(job, report):
    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])

    used_agent = False
    try:
        used_agent = _v100_forja_agent_request(job, report)
    except Exception as e:
        comp["actions"].append({
            "name": "forja_agent_exception",
            "ok": False,
            "message": str(e),
        })

    if used_agent:
        return

    # Fallback antigo: API direta do Forgejo via FORGEJO_TOKEN.
    return _original_forgejo_v100(job, report)




# CloudIF v101 — Forja Agent endpoint real /project/ensure

def _v101_read_env_file(path):
    data = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return data

def _v101_forja_cfg():
    # Fonte de verdade: arquivo antigo do client.
    old = _v101_read_env_file("/etc/cloudif/forja-agent-client.env")
    new = _v101_read_env_file("/etc/cloudif/provision.env")

    url = old.get("FORJA_AGENT_URL") or new.get("FORJA_AGENT_URL") or env("FORJA_AGENT_URL", "http://10.62.91.2:18095")
    token = old.get("FORJA_AGENT_TOKEN") or new.get("FORJA_AGENT_TOKEN") or env("FORJA_AGENT_TOKEN", "")

    return url.rstrip("/"), token

def _v101_forja_project_ensure(job, report):
    agent_url, token = _v101_forja_cfg()
    slug = report["slug"]
    tenant = report.get("tenant") or ""

    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])

    if not token:
        comp["actions"].append({
            "name": "forja_agent_auth",
            "ok": False,
            "message": "FORJA_AGENT_TOKEN vazio em /etc/cloudif/forja-agent-client.env e /etc/cloudif/provision.env.",
        })
        return False

    payload = {
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant,
        "forgejo_org": env("FORGEJO_ORG", "cloudif"),
        "org": env("FORGEJO_ORG", "cloudif"),
        "repo": slug,
        "repository": slug,
        "repo_name": slug,
        "create_repo": True,
        "ensure_webhook": True,
        "webhook_url": env("CLOUDIF_DEPLOY_WEBHOOK_URL", ""),
        "user": job.get("user") or {},
        "project": {
            "slug": slug,
            "name": job.get("name") or slug,
            "description": job.get("description") or "",
            "tenant": tenant,
        },
        "komodo": {
            "url": env("KOMODO_URL", "https://komodoiff.duckdns.org"),
            "containers": [
                f"{slug}-app",
                f"{slug}-worker",
                f"{slug}-proxy",
            ] + ([f"{tenant}-supabase"] if tenant else []),
        },
    }

    headers = {
        "X-CloudIF-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    st, data, raw = http_json(
        "POST",
        agent_url + "/project/ensure",
        token="",
        data=payload,
        extra_headers=headers,
        timeout=60,
    )

    if st in [200, 201, 202]:
        comp["status"] = "done_via_forja_agent"
        comp["ok"] = True
        comp["actions"].append({
            "name": "forja_agent_project_ensure",
            "ok": True,
            "message": "Forja Agent aceitou /project/ensure.",
            "endpoint": "/project/ensure",
        })

        if isinstance(data, dict):
            repo_url = (
                data.get("repo_url")
                or data.get("html_url")
                or data.get("url")
                or ((data.get("repository") or {}).get("html_url") if isinstance(data.get("repository"), dict) else "")
            )
            if repo_url:
                comp["url"] = repo_url

            org = data.get("org") or data.get("organization") or data.get("forgejo_org")
            if org:
                comp["organization"] = org

            repo_name = data.get("repo") or data.get("repository_name") or data.get("name")
            if repo_name:
                comp["repository"] = repo_name

            hooks = data.get("webhooks") or data.get("hooks") or []
            if hooks:
                comp["actions"].append({
                    "name": "forja_agent_webhooks",
                    "ok": True,
                    "message": f"Forja Agent retornou {len(hooks)} webhook(s).",
                })

            # Guarda resposta resumida no relatório.
            comp["agent_response_keys"] = sorted(list(data.keys()))[:30]

        return True

    if st in [401, 403]:
        comp["status"] = "forja_agent_auth_error"
        comp["ok"] = False
        comp["actions"].append({
            "name": "forja_agent_project_ensure",
            "ok": False,
            "status": st,
            "message": "Forja Agent recusou autenticação em /project/ensure. Token do client está inválido ou fora de sincronia.",
        })
        return False

    comp["actions"].append({
        "name": "forja_agent_project_ensure",
        "ok": False,
        "status": st,
        "message": "Forja Agent /project/ensure não aceitou o provisionamento.",
        "detail": data if isinstance(data, dict) else {},
    })
    return False

_original_forgejo_v101 = forgejo

def forgejo(job, report):
    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])
    try:
        if _v101_forja_project_ensure(job, report):
            return
    except Exception as e:
        comp["actions"].append({
            "name": "forja_agent_project_ensure_exception",
            "ok": False,
            "message": str(e),
        })
    comp["ok"] = False
    if not comp.get("status") or comp.get("status") == "pending":
        comp["status"] = "forja_agent_error"
    comp["actions"].append({
        "name": "direct_forgejo_fallback_disabled",
        "ok": False,
        "message": "Fallback direto desativado. O provisionamento usa exclusivamente o Forja Agent.",
    })




# CloudIF v111 — slug compatível com Forja Agent /project/ensure
def _v111_project_slug(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "projeto"

_original_v111_forja_project_ensure = _v101_forja_project_ensure if "_v101_forja_project_ensure" in globals() else None

def _v101_forja_project_ensure(job, report):
    agent_url, token = _v101_forja_cfg()
    slug = _v111_project_slug(report["slug"])
    tenant = report.get("tenant") or ""

    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])

    if not token:
        comp["actions"].append({
            "name": "forja_agent_auth",
            "ok": False,
            "message": "FORJA_AGENT_TOKEN vazio em /etc/cloudif/forja-agent-client.env e /etc/cloudif/provision.env.",
        })
        return False

    payload = {
        "project_slug": slug,
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant,
        "forgejo_org": env("FORGEJO_ORG", "cloudif"),
        "org": env("FORGEJO_ORG", "cloudif"),
        "repo": slug,
        "repository": slug,
        "repo_name": slug,
        "create_repo": True,
        "ensure_webhook": True,
        "webhook_url": env("CLOUDIF_DEPLOY_WEBHOOK_URL", ""),
        "user": job.get("user") or {},
        "project": {
            "project_slug": slug,
            "slug": slug,
            "name": job.get("name") or slug,
            "description": job.get("description") or "",
            "tenant": tenant,
        },
        "komodo": {
            "url": env("KOMODO_URL", "https://komodoiff.duckdns.org"),
            "containers": [
                f"{slug}-app",
                f"{slug}-worker",
                f"{slug}-proxy",
            ] + ([f"{tenant}-supabase"] if tenant else []),
        },
    }

    headers = {
        "X-CloudIF-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    st, data, raw = http_json(
        "POST",
        agent_url + "/project/ensure",
        token="",
        data=payload,
        extra_headers=headers,
        timeout=60,
    )

    if st in [200, 201, 202] and isinstance(data, dict) and data.get("ok") is not False:
        comp["status"] = "done_via_forja_agent"
        comp["ok"] = True
        comp["actions"].append({
            "name": "forja_agent_project_ensure",
            "ok": True,
            "message": "Forja Agent aceitou /project/ensure.",
            "endpoint": "/project/ensure",
        })

        repo_url = (
            data.get("repo_url")
            or data.get("html_url")
            or data.get("url")
            or ((data.get("repository") or {}).get("html_url") if isinstance(data.get("repository"), dict) else "")
        )
        if repo_url:
            comp["url"] = repo_url

        comp["agent_response_keys"] = sorted(list(data.keys()))[:30]
        return True

    if st in [401, 403]:
        comp["status"] = "forja_agent_auth_error"
        comp["ok"] = False
        comp["actions"].append({
            "name": "forja_agent_project_ensure",
            "ok": False,
            "status": st,
            "message": "Forja Agent recusou autenticação em /project/ensure.",
        })
        return False

    comp["actions"].append({
        "name": "forja_agent_project_ensure",
        "ok": False,
        "status": st,
        "message": "Forja Agent /project/ensure não aceitou o provisionamento.",
        "detail": data if isinstance(data, dict) else {},
    })
    return False




# CloudIF v115 — padrão canônico de repo Forgejo: cloudif-<project_slug>
def _v115_project_slug(value):
    import re
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "projeto"

def _v115_repo_name(slug):
    slug = _v115_project_slug(slug)
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def _v115_repo_path(slug, owner="cloudif"):
    return str(owner or "cloudif") + "/" + _v115_repo_name(slug)

def _v115_repo_url(slug, owner="cloudif"):
    return "https://cloudiff.duckdns.org/git/" + _v115_repo_path(slug, owner)

def _v115_repo_clone_url(slug, owner="cloudif"):
    return _v115_repo_url(slug, owner) + ".git"

def _v101_forja_project_ensure(job, report):
    agent_url, token = _v101_forja_cfg()

    slug = _v115_project_slug(report["slug"])
    access = _cloudif_project_access(slug, job)
    owner = access["owner"]
    repo_name = _v115_repo_name(slug)
    repo_path = _v115_repo_path(slug, owner)
    repo_url = _v115_repo_url(slug, owner)
    tenant = report.get("tenant") or ""

    comp = report["components"]["forgejo"]
    comp.setdefault("actions", [])

    if not token:
        comp["status"] = "forja_agent_missing_token"
        comp["ok"] = False
        comp["actions"].append({
            "name": "forja_agent_auth",
            "ok": False,
            "message": "FORJA_AGENT_TOKEN vazio em /etc/cloudif/forja-agent-client.env ou /etc/cloudif/provision.env.",
        })
        return False

    payload = {
        "project_slug": slug,
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant,
        "runtime_template": job.get("runtime_template") or "node22",
        "runtime_layout": job.get("runtime_layout") or "unified-v1",

        "forgejo_owner": owner,
        "forgejo_owner_kind": "user",
        "owner_user": owner,
        "org": owner,
        "access": access,

        # Padrão correto: projeto teste -> repo cloudif-teste
        "repo": repo_name,
        "repository": repo_name,
        "repo_name": repo_name,
        "repo_path": repo_path,
        "repo_url": repo_url,

        "create_repo": True,
        "ensure_webhook": True,
        "webhook_url": env("CLOUDIF_DEPLOY_WEBHOOK_URL", ""),
        "user": job.get("user") or {},

        "project": {
            "project_slug": slug,
            "slug": slug,
            "name": job.get("name") or slug,
            "description": job.get("description") or "",
            "tenant": tenant,
            "runtime_template": job.get("runtime_template") or "node22",
        "runtime_layout": job.get("runtime_layout") or "unified-v1",
            "repo": repo_name,
            "repo_path": repo_path,
            "repo_url": repo_url,
        },

        "komodo": {
            "url": env("KOMODO_URL", "https://komodoiff.duckdns.org"),
            "containers": [
                f"{slug}-app",
                f"{slug}-worker",
                f"{slug}-proxy",
            ] + ([f"{tenant}-supabase"] if tenant else []),
            "repo": repo_path,
            "repo_url": _v115_repo_clone_url(slug, owner),
        },
    }

    headers = {
        "X-CloudIF-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    st, data, raw = http_json(
        "POST",
        agent_url + "/project/ensure",
        token="",
        data=payload,
        extra_headers=headers,
        timeout=90,
    )

    if st in [200, 201, 202] and isinstance(data, dict) and data.get("ok") is not False:
        comp["status"] = "done_via_forja_agent"
        comp["ok"] = True
        comp["repository"] = repo_name
        comp["repository_path"] = repo_path
        comp["url"] = repo_url
        comp["clone_url"] = _v115_repo_clone_url(slug, owner)

        project_data = data.get("project") if isinstance(data.get("project"), dict) else {}
        forgejo_data = project_data.get("forgejo") if isinstance(project_data.get("forgejo"), dict) else {}

        if forgejo_data:
            comp["forja_agent_forgejo"] = {
                "ok": forgejo_data.get("ok"),
                "created": forgejo_data.get("created"),
                "owner": forgejo_data.get("owner"),
                "repo": forgejo_data.get("repo"),
                "url": forgejo_data.get("url"),
                "message": forgejo_data.get("message"),
            }

        webhook_data = project_data.get("forgejo_webhook") if isinstance(project_data.get("forgejo_webhook"), dict) else {}
        if webhook_data:
            comp["forgejo_webhook"] = {
                "ok": webhook_data.get("ok"),
                "id": webhook_data.get("id"),
                "type": webhook_data.get("type"),
                "url": webhook_data.get("url"),
                "message": webhook_data.get("message"),
            }

        komodo_wh = project_data.get("komodo_webhook") if isinstance(project_data.get("komodo_webhook"), dict) else {}
        if komodo_wh:
            wh_url = str(komodo_wh.get("url") or "")
            if "token=" in wh_url:
                wh_url = wh_url.split("token=", 1)[0] + "token=***OCULTO***"
            comp["komodo_webhook"] = {
                "ok": komodo_wh.get("ok"),
                "created_local": komodo_wh.get("created_local"),
                "created_remote": komodo_wh.get("created_remote"),
                "url_masked": wh_url,
                "message": komodo_wh.get("message"),
            }

        komodo_trigger = project_data.get("komodo_trigger") if isinstance(project_data.get("komodo_trigger"), dict) else {}
        if komodo_trigger:
            comp["komodo_trigger"] = {
                "ok": komodo_trigger.get("ok"),
                "executed": komodo_trigger.get("executed"),
                "message": komodo_trigger.get("message"),
            }

        comp["actions"].append({
            "name": "forja_agent_project_ensure",
            "ok": True,
            "message": "Forja Agent aceitou /project/ensure.",
            "endpoint": "/project/ensure",
        })

        comp["agent_response_keys"] = sorted(list(data.keys()))[:40]
        return True

    comp["status"] = "forja_agent_error"
    comp["ok"] = False
    comp["actions"].append({
        "name": "forja_agent_project_ensure",
        "ok": False,
        "status": st,
        "message": "Forja Agent /project/ensure não aceitou o provisionamento.",
        "detail": data if isinstance(data, dict) else {},
    })
    return False


def komodo(job, report):
    comp = report["components"]["komodo"]
    slug = report["slug"]
    tenant = report["tenant"]

    komodo_url = env("KOMODO_URL", "https://komodoiff.duckdns.org").rstrip("/")
    deploy_center = env("CLOUDIF_DEPLOY_CENTER_URL", "http://127.0.0.1:18099").rstrip("/")

    containers = [
        f"{slug}-app",
        f"{slug}-worker",
        f"{slug}-proxy",
    ]
    if tenant:
        containers.append(f"{tenant}-supabase")

    comp["url"] = komodo_url
    comp["containers"] = containers

    manifest = {
        "project": slug,
        "tenant": tenant,
        "komodo_url": komodo_url,
        "containers": containers,
        "triggers": [
            {
                "name": "cloudif-komodo-deploy-trigger",
                "purpose": "Acionar deploy a partir de push/release no Forgejo.",
            },
            {
                "name": "cloudif-komodo-sync-trigger",
                "purpose": "Sincronizar containers vinculados ao projeto.",
            },
            {
                "name": "cloudif-komodo-healthcheck-trigger",
                "purpose": "Verificar saúde dos containers do projeto.",
            },
        ],
    }

    d = BASE / slug
    d.mkdir(parents=True, exist_ok=True)
    manifest_path = d / "komodo-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report["files"]["komodo_manifest"] = str(manifest_path)

    # Health do Deploy Center
    st, data, raw = http_json("GET", deploy_center + "/health")
    if st == 200:
        comp["actions"].append({"name": "deploy_center_health", "ok": True, "message": "Deploy Center respondeu /health."})
    else:
        comp["actions"].append({"name": "deploy_center_health", "ok": False, "message": "Deploy Center não respondeu /health.", "status": st, "detail": data})

    # Tenta endpoints reais se existirem no Deploy Center.
    payload = manifest
    attempted = False
    for endpoint in [
        "/api/project/integrate",
        "/api/projects/integrate",
        "/project/integrate",
        "/integrate",
        "/api/komodo/project",
    ]:
        attempted = True
        st2, data2, raw2 = http_json("POST", deploy_center + endpoint, data=payload)
        if st2 in [200, 201, 202]:
            comp["actions"].append({
                "name": "cloudif-komodo-deploy-trigger",
                "ok": True,
                "message": f"Integração enviada ao Deploy Center em {endpoint}.",
                "endpoint": endpoint,
            })
            comp["status"] = "done"
            comp["ok"] = True
            return

    comp["actions"].append({
        "name": "cloudif-komodo-deploy-trigger",
        "ok": False,
        "message": "Nenhum endpoint de integração Komodo aceitou o manifesto. Manifesto foi gravado para auditoria.",
        "manifest": str(manifest_path),
    })

    # Se houver API/tokens de Komodo, registra tentativa explícita.
    if env("KOMODO_API_KEY") or env("KOMODO_API_SECRET"):
        comp["actions"].append({
            "name": "komodo_api_credentials_detected",
            "ok": True,
            "message": "Credenciais Komodo detectadas, mas endpoint específico ainda precisa ser mapeado conforme API do Komodo instalada.",
        })

    comp["status"] = "manifest_only"
    comp["ok"] = False




def _cloudif_terminal_after_provision(agent_url, token, slug, data, comp):
    try:
        stack_action=data.get("stack_action") if isinstance(data.get("stack_action"),dict) else {}
        stack=data.get("stack") if isinstance(data.get("stack"),dict) else {}
        stack_id=(data.get("stack_id") or stack.get("id") or stack.get("_id") or stack_action.get("id") or stack_action.get("stack_id") or "")
        if isinstance(stack_id,dict): stack_id=stack_id.get("$oid") or ""
        if not stack_id:
            comp.setdefault("actions",[]).append({"name":"komodo_container_terminal","ok":False,"message":"Stack criado, mas ID ainda não disponível; abertura fará reconciliação automática."})
            return
        headers={"Accept":"application/json","Content-Type":"application/json"}
        if token: headers["X-CloudIF-Token"]=token
        payload={"project":slug,"stack_id":str(stack_id),"service":"web","terminal":"cloudif-"+slug,"shell":"sh"}
        for _ in range(4):
            st,res,raw=http_json("POST",agent_url+"/komodo/project/terminal/ensure",token="",data=payload,extra_headers=headers,timeout=30)
            if st==200 and isinstance(res,dict) and res.get("ok"):
                comp.setdefault("actions",[]).append({"name":"komodo_container_terminal","ok":True,"message":"Terminal Container criado com shell sh.","target":res.get("target"),"url":res.get("url")})
                return
            time.sleep(5)
        comp.setdefault("actions",[]).append({"name":"komodo_container_terminal","ok":False,"message":"Container ainda não estava pronto; abertura/reparação concluirá automaticamente."})
    except Exception as exc:
        comp.setdefault("actions",[]).append({"name":"komodo_container_terminal","ok":False,"message":"Terminal será reconciliado na abertura.","detail":str(exc)[:180]})

# CloudIF v112 — função Komodo canônica via Komodo Agent 10.62.91.2:18098
def komodo(job, report):
    comp = report["components"]["komodo"]
    comp.setdefault("actions", [])

    slug = report["slug"]
    tenant = report.get("tenant") or ""

    agent_url = env("KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/")
    token = env("KOMODO_AGENT_TOKEN", "")

    containers = [
        f"{slug}-app",
        f"{slug}-worker",
        f"{slug}-proxy",
    ]

    if tenant:
        containers.append(f"{tenant}-supabase")

    comp["url"] = env("KOMODO_URL", "https://komodoiff.duckdns.org")
    comp["agent_url"] = agent_url
    comp["containers"] = containers

    payload = {
        "project_slug": slug,
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant or "unknown",
        "containers": containers,
        "repo": _v115_repo_path(slug),
        "repo_url": _v115_repo_clone_url(slug),
        "forgejo": {
            "owner": "cloudif",
            "repo": _v115_repo_name(slug),
            "repo_path": _v115_repo_path(slug),
            "repo_url": _v115_repo_clone_url(slug),
            "git_provider": "cloudiff.duckdns.org/git",
            "branch": "main",
        },
        "user": job.get("user") or {},
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if token:
        headers["X-CloudIF-Token"] = token

    for ep in ["/komodo/project/ensure", "/project/ensure", "/komodo/ensure"]:
        st, data, raw = http_json(
            "POST",
            agent_url + ep,
            token="",
            data=payload,
            extra_headers=headers,
            timeout=90,
        )

        if st in [200, 201, 202] and isinstance(data, dict) and data.get("ok") is not False:
            comp["status"] = "done_via_komodo_agent"
            comp["ok"] = True
            comp["actions"].append({
                "name": "komodo_agent_project_ensure",
                "ok": True,
                "message": f"Komodo Agent aceitou provisionamento em {ep}.",
                "endpoint": ep,
            })

            comp["agent_response_keys"] = sorted(list(data.keys()))[:40]
            _cloudif_terminal_after_provision(agent_url, token, slug, data, comp)

            forgejo = data.get("forgejo") if isinstance(data.get("forgejo"), dict) else {}
            if forgejo:
                comp["forgejo"] = forgejo

            repo_action = data.get("repo_action") if isinstance(data.get("repo_action"), dict) else {}
            stack_action = data.get("stack_action") if isinstance(data.get("stack_action"), dict) else {}

            if repo_action:
                comp["repo_action_created"] = repo_action.get("created")
            if stack_action:
                comp["stack_action_created"] = stack_action.get("created")

            return

        comp["actions"].append({
            "name": "komodo_agent_project_ensure_attempt",
            "ok": False,
            "status": st,
            "endpoint": ep,
            "message": "Tentativa de provisionar no Komodo Agent não foi aceita.",
            "detail": data if isinstance(data, dict) else {},
        })

        if st in [401, 403]:
            comp["status"] = "auth_error"
            comp["ok"] = False
            return

    comp["status"] = "error"
    comp["ok"] = False




# CloudIF v115 — função Komodo canônica com repo cloudif/cloudif-<slug>
def komodo(job, report):
    comp = report["components"]["komodo"]
    comp.setdefault("actions", [])

    slug = _v115_project_slug(report["slug"]) if "_v115_project_slug" in globals() else str(report["slug"])
    access = _cloudif_project_access(slug, job)
    owner = access["owner"]
    repo_name = _v115_repo_name(slug) if "_v115_repo_name" in globals() else "cloudif-" + slug
    repo_path = _v115_repo_path(slug, owner) if "_v115_repo_path" in globals() else owner + "/" + repo_name
    repo_url = _v115_repo_clone_url(slug, owner) if "_v115_repo_clone_url" in globals() else f"https://cloudiff.duckdns.org/git/{repo_path}.git"

    tenant = report.get("tenant") or ""
    agent_url = env("KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/")
    token = env("KOMODO_AGENT_TOKEN", "")

    containers = [
        f"{slug}-app",
        f"{slug}-worker",
        f"{slug}-proxy",
    ]

    if tenant:
        containers.append(f"{tenant}-supabase")

    comp["url"] = env("KOMODO_URL", "https://komodoiff.duckdns.org")
    comp["agent_url"] = agent_url
    comp["containers"] = containers
    comp["repository"] = repo_name
    comp["repository_path"] = repo_path
    comp["repo_url"] = repo_url

    payload = {
        "project_slug": slug,
        "slug": slug,
        "name": job.get("name") or slug,
        "description": job.get("description") or "",
        "tenant": tenant or "unknown",
        "runtime_template": job.get("runtime_template") or "node22",
        "runtime_layout": job.get("runtime_layout") or "unified-v1",
        "containers": containers,

        "repo": repo_path,
        "repo_url": repo_url,

        "owner_user": owner,
        "access": access,
        "forgejo": {
            "owner": owner,
            "repo": repo_name,
            "repo_path": repo_path,
            "repo_url": repo_url,
            "git_provider": "cloudiff.duckdns.org/git",
            "branch": "main",
        },

        "user": job.get("user") or {},
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if token:
        headers["X-CloudIF-Token"] = token

    for ep in ["/komodo/project/ensure", "/project/ensure", "/komodo/ensure"]:
        st, data, raw = http_json(
            "POST",
            agent_url + ep,
            token="",
            data=payload,
            extra_headers=headers,
            timeout=90,
        )

        if st in [200, 201, 202] and isinstance(data, dict) and data.get("ok") is not False:
            comp["status"] = "done_via_komodo_agent"
            comp["ok"] = True
            comp["actions"].append({
                "name": "komodo_agent_project_ensure",
                "ok": True,
                "message": f"Komodo Agent aceitou provisionamento em {ep}.",
                "endpoint": ep,
            })

            comp["agent_response_keys"] = sorted(list(data.keys()))[:40]
            stack = data.get("stack") if isinstance(data.get("stack"), dict) else {}
            stack_action = data.get("stack_action") if isinstance(data.get("stack_action"), dict) else {}
            stack_id = data.get("stack_id") or stack.get("id") or stack.get("_id") or stack_action.get("stack_id") or stack_action.get("id") or ""
            if isinstance(stack_id, dict):
                stack_id = stack_id.get("$oid") or ""
            comp["stack_id"] = str(stack_id or "")
            comp["stack_name"] = str(data.get("stack_name") or stack.get("name") or stack_action.get("name") or ("cloudif-" + slug))
            repo = data.get("repo") if isinstance(data.get("repo"), dict) else {}
            repo_action = data.get("repo_action") if isinstance(data.get("repo_action"), dict) else {}
            repo_id = data.get("repo_id") or repo.get("id") or repo.get("_id") or repo_action.get("repo_id") or repo_action.get("id") or ""
            if isinstance(repo_id, dict):
                repo_id = repo_id.get("$oid") or ""
            comp["repo_id"] = str(repo_id or "")
            comp["repo_name"] = str(data.get("repo_name") or repo.get("name") or repo_name)
            server = data.get("server") if isinstance(data.get("server"), dict) else {}
            comp["server_id"] = str(server.get("id") or data.get("server_id") or "")
            comp["server_name"] = str(server.get("name") or data.get("server_name") or "")
            _cloudif_terminal_after_provision(agent_url, token, slug, data, comp)
            return

        comp["actions"].append({
            "name": "komodo_agent_project_ensure_attempt",
            "ok": False,
            "status": st,
            "endpoint": ep,
            "message": "Tentativa de provisionar no Komodo Agent não foi aceita.",
            "detail": data if isinstance(data, dict) else {},
        })

        if st in [401, 403]:
            comp["status"] = "auth_error"
            comp["ok"] = False
            return

    comp["status"] = "error"
    comp["ok"] = False


def supabase(job, report):
    comp = report["components"]["supabase"]
    slug = report["slug"]
    tenant = report["tenant"]

    if not tenant:
        comp["status"] = "skipped_no_database"
        comp["actions"].append({
            "name": "supabase_database",
            "ok": True,
            "message": "Projeto sem banco de dados; Supabase não foi provisionado.",
        })
        comp["ok"] = True
        return

    container = env("SUPABASE_DB_CONTAINER", "supabase-db")
    db_name = env("SUPABASE_DB_NAME", "postgres")
    db_user = env("SUPABASE_DB_USER", "postgres")

    rc, out, err = run(["docker", "inspect", container], timeout=20)
    if rc != 0:
        comp["status"] = "missing_container"
        comp["actions"].append({
            "name": "supabase_db_container",
            "ok": False,
            "message": f"Container {container} não encontrado.",
            "detail": err,
        })
        return

    def sql_literal(v):
        return "'" + str(v).replace("'", "''") + "'"

    sql = f"""
CREATE SCHEMA IF NOT EXISTS cloudif;

CREATE TABLE IF NOT EXISTS cloudif.project_registry (
  slug text PRIMARY KEY,
  tenant text,
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloudif.project_events (
  id bigserial PRIMARY KEY,
  slug text NOT NULL,
  event text NOT NULL,
  payload jsonb DEFAULT '{{}}'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloudif.project_acl (
  id bigserial PRIMARY KEY,
  slug text NOT NULL,
  subject_type text NOT NULL,
  subject text NOT NULL,
  permission text NOT NULL DEFAULT 'access',
  updated_at timestamptz DEFAULT now(),
  UNIQUE(slug, subject_type, subject)
);

CREATE OR REPLACE FUNCTION cloudif.cloudif_register_project_event(
  p_slug text,
  p_event text,
  p_payload jsonb DEFAULT '{{}}'::jsonb
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO cloudif.project_events(slug, event, payload)
  VALUES (p_slug, p_event, COALESCE(p_payload, '{{}}'::jsonb));
END;
$$;

CREATE OR REPLACE FUNCTION cloudif.cloudif_ensure_project_schema(
  p_slug text,
  p_tenant text
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO cloudif.project_registry(slug, tenant, updated_at)
  VALUES (p_slug, p_tenant, now())
  ON CONFLICT (slug) DO UPDATE
    SET tenant = EXCLUDED.tenant,
        updated_at = now();

  PERFORM cloudif.cloudif_register_project_event(
    p_slug,
    'ensure_project_schema',
    jsonb_build_object('tenant', p_tenant)
  );
END;
$$;

CREATE OR REPLACE FUNCTION cloudif.cloudif_sync_project_acl(
  p_slug text,
  p_subject_type text,
  p_subject text,
  p_permission text DEFAULT 'access'
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO cloudif.project_acl(slug, subject_type, subject, permission, updated_at)
  VALUES (p_slug, p_subject_type, p_subject, COALESCE(p_permission, 'access'), now())
  ON CONFLICT (slug, subject_type, subject) DO UPDATE
    SET permission = EXCLUDED.permission,
        updated_at = now();

  PERFORM cloudif.cloudif_register_project_event(
    p_slug,
    'sync_project_acl',
    jsonb_build_object(
      'subject_type', p_subject_type,
      'subject', p_subject,
      'permission', COALESCE(p_permission, 'access')
    )
  );
END;
$$;

CREATE OR REPLACE FUNCTION cloudif.cloudif_project_acl_changed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM cloudif.cloudif_register_project_event(
    COALESCE(NEW.slug, OLD.slug),
    TG_OP || '_project_acl',
    jsonb_build_object(
      'subject_type', COALESCE(NEW.subject_type, OLD.subject_type),
      'subject', COALESCE(NEW.subject, OLD.subject)
    )
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_cloudif_project_acl_changed ON cloudif.project_acl;

CREATE TRIGGER trg_cloudif_project_acl_changed
AFTER INSERT OR UPDATE OR DELETE ON cloudif.project_acl
FOR EACH ROW EXECUTE FUNCTION cloudif.cloudif_project_acl_changed();

SELECT cloudif.cloudif_ensure_project_schema({sql_literal(slug)}, {sql_literal(tenant)});
SELECT cloudif.cloudif_register_project_event(
  {sql_literal(slug)},
  'provision_supabase',
  jsonb_build_object('tenant', {sql_literal(tenant)})
);
"""

    rc, out, err = run(["docker", "exec", "-i", container, "psql", "-U", db_user, "-d", db_name, "-v", "ON_ERROR_STOP=1"], input_text=sql, timeout=120)

    d = BASE / slug
    d.mkdir(parents=True, exist_ok=True)
    sql_path = d / "supabase-provision.sql"
    sql_path.write_text(sql, encoding="utf-8")
    report["files"]["supabase_sql"] = str(sql_path)

    if rc == 0:
        comp["actions"].extend([
            {"name": "cloudif_ensure_project_schema", "ok": True, "message": "Procedure criada/atualizada e executada."},
            {"name": "cloudif_sync_project_acl", "ok": True, "message": "Procedure de sincronização ACL criada/atualizada."},
            {"name": "cloudif_register_project_event", "ok": True, "message": "Procedure de eventos criada/atualizada."},
            {"name": "trg_cloudif_project_acl_changed", "ok": True, "message": "Trigger criada/atualizada."},
        ])
        ensure_script = env("CLOUDIF_SUPABASE_ENSURE_SCRIPT", "/srv/cloudif/bin/cloudif-auto-ensure-supabase-tenant.sh")
        erc, eout, eerr = run([ensure_script, tenant], timeout=2700)
        comp["actions"].append({
            "name": "supabase_tenant_runtime",
            "ok": erc == 0,
            "message": "Tenant Supabase criado e reconciliado." if erc == 0 else "Falha ao criar o tenant Supabase.",
            "detail": (eout + "\n" + eerr)[-1500:],
        })
        hrc, hout, herr = run(["bash", "-lc", f"source /srv/cloudif/lib/cloudif-supabase.sh; cloudif_supabase_tenant_basic_health {tenant!r}"], timeout=120)
        comp["actions"].append({
            "name": "supabase_tenant_health",
            "ok": hrc == 0,
            "message": "Containers do tenant estão saudáveis." if hrc == 0 else "Tenant criado, mas ainda não está saudável.",
            "detail": (hout + "\n" + herr)[-1000:],
        })
        crc, cout, cerr = run(["/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh", tenant], timeout=420)
        comp["actions"].append({
            "name": "supabase_tenant_certificate",
            "ok": crc == 0,
            "message": "Certificado do tenant reconciliado." if crc == 0 else "Falha ao reconciliar o certificado do tenant.",
            "detail": (cout + "\n" + cerr)[-1000:],
        })
        comp["ok"] = bool(erc == 0 and hrc == 0 and crc == 0)
        comp["status"] = "done" if comp["ok"] else "tenant_runtime_error"
    else:
        comp["status"] = "error"
        comp["actions"].append({
            "name": "supabase_sql",
            "ok": False,
            "message": "Falha ao aplicar SQL no Supabase/Postgres.",
            "stderr": err[-1000:],
        })

def persist_portal_state(report):
    """Persiste resultados dos agentes para leitura imediata no Portal."""
    try:
        import sqlite3
        con = sqlite3.connect(env("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"), timeout=20)
        slug = str(report.get("slug") or "")
        tenant = str(report.get("tenant") or "")
        components = report.get("components") or {}
        forge = components.get("forgejo") or {}
        komodo = components.get("komodo") or {}
        supabase_comp = components.get("supabase") or {}
        repo_url = str(forge.get("url") or "")
        repo_name = str(forge.get("repository") or komodo.get("repo_name") or komodo.get("repository") or "")
        forgejo_webhook = forge.get("forgejo_webhook") if isinstance(forge.get("forgejo_webhook"), dict) else {}
        forgejo_webhook_url = str(forgejo_webhook.get("url") or "")
        stack_id = str(komodo.get("stack_id") or "")
        stack_name = str(komodo.get("stack_name") or "")
        komodo_repo_id = str(komodo.get("repo_id") or "")
        komodo_repo_name = str(komodo.get("repo_name") or komodo.get("repository") or "")
        server_name = str(komodo.get("server_name") or "")
        now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        con.execute("""INSERT INTO project_integrations(project,tenant,repo_url,stack_name,stack_id,repo_name,status,message,updated_at,forgejo_repo_url,forgejo_webhook_url,komodo_stack_name,komodo_stack_id,komodo_repo_name,komodo_repo_id,server_name,forgejo_status,komodo_status,supabase_status)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project) DO UPDATE SET
        tenant=COALESCE(NULLIF(excluded.tenant,''),project_integrations.tenant),
        repo_url=COALESCE(NULLIF(excluded.repo_url,''),project_integrations.repo_url),
        stack_name=COALESCE(NULLIF(excluded.stack_name,''),project_integrations.stack_name),
        stack_id=COALESCE(NULLIF(excluded.stack_id,''),project_integrations.stack_id),
        repo_name=COALESCE(NULLIF(excluded.repo_name,''),project_integrations.repo_name),
        status=excluded.status,message=excluded.message,updated_at=excluded.updated_at,
        forgejo_repo_url=COALESCE(NULLIF(excluded.forgejo_repo_url,''),project_integrations.forgejo_repo_url),
        forgejo_webhook_url=COALESCE(NULLIF(excluded.forgejo_webhook_url,''),project_integrations.forgejo_webhook_url),
        komodo_stack_name=COALESCE(NULLIF(excluded.komodo_stack_name,''),project_integrations.komodo_stack_name),
        komodo_stack_id=COALESCE(NULLIF(excluded.komodo_stack_id,''),project_integrations.komodo_stack_id),
        komodo_repo_name=COALESCE(NULLIF(excluded.komodo_repo_name,''),project_integrations.komodo_repo_name),
        komodo_repo_id=COALESCE(NULLIF(excluded.komodo_repo_id,''),project_integrations.komodo_repo_id),
        server_name=COALESCE(NULLIF(excluded.server_name,''),project_integrations.server_name),
        forgejo_status=excluded.forgejo_status,komodo_status=excluded.komodo_status,supabase_status=excluded.supabase_status""",
        (slug,tenant,repo_url,stack_name,stack_id,repo_name,"ready" if report.get("ok") else "degraded","Provisionamento concluído." if report.get("ok") else "Provisionamento com pendências.",now,repo_url,forgejo_webhook_url,stack_name,stack_id,komodo_repo_name,komodo_repo_id,server_name,str(forge.get("status") or ""),str(komodo.get("status") or ""),str(supabase_comp.get("status") or "")))
        con.execute("""UPDATE projects SET
          repo_url=COALESCE(NULLIF(?,''),repo_url),
          repo_name=COALESCE(NULLIF(?,''),repo_name),
          stack_name=COALESCE(NULLIF(?,''),stack_name),
          komodo_status=?,updated_at=? WHERE slug=?""",
          (repo_url,repo_name,stack_name,"running" if komodo.get("ok") else "error",now,slug))
        con.commit();con.close()
    except Exception as exc:
        log("PORTAL_STATE_PERSIST_ERROR " + type(exc).__name__ + ": " + str(exc))

def main():
    load_env_files()

    if len(sys.argv) < 2:
        print("Uso: cloudif_project_provision_real.py <job.json>", file=sys.stderr)
        return 2

    job_path = Path(sys.argv[1])
    job = json.loads(job_path.read_text(encoding="utf-8"))

    report = report_init(job)
    log(f"REAL_START slug={report['slug']} tenant={report['tenant']} job={job_path}")
    save_report(report)

    try:
        forgejo(job, report)
    except Exception as e:
        report["errors"].append({"component": "forgejo", "error": str(e)})
        report["components"]["forgejo"]["status"] = "exception"

    save_report(report)

    try:
        komodo(job, report)
    except Exception as e:
        report["errors"].append({"component": "komodo", "error": str(e)})
        report["components"]["komodo"]["status"] = "exception"

    save_report(report)

    try:
        supabase(job, report)
    except Exception as e:
        report["errors"].append({"component": "supabase", "error": str(e)})
        report["components"]["supabase"]["status"] = "exception"

    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["ok"] = all(c.get("ok") for c in report["components"].values())
    path = save_report(report)
    persist_portal_state(report)

    log(f"REAL_DONE slug={report['slug']} ok={report['ok']} report={path}")
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
