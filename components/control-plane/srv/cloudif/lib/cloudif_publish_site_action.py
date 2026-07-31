# CloudIF v137a-safe — Publicar site via Komodo Agent
import json
import urllib.error
import urllib.request
from pathlib import Path

def _read_env(path):
    data = {}
    p = Path(path)
    if not p.exists():
        return data
    for raw in p.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data

def _komodo_agent_config():
    env1 = _read_env("/etc/cloudif/komodo-agent-client.env")
    env2 = _read_env("/etc/cloudif/provision.env")
    url = (
        env1.get("KOMODO_AGENT_URL")
        or env2.get("KOMODO_AGENT_URL")
        or "http://10.62.91.2:18098"
    ).rstrip("/")
    token = env1.get("KOMODO_AGENT_TOKEN") or env2.get("KOMODO_AGENT_TOKEN") or ""
    return url, token

def _form_get(form, key, default=""):
    try:
        if hasattr(form, "getvalue"):
            return form.getvalue(key) or default
        v = form.get(key, default)
        if isinstance(v, list):
            return v[0] if v else default
        return v or default
    except Exception:
        return default

def _http_post_json(path, payload, timeout=90):
    base, token = _komodo_agent_config()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if token:
        headers["X-CloudIF-Token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw}
            return {"ok": 200 <= r.status < 300, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}", "data": {}}

def _is_publish_op(form):
    op = (
        _form_get(form, "op")
        or _form_get(form, "action")
        or _form_get(form, "cmd")
        or ""
    ).strip()

    return op in {
        "publish_site",
        "publicar_site",
        "deploy_site",
        "build_site",
        "publish",
    }

def handle_publish_site_action(form, actor="portal"):
    if not _is_publish_op(form):
        return None

    project = (
        _form_get(form, "project")
        or _form_get(form, "slug")
        or _form_get(form, "project_slug")
        or ""
    ).strip()

    tenant = (_form_get(form, "tenant") or "").strip()

    if not project:
        return False, "Projeto não informado para publicação.", {
            "ok": False,
            "error": "project_required",
        }

    payload = {
        "project_slug": project,
        "tenant": tenant,
        "actor": actor,
        "source": "portal-v137a",
    }

    pull = _http_post_json("/komodo/stack/pull", payload, timeout=90)
    deploy = _http_post_json("/komodo/stack/deploy", payload, timeout=90)

    ok = bool(pull.get("ok")) and bool(deploy.get("ok"))

    if ok:
        msg = f"Publicação acionada para {project}. Pull e deploy enviados ao Komodo."
    else:
        msg = f"Publicação solicitada para {project}, mas houve falha em pull ou deploy."

    return ok, msg, {
        "ok": ok,
        "project": project,
        "tenant": tenant,
        "public_url": f"https://{project}.cloudiff.duckdns.org",
        "pull": pull,
        "deploy": deploy,
    }
