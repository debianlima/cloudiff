#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

ENV = Path("/etc/cloudif/forja-agent-client.env")

def read_env():
    data = {}
    if ENV.exists():
        for line in ENV.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    data.update({k: v for k, v in os.environ.items() if k.startswith("FORJA_AGENT_")})
    return data

def request(method, path, payload=None, timeout=7):
    cfg = read_env()
    base = (cfg.get("FORJA_AGENT_URL") or "").rstrip("/")
    token = cfg.get("FORJA_AGENT_TOKEN") or ""

    if not base or not token:
        return {"ok": False, "error": "FORJA_AGENT_URL/FORJA_AGENT_TOKEN não configurados"}

    headers = {
        "Accept": "application/json",
        "User-Agent": "CloudIF-Hospedagem-Client/4.0",
        "X-CloudIF-Token": token,
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            return json.loads(body)
        except Exception:
            return {"ok": False, "status": e.code, "raw": body[:1000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("projects")

    p = sub.add_parser("project-ensure")
    p.add_argument("--file", required=True)

    p2 = sub.add_parser("forgejo-sync")
    p2.add_argument("--file", required=True)

    p3 = sub.add_parser("forgejo-webhook")
    p3.add_argument("--file", required=True)

    p4 = sub.add_parser("komodo-webhook")
    p4.add_argument("--file", required=True)

    p5 = sub.add_parser("komodo-trigger")
    p5.add_argument("--file", required=True)

    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(request("GET", "/status", timeout=6), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "projects":
        print(json.dumps(request("GET", "/projects", timeout=6), ensure_ascii=False, indent=2))
        return 0

    payload = None
    if hasattr(args, "file"):
        payload = json.loads(Path(args.file).read_text(errors="ignore"))

    path = {
        "project-ensure": "/project/ensure",
        "forgejo-sync": "/forgejo/ensure-repo",
        "forgejo-webhook": "/forgejo/ensure-webhook",
        "komodo-webhook": "/komodo/ensure-webhook",
        "komodo-trigger": "/komodo/trigger",
    }.get(args.cmd)

    print(json.dumps(request("POST", path, payload=payload, timeout=20), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
