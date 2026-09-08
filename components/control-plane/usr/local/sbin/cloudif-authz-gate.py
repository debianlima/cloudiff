#!/usr/bin/env python3
import hashlib
import os
import re
import sys
import time
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DOMAIN = os.environ.get("CLOUDIF_DOMAIN", "cloudiff.duckdns.org").lower()
OUTPOST_URL = os.environ.get("CLOUDIF_AUTHENTIK_OUTPOST", "http://10.62.91.2:9000/outpost.goauthentik.io/auth/nginx")
LISTEN_HOST = os.environ.get("CLOUDIF_AUTHZ_LISTEN_HOST", "10.62.92.7")
LISTEN_PORT = int(os.environ.get("CLOUDIF_AUTHZ_LISTEN_PORT", "18092"))

CACHE_ALLOW_TTL = int(os.environ.get("CLOUDIF_AUTHZ_CACHE_ALLOW_TTL", "15"))
CACHE_DENY_TTL = int(os.environ.get("CLOUDIF_AUTHZ_CACHE_DENY_TTL", "5"))
LOG_204 = os.environ.get("CLOUDIF_AUTHZ_LOG_204", "false").lower() in {"1", "true", "yes", "on"}

ACCESS_DIR = Path(os.environ.get("CLOUDIF_TENANT_ACCESS_DIR", "/var/lib/cloudif/tenant-access"))
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,126}$")
SUBJECT_RE = re.compile(r"^[^\s\x00]{1,256}$")

ADMIN_USERS = {
    x.strip().lower()
    for x in os.environ.get("CLOUDIF_ADMIN_USERS", "").split(",")
    if x.strip()
}

ADMIN_GROUPS = {
    x.strip().lower()
    for x in os.environ.get("CLOUDIF_ADMIN_GROUPS", "").split(",")
    if x.strip()
}

CACHE = {}
CACHE_LOCK = threading.Lock()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def clean_host(value: str) -> str:
    value = (value or "").strip().lower()
    if "," in value:
        value = value.split(",", 1)[0].strip()
    if ":" in value:
        value = value.split(":", 1)[0].strip()
    return value

def tenant_from_request(host: str, uri: str) -> str:
    host = clean_host(host)
    uri = uri or "/"

    suffix = "." + DOMAIN
    if host.endswith(suffix):
        tenant = host[:-len(suffix)].strip(".")
        if TENANT_RE.fullmatch(tenant) and tenant not in {"www", "authiff", "cloudiff"}:
            return tenant

    parts = uri.split("/")
    if len(parts) >= 3 and parts[1] == "supabase" and parts[2]:
        tenant = parts[2].lower()
        if TENANT_RE.fullmatch(tenant):
            return tenant

    return ""

def groups_to_set(groups_header: str):
    raw = groups_header or ""
    for separator in (";", "|"):
        raw = raw.replace(separator, ",")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def load_tenant_access(tenant: str):
    users = set()
    groups = set()
    tenant = (tenant or "").strip().lower()
    if not TENANT_RE.fullmatch(tenant):
        return users, groups
    for suffix, target in (("users", users), ("groups", groups)):
        path = ACCESS_DIR / f"{tenant}.{suffix}"
        try:
            for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
                value = raw.strip().lower()
                if not value or value.startswith("#") or not SUBJECT_RE.fullmatch(value):
                    continue
                target.add(value)
        except (FileNotFoundError, PermissionError, UnicodeError, OSError):
            continue
    return users, groups


def authorize_tenant(username: str, groups, tenant: str):
    username = (username or "").strip().lower()
    tenant = (tenant or "").strip().lower()
    normalized_groups = {str(value).strip().lower() for value in (groups or set()) if str(value).strip()}
    if username == tenant:
        return True, "user-matches-tenant"
    if username in ADMIN_USERS:
        return True, "admin-user"
    if normalized_groups.intersection(ADMIN_GROUPS):
        return True, "admin-group"
    allow_users, allow_groups = load_tenant_access(tenant)
    if username in allow_users:
        return True, "tenant-user-allowlist"
    if normalized_groups.intersection(allow_groups):
        return True, "tenant-group-allowlist"
    return False, f"user-{username}-cannot-access-tenant-{tenant}"

def cache_key(cookie: str, host: str, tenant: str) -> str:
    # A chave usa cookie + host + tenant. Não usa URI para o Studio não consultar o
    # Authentik em cada endpoint diferente da mesma sessão.
    raw = f"{cookie}|{clean_host(host)}|{tenant}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()

def cache_get(key):
    now = time.time()
    with CACHE_LOCK:
        item = CACHE.get(key)
        if not item:
            return None
        expires, status, headers, body = item
        if expires <= now:
            CACHE.pop(key, None)
            return None
        return status, headers, body

def cache_set(key, ttl, status, headers, body):
    if ttl <= 0:
        return
    with CACHE_LOCK:
        CACHE[key] = (time.time() + ttl, status, headers, body)

def maybe_cleanup_cache():
    # Limpeza leve para não crescer indefinidamente.
    if len(CACHE) < 5000:
        return
    now = time.time()
    with CACHE_LOCK:
        expired = [k for k, v in CACHE.items() if v[0] <= now]
        for k in expired:
            CACHE.pop(k, None)

class Handler(BaseHTTPRequestHandler):
    server_version = "CloudIFAuthZ/239"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def log_request(self, code="-", size="-"):
        try:
            code_int = int(code)
        except Exception:
            code_int = 0
        if code_int == 204 and not LOG_204:
            return
        super().log_request(code, size)

    def send_text(self, code, text, extra_headers=None):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                if v:
                    self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_cached_or_final(self, status, headers, body=""):
        self.send_response(status)
        for k, v in headers.items():
            if v:
                self.send_header(k, v)
        self.send_header("X-CloudIF-AuthZ-Cache", headers.get("X-CloudIF-AuthZ-Cache", "miss"))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body.encode("utf-8"))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        maybe_cleanup_cache()

        if self.path.split("?", 1)[0] != "/authz":
            self.send_text(404, "not found\n")
            return

        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        uri = self.headers.get("X-Original-URI") or "/"
        original_url = self.headers.get("X-Original-URL") or f"https://{host}{uri}"
        cookie = self.headers.get("Cookie", "")
        tenant = tenant_from_request(host, uri)

        if not tenant:
            self.send_text(403, "CloudIF AuthZ: tenant não identificado\n", {
                "X-CloudIF-AuthZ-Reason": "tenant-not-found",
                "X-CloudIF-AuthZ-Cache": "no-cache",
            })
            return

        # Não cacheia requisição sem cookie. Assim anônimo sempre força 401 correto.
        ck = cache_key(cookie, host, tenant) if cookie else ""
        if ck:
            cached = cache_get(ck)
            if cached:
                status, headers, body = cached
                headers = dict(headers)
                headers["X-CloudIF-AuthZ-Cache"] = "hit"
                self.send_cached_or_final(status, headers, body)
                return

        headers = {
            "Host": clean_host(host),
            "Cookie": cookie,
            "X-Original-URL": original_url,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": host,
            "X-Forwarded-Uri": uri,
            "X-Real-IP": self.client_address[0],
            "X-Forwarded-For": self.headers.get("X-Forwarded-For", self.client_address[0]),
        }

        req = urllib.request.Request(OUTPOST_URL, headers=headers, method="GET")

        try:
            resp = OPENER.open(req, timeout=8)
            status = resp.getcode()
            resp_headers = resp.headers
        except urllib.error.HTTPError as e:
            status = e.code
            resp_headers = e.headers
        except Exception as e:
            self.send_text(500, f"CloudIF AuthZ: erro consultando Authentik: {e}\n", {
                "X-CloudIF-AuthZ-Reason": "authentik-error",
                "X-CloudIF-AuthZ-Cache": "miss",
            })
            return

        set_cookie = resp_headers.get("Set-Cookie", "")

        if status in (401, 403):
            self.send_text(status, "unauthorized\n", {
                "Set-Cookie": set_cookie,
                "X-CloudIF-AuthZ-Reason": "authentik-denied",
                "X-CloudIF-AuthZ-Cache": "miss",
            })
            return

        if 300 <= status < 400:
            self.send_text(401, "login required\n", {
                "Set-Cookie": set_cookie,
                "X-CloudIF-AuthZ-Reason": "authentik-redirect",
                "X-CloudIF-AuthZ-Cache": "miss",
            })
            return

        if not (200 <= status < 300):
            self.send_text(500, f"CloudIF AuthZ: status inesperado do Authentik: {status}\n", {
                "X-CloudIF-AuthZ-Reason": "authentik-unexpected-status",
                "X-CloudIF-AuthZ-Cache": "miss",
            })
            return

        username = (resp_headers.get("X-authentik-username") or "").strip().lower()
        email = (resp_headers.get("X-authentik-email") or "").strip().lower()
        groups_header = resp_headers.get("X-authentik-groups") or ""
        groups = groups_to_set(groups_header)

        allowed, reason = authorize_tenant(username, groups, tenant)

        if not allowed:
            final_headers = {
                "Set-Cookie": set_cookie,
                "X-CloudIF-AuthZ-Reason": reason,
                "X-CloudIF-Tenant": tenant,
                "X-Authentik-Username": username,
                "X-Authentik-Email": email,
                "X-CloudIF-AuthZ-Cache": "miss",
            }
            body = f"CloudIF AuthZ: usuário '{username}' não pode acessar tenant '{tenant}'\n"
            if ck:
                cache_set(ck, CACHE_DENY_TTL, 403, final_headers, body)
            self.send_text(403, body, final_headers)
            return

        final_headers = {
            "Set-Cookie": set_cookie,
            "X-CloudIF-AuthZ-Reason": reason,
            "X-CloudIF-Tenant": tenant,
            "X-Authentik-Username": username,
            "X-Authentik-Email": email,
            "X-Authentik-Groups": groups_header,
            "X-CloudIF-AuthZ-Cache": "miss",
        }

        if ck:
            cache_set(ck, CACHE_ALLOW_TTL, 204, final_headers, "")

        self.send_response(204)
        for k, v in final_headers.items():
            if v:
                self.send_header(k, v)
        self.end_headers()

def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"CloudIF AuthZ Gate v239 ouvindo em {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    print(f"DOMAIN={DOMAIN}", flush=True)
    print(f"OUTPOST={OUTPOST_URL}", flush=True)
    print(f"CACHE_ALLOW_TTL={CACHE_ALLOW_TTL}", flush=True)
    print(f"CACHE_DENY_TTL={CACHE_DENY_TTL}", flush=True)
    print(f"ADMIN_USERS={sorted(ADMIN_USERS)}", flush=True)
    print(f"ADMIN_GROUPS={sorted(ADMIN_GROUPS)}", flush=True)
    print(f"ACCESS_DIR={ACCESS_DIR}", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    main()
