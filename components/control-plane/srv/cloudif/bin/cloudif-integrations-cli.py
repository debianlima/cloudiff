#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path("/etc/cloudif/cloudif-integrations.env")
STATE_DIR = Path("/var/lib/cloudif/integrations")
STATE_DIR.mkdir(parents=True, exist_ok=True)

def read_env(path=ENV_FILE):
    data = {}
    if path.exists():
        for line in path.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    data.update({k: v for k, v in os.environ.items() if k.startswith(("FORGEJO_", "KOMODO_", "CLOUDIF_INTEGRATION_"))})
    return data

def bool_env(v, default=False):
    if v is None or v == "":
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "sim", "on"}

def http_json(method, url, token="", payload=None, timeout=5):
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "CloudIF-Integrations/1.0",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body[:500]}
            return {
                "ok": 200 <= r.status < 300,
                "status": r.status,
                "data": parsed,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body[:500]}
        return {
            "ok": False,
            "status": e.code,
            "data": parsed,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "error": str(e),
        }

def clean_base(url):
    return (url or "").rstrip("/")

def repo_name(cfg, tenant):
    return (cfg.get("FORGEJO_REPO_PREFIX") or "cloudif-") + tenant

def forgejo_status(cfg):
    url = clean_base(cfg.get("FORGEJO_URL", ""))
    token = cfg.get("FORGEJO_TOKEN", "")
    timeout = int(cfg.get("CLOUDIF_INTEGRATION_TIMEOUT", "5") or "5")

    if not url:
        return {"ok": False, "configured": False, "message": "Forgejo não configurado."}

    res = http_json("GET", f"{url}/api/v1/version", token=token, timeout=timeout)
    if res["ok"]:
        version = res.get("data", {}).get("version", "desconhecida")
        return {"ok": True, "configured": True, "message": f"Forgejo respondeu. Versão: {version}"}

    return {
        "ok": False,
        "configured": True,
        "message": f"Forgejo não respondeu corretamente. HTTP/status: {res.get('status')} {res.get('error','')}",
    }

def komodo_status(cfg):
    url = clean_base(cfg.get("KOMODO_URL", ""))
    token = cfg.get("KOMODO_TOKEN", "")
    timeout = int(cfg.get("CLOUDIF_INTEGRATION_TIMEOUT", "5") or "5")

    if not url:
        return {"ok": False, "configured": False, "message": "Komodo não configurado."}

    # Tenta endpoints comuns sem travar o portal.
    candidates = ["/api/health", "/health", "/"]
    last = None

    for path in candidates:
        full = url + path
        res = http_json("GET", full, token=token, timeout=timeout)
        last = res
        if res["ok"]:
            return {"ok": True, "configured": True, "message": f"Komodo respondeu em {path}."}

    return {
        "ok": False,
        "configured": True,
        "message": f"Komodo não respondeu nos endpoints testados. Último status: {last.get('status') if last else '-'}",
    }

def ensure_forgejo_repo(cfg, tenant):
    url = clean_base(cfg.get("FORGEJO_URL", ""))
    token = cfg.get("FORGEJO_TOKEN", "")
    owner = (cfg.get("FORGEJO_OWNER") or "").strip()
    timeout = int(cfg.get("CLOUDIF_INTEGRATION_TIMEOUT", "5") or "5")

    if not url:
        raise SystemExit("ERRO: FORGEJO_URL vazio em /etc/cloudif/cloudif-integrations.env")
    if not token:
        raise SystemExit("ERRO: FORGEJO_TOKEN vazio em /etc/cloudif/cloudif-integrations.env")

    name = repo_name(cfg, tenant)
    private = bool_env(cfg.get("FORGEJO_PRIVATE"), True)
    auto_init = bool_env(cfg.get("FORGEJO_AUTO_INIT"), True)

    payload = {
        "name": name,
        "description": f"Repositório CloudIF do tenant {tenant}",
        "private": private,
        "auto_init": auto_init,
        "default_branch": "main",
    }

    # Se owner estiver configurado, tenta criar em organização.
    if owner:
        check = http_json("GET", f"{url}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}", token=token, timeout=timeout)
        if check["ok"]:
            return {"ok": True, "created": False, "message": "Repositório já existe.", "repo": f"{owner}/{name}", "url": f"{url}/{owner}/{name}"}

        create_url = f"{url}/api/v1/orgs/{urllib.parse.quote(owner)}/repos"
        res = http_json("POST", create_url, token=token, payload=payload, timeout=timeout)

        if res["ok"]:
            return {"ok": True, "created": True, "message": "Repositório criado na organização.", "repo": f"{owner}/{name}", "url": f"{url}/{owner}/{name}"}

        # Se falhar como org, tenta usuário autenticado.
        if res.get("status") not in {404, 403}:
            return {"ok": False, "message": "Falha ao criar repositório na organização.", "detail": res}

    res = http_json("POST", f"{url}/api/v1/user/repos", token=token, payload=payload, timeout=timeout)
    if res["ok"]:
        data = res.get("data", {})
        html_url = data.get("html_url") or f"{url}/{name}"
        full_name = data.get("full_name") or name
        return {"ok": True, "created": True, "message": "Repositório criado no usuário do token.", "repo": full_name, "url": html_url}

    if res.get("status") == 409:
        return {"ok": True, "created": False, "message": "Repositório já existia.", "repo": name}

    return {"ok": False, "message": "Falha ao criar repositório.", "detail": res}

def save_tenant_integration(tenant, data):
    path = STATE_DIR / f"{tenant}.json"
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except Exception:
            old = {}
    old.update(data)
    old["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(old, ensure_ascii=False, indent=2))
    return str(path)

def komodo_trigger(cfg, tenant):
    hook = clean_base(cfg.get("KOMODO_WEBHOOK_URL", ""))
    token = cfg.get("KOMODO_TOKEN", "")
    timeout = int(cfg.get("CLOUDIF_INTEGRATION_TIMEOUT", "5") or "5")

    if not hook:
        return {"ok": False, "configured": False, "message": "KOMODO_WEBHOOK_URL não configurado. Nada foi acionado."}

    payload = {
        "tenant": tenant,
        "environment": cfg.get("KOMODO_ENV", "cloudif"),
        "source": "cloudif-portal",
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    res = http_json("POST", hook, token=token, payload=payload, timeout=timeout)

    if res["ok"]:
        return {"ok": True, "message": "Webhook do Komodo acionado.", "detail": res}

    return {"ok": False, "message": "Falha ao acionar webhook do Komodo.", "detail": res}

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    p_repo = sub.add_parser("forgejo-ensure-repo")
    p_repo.add_argument("tenant")

    p_komodo = sub.add_parser("komodo-trigger")
    p_komodo.add_argument("tenant")

    args = parser.parse_args()
    cfg = read_env()

    if args.cmd == "status":
        print(json.dumps({
            "forgejo": forgejo_status(cfg),
            "komodo": komodo_status(cfg),
        }, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "forgejo-ensure-repo":
        res = ensure_forgejo_repo(cfg, args.tenant)
        if res.get("ok"):
            save_tenant_integration(args.tenant, {"forgejo": res})
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 2

    if args.cmd == "komodo-trigger":
        res = komodo_trigger(cfg, args.tenant)
        if res.get("ok"):
            save_tenant_integration(args.tenant, {"komodo": res})
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 2

if __name__ == "__main__":
    raise SystemExit(main())
