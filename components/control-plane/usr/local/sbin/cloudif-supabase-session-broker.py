#!/usr/bin/env python3
import base64, hashlib, json, os, re, secrets, subprocess, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

def env(k, default=""):
    return os.environ.get(k, default)

PUBLIC_BASE = env("PUBLIC_BASE").rstrip("/")
ISSUER = env("OIDC_ISSUER").rstrip("/")
CLIENT_ID = env("OIDC_CLIENT_ID")
CLIENT_SECRET = env("OIDC_CLIENT_SECRET")
REDIRECT_URI = env("OIDC_REDIRECT_URI")
LISTEN = env("BROKER_LISTEN", "0.0.0.0")
PORT = int(env("BROKER_PORT", "18091"))
ENSURE_SCRIPT = env("ENSURE_SCRIPT")
STATE_TTL = int(env("BROKER_STATE_TTL", "600"))
STATE_MAX = int(env("BROKER_STATE_MAX", "256"))
TENANT_COOKIE_TTL = int(env("BROKER_TENANT_COOKIE_TTL", "3600"))

STATE = {}

def log(msg):
    print(time.strftime("[%Y-%m-%dT%H:%M:%S]"), msg, flush=True)

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def fetch_json(url, timeout=20, headers=None, data=None):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def discovery():
    return fetch_json(ISSUER + "/.well-known/openid-configuration", 15)

def token_request(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    return fetch_json(url, 25, {"Content-Type": "application/x-www-form-urlencoded"}, data)

def userinfo(url, token):
    return fetch_json(url, 20, {"Authorization": f"Bearer {token}"})

def tenant_from_claims(claims):
    raw = claims.get("preferred_username") or claims.get("username") or claims.get("email") or claims.get("sub") or "unknown"
    raw = str(raw).split("@")[0].lower()
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip(".-_")
    return raw or "unknown"

def purge_states():
    cutoff = time.time() - STATE_TTL
    expired = [key for key, value in STATE.items() if value.get("created", 0) < cutoff]
    for key in expired:
        STATE.pop(key, None)

def ensure_background(tenant):
    os.makedirs("/var/log/cloudif", exist_ok=True)
    logfile = f"/var/log/cloudif/ensure-{tenant}.log"
    lockfile = f"/run/cloudif-ensure-{tenant}.lock"

    cmd = f'flock -n "{lockfile}" bash -lc {repr(f"{ENSURE_SCRIPT} {tenant} >> {logfile} 2>&1")}'
    subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    log(f"ensure background tenant={tenant} log={logfile}")

class Handler(BaseHTTPRequestHandler):
    server_version = "CloudIF"
    sys_version = ""

    def security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def text(self, code, body, ctype="text/plain"):
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, url, cookie=None):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.security_headers()
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path in ["/health", "/cloudif/supabase/session/health"]:
                return self.text(200, json.dumps({"ok": True, "service": "cloudif-session-broker"}) + "\n", "application/json")

            if path == "/cloudif/supabase/session/start":
                purge_states()
                if len(STATE) >= STATE_MAX:
                    return self.text(429, "muitas autenticações pendentes; tente novamente em alguns minutos\n")
                meta = discovery()
                verifier = b64url(secrets.token_bytes(32))
                challenge = b64url(hashlib.sha256(verifier.encode()).digest())
                state = b64url(secrets.token_bytes(32))
                STATE[state] = {"verifier": verifier, "created": time.time()}

                q = {
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "response_type": "code",
                    "scope": "openid email profile",
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }

                url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(q)
                endpoint = urllib.parse.urlsplit(meta["authorization_endpoint"])
                log(f"start authorization_endpoint={endpoint.scheme}://{endpoint.netloc}{endpoint.path}")
                return self.redirect(url)

            if path == "/cloudif/supabase/session/callback":
                qs = urllib.parse.parse_qs(parsed.query)
                code = qs.get("code", [""])[0]
                state = qs.get("state", [""])[0]
                purge_states()
                state_data = STATE.pop(state, None)

                if not code or not state_data:
                    return self.text(400, "callback inválido ou expirado\n")
                verifier = state_data["verifier"]

                meta = discovery()
                tokens = token_request(meta["token_endpoint"], {
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": verifier,
                })

                if not tokens.get("access_token") or not meta.get("userinfo_endpoint"):
                    log("callback sem access_token ou userinfo_endpoint")
                    return self.text(502, "falha temporária ao validar a identidade\n")
                try:
                    claims = userinfo(meta["userinfo_endpoint"], tokens["access_token"])
                    log("claims validadas via userinfo")
                except Exception as e:
                    log(f"userinfo falhou type={type(e).__name__}")
                    return self.text(502, "falha temporária ao validar a identidade\n")

                if not claims or not claims.get("sub"):
                    log("userinfo sem claim sub")
                    return self.text(403, "identidade inválida\n")
                tenant = tenant_from_claims(claims)
                if tenant == "unknown":
                    log("identidade sem tenant válido")
                    return self.text(403, "identidade sem tenant válido\n")
                ensure_background(tenant)

                target = f"https://{tenant}.cloudiff.duckdns.org/"
                cookie = f"cloudif_tenant={tenant}; Max-Age={TENANT_COOKIE_TTL}; Path=/; Secure; HttpOnly; SameSite=Lax"
                log(f"callback tenant={tenant}")
                return self.redirect(target, cookie)

            return self.text(404, "not found\n")

        except Exception as e:
            clean_path = urllib.parse.urlsplit(self.path).path
            log(f"ERRO path={clean_path} type={type(e).__name__}")
            return self.text(500, "erro interno\n")

    def log_message(self, fmt, *args):
        message = fmt % args
        message = re.sub(r'([?&](?:code|state|t)=)[^&\s"]+', r'\1<redacted>', message)
        log(f'{self.client_address[0]} - "{message}"')

if __name__ == "__main__":
    log(f"CloudIF broker listening on {LISTEN}:{PORT}")
    HTTPServer((LISTEN, PORT), Handler).serve_forever()
