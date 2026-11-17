#!/usr/bin/env python3
"""Paperclip W1 safe static HTTP probe: fixed targets; never sends credentials.
This check does not authenticate, make runtime changes or infer an end-to-end pass.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.request

PUBLIC = "https://1025-w1-preview.cloudiff.duckdns.org"
ORIGIN = "http://10.62.91.2:18150"
HOST = "1025-w1-preview.cloudiff.duckdns.org"
PATHS = ("/", "/ui/", "/src/main.tsx", "/@vite/client", "/.cloudif-health")
MAX_BYTES = 8192

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

def _urlopen_no_redirect(request, timeout):
    # Prevent a tenant-controlled redirect from making this probe contact an
    # unapproved external destination. Follow no redirects, send no cookies.
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context()),
                _NoRedirect()]
    return urllib.request.build_opener(*handlers).open(request, timeout=timeout)
# Only same-origin, fixed-prefix built assets may be requested. No arbitrary URL fetch.
ASSET_RE = re.compile(r"""(?:src|href)=["'](/(?:assets|ui/assets)/[a-zA-Z0-9_./-]+\.(?:js|css))["']""")

def request_once(base: str, path: str, *, origin: bool) -> dict:
    headers = {"Host": HOST} if origin else {}
    req = urllib.request.Request(base + path, headers=headers, method="GET")
    answer: dict = {"http": None, "content_type": "", "vite_raw_index": False,
                    "title_is_paperclip": False, "transport_error": "",
                    "built_asset_path": "", "raw_vite_source": False}
    try:
        with _urlopen_no_redirect(req, timeout=6) as res:
            status, content_type = res.status, res.headers.get("Content-Type", "")
            body = res.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        status, content_type = exc.code, exc.headers.get("Content-Type", "")
        body = b"" # never log or consume an error response body
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        answer["transport_error"] = type(exc).__name__
        return answer
    answer["http"] = int(status)
    answer["content_type"] = content_type.split(";")[0].strip().lower()[:64]
    if path in ("/ui/", "/") and answer["http"] == 200 and "text/html" in answer["content_type"]:
        body = body.decode("utf-8", "replace")
        answer["vite_raw_index"] = bool(re.search(
            r"""<script[^>]+src=["']/src/main\.tsx["']""", body, re.I))
        answer["raw_vite_source"] = "/src/main." in body or "/@vite/client" in body
        answer["title_is_paperclip"] = bool(re.search(
            r"<title[^>]*>\s*Paperclip(?:[^<]*)</title>", body, re.I))
        asset = ASSET_RE.search(body)
        if asset:
            candidate = asset.group(1)
            if ".." not in candidate and "//" not in candidate:
                answer["built_asset_path"] = candidate[:200]
    return answer

def classify(observations: dict) -> str:
    p = observations.get("public", {})
    o = observations.get("origin", {})
    if p.get("/", {}).get("http") == 403 and o.get("/", {}).get("http") == 403:
        ui = o.get("/ui/", {})
        if (ui.get("http") == 200 and ui.get("vite_raw_index")
                and o.get("/src/main.tsx", {}).get("http") == 404
                and o.get("/@vite/client", {}).get("http") == 404):
            return "BROKEN_ROOT_403_VITE_SOURCE_UNBUILT"
        return "BROKEN_ROOT_403"
    if p.get("/", {}).get("http") == 200:
        root = p.get("/", {})
        path = root.get("built_asset_path", "")
        asset = p.get(path, {}) if path else {}
        if root.get("raw_vite_source") or root.get("vite_raw_index"):
            return "BROKEN_HTTP_200_RAW_VITE_SOURCE"
        if (root.get("title_is_paperclip") and path
                and asset.get("http") == 200
                and asset.get("content_type") in (
                    "text/javascript", "application/javascript", "text/css")):
            return "STATIC_APP_ASSET_200_AUTH_E2E_PENDING"
        return "HTTP_ROOT_200_E2E_NOT_VERIFIED"
    return "NOT_VALIDATED"

def probe() -> dict:
    obs = {"public": {p: request_once(PUBLIC, p, origin=False) for p in PATHS},
           "origin": {p: request_once(ORIGIN, p, origin=True) for p in PATHS}}
    # If a built asset is advertised by the public HTML, validate exactly one
    # safe same-origin built asset without cookies, redirects or credentials.
    asset_path = obs["public"]["/"].get("built_asset_path", "")
    if asset_path and asset_path not in obs["public"]:
        obs["public"][asset_path] = request_once(PUBLIC, asset_path, origin=False)
    return {"schema": "cloudiff-paperclip-w1-http-readonly/1",
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "strict_https_public_and_fixed_internal_origin",
            "project": "paperclip", "public_number": 1025, "stage": "W1",
            "state": classify(obs), "observations": obs,
            "mutations": False, "credentials_used": False, "browser_e2e_verified": False,
            "production_release_authorized": False}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", help="Restricted local JSON path; no remote file writes")
    args = ap.parse_args()
    data = probe()
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = pathlib.Path(args.output)
        if output.is_symlink(): raise SystemExit("SYMLINK_OUTPUT_FORBIDDEN")
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as fd:
            fd.write(content)
        output.chmod(0o600)
    print(content)
    # Exit 0 means the static HTTP gate passed, never authorization/E2E.
    return 0 if data["state"] == "STATIC_APP_ASSET_200_AUTH_E2E_PENDING" else 2

if __name__ == "__main__":
    sys.exit(main())
