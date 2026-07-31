#!/usr/bin/env python3
import base64
import hashlib
import html
import hmac
import secrets
import time
import http.server
import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

HOST = os.environ.get("CLOUDIF_LAUNCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLOUDIF_LAUNCH_PORT", "18090"))
PUBLIC_HOST = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")
PUBLIC_PREFIX = os.environ.get("CLOUDIF_PUBLIC_PREFIX", "/supabase").rstrip("/")
TOKEN = os.environ.get("CLOUDIF_LAUNCH_TOKEN", "").strip()
SESSION_COOKIE = "cloudif_launch_session"
SESSION_TTL = int(os.environ.get("CLOUDIF_LAUNCH_SESSION_TTL", "900"))
ENSURE = os.environ.get("CLOUDIF_ENSURE_SCRIPT", "/srv/cloudif/bin/cloudif-auto-ensure-supabase-tenant.sh")

STATE_DIR = Path("/var/lib/cloudif/launch-state")
LOG_DIR = Path("/var/log/cloudif")
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

TENANT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")


def now():
    return datetime.now().isoformat(timespec="seconds")


def public_url(tenant):
    if PUBLIC_PREFIX:
        return f"https://{PUBLIC_HOST}{PUBLIC_PREFIX}/{tenant}/"
    return f"https://{PUBLIC_HOST}/{tenant}/"


def project_url(tenant):
    return public_url(tenant).rstrip("/") + "/project/default"


def unit_name(tenant):
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", tenant)
    return f"cloudif-supabase-ensure-{safe}.service"


def state_file(tenant):
    return STATE_DIR / f"{tenant}.json"


def log_file(tenant):
    return LOG_DIR / f"auto-ensure-supabase-{tenant}.log"


def read_state(tenant):
    p = state_file(tenant)
    if not p.exists():
        return {
            "tenant": tenant,
            "state": "idle",
            "message": "Nenhuma preparação em andamento.",
            "updated_at": now(),
            "public_url": public_url(tenant),
            "project_url": project_url(tenant),
        }

    try:
        data = json.loads(p.read_text())
    except Exception:
        data = {
            "tenant": tenant,
            "state": "unknown",
            "message": "Arquivo de estado inválido.",
        }

    data["public_url"] = public_url(tenant)
    data["project_url"] = project_url(tenant)
    return data


def write_state(tenant, data):
    data["tenant"] = tenant
    data["updated_at"] = now()
    data["public_url"] = public_url(tenant)
    data["project_url"] = project_url(tenant)
    state_file(tenant).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def run_shell(cmd, timeout=8):
    return subprocess.run(
        ["bash", "-lc", cmd],
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def is_unit_active(tenant):
    return run_shell(f"systemctl is-active --quiet {unit_name(tenant)}", timeout=5).returncode == 0


def unit_status(tenant):
    r = run_shell(f"systemctl is-active {unit_name(tenant)} 2>/dev/null || true", timeout=5)
    return (r.stdout or "").strip()


def enqueue_tenant_reconcile(tenant, state):
    if state.get("reconcile_request_id"):
        return state
    try:
        import sys as _reconcile_sys
        if "/srv/cloudif/lib" not in _reconcile_sys.path:
            _reconcile_sys.path.insert(0, "/srv/cloudif/lib")
        from cloudif_reconcile_client import enqueue as _enqueue_reconcile
        result = _enqueue_reconcile(
            "tenant.ready",
            actor="supabase-launch-api",
            tenant=tenant,
            payload={"source": "tenant_ready"},
            dedupe_seconds=3600,
        )
        if result and result.get("request_id"):
            state["reconcile_request_id"] = result["request_id"]
            state["reconcile_status"] = result.get("status", "queued")
    except Exception as exc:
        state["reconcile_error"] = type(exc).__name__
    return state


def tenant_ready(tenant):
    if not TENANT_RE.fullmatch(tenant or ""):
        return False
    project = f"cloudif_{tenant}"
    for service in ("studio", "auth", "kong"):
        try:
            result = subprocess.run(
                [
                    "docker", "ps",
                    "--filter", f"label=com.docker.compose.project={project}",
                    "--filter", f"label=com.docker.compose.service={service}",
                    "--format", "{{.ID}}",
                ],
                text=True,
                capture_output=True,
                timeout=8,
            )
        except Exception:
            return False
        if result.returncode != 0 or not result.stdout.strip():
            return False
    return True


def tail_log(tenant, lines=120):
    p = log_file(tenant)
    if not p.exists():
        return "Ainda não há log para este tenant."

    try:
        out = subprocess.check_output(
            ["bash", "-lc", f"tail -n {int(lines)} {str(p)}"],
            text=True,
            timeout=5,
        )
        return out[-16000:]
    except Exception as e:
        return f"Erro ao ler log: {e}"


def refresh_state(tenant):
    st = read_state(tenant)

    if tenant_ready(tenant):
        st["state"] = "ready"
        st["message"] = "Ambiente pronto."
        st = enqueue_tenant_reconcile(tenant, st)
        write_state(tenant, st)
        return st

    if is_unit_active(tenant):
        st["state"] = "running"
        st["message"] = "Preparando ambiente. Aguarde; uma nova tentativa está bloqueada."
        st["unit"] = unit_name(tenant)
        write_state(tenant, st)
        return st

    if st.get("state") == "running":
        log = tail_log(tenant, 180)
        if "OK: AUTO ENSURE FINALIZADO" in log or tenant_ready(tenant):
            st["state"] = "ready"
            st["message"] = "Ambiente pronto."
            st = enqueue_tenant_reconcile(tenant, st)
        else:
            st["state"] = "failed"
            st["message"] = f"A preparação parou antes de concluir. Unit: {unit_status(tenant)}"
        write_state(tenant, st)

    return read_state(tenant)


def start_job(tenant, action):
    if is_unit_active(tenant):
        st = refresh_state(tenant)
        st["message"] = "Já existe uma preparação em andamento. Nova tentativa bloqueada."
        write_state(tenant, st)
        return st

    lf = log_file(tenant)
    cmd = (
        f"exec >>'{lf}' 2>&1; "
        f"echo; echo '###############################################################################'; "
        f"echo '# CloudIF job iniciado em {now()} action={action} tenant={tenant}'; "
        f"echo '###############################################################################'; "
        f"TERM=xterm HOME=/root SHELL=/bin/bash "
        f"CLOUDIF_PUBLIC_HOST='{PUBLIC_HOST}' "
        f"CLOUDIF_PUBLIC_PREFIX='{PUBLIC_PREFIX}' "
        f"PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' "
        f"'{ENSURE}' '{tenant}' '{action}'"
    )

    subprocess.run(["systemctl", "reset-failed", unit_name(tenant)], capture_output=True)

    r = subprocess.run(
        [
            "systemd-run",
            "--unit", unit_name(tenant),
            "--description", f"CloudIF Supabase ensure {tenant}",
            "--property", "WorkingDirectory=/srv/cloudif",
            "--property", "Restart=no",
            "/bin/bash", "-lc", cmd,
        ],
        text=True,
        capture_output=True,
    )

    if r.returncode != 0:
        st = {
            "state": "failed",
            "message": "Falha ao iniciar preparação em background.",
            "stdout": r.stdout,
            "stderr": r.stderr,
            "unit": unit_name(tenant),
        }
        write_state(tenant, st)
        return st

    st = {
        "state": "running",
        "message": "Preparação iniciada em segundo plano.",
        "action": action,
        "unit": unit_name(tenant),
        "started_at": now(),
        "log": str(lf),
    }
    write_state(tenant, st)
    return st


def stop_job(tenant):
    subprocess.run(["systemctl", "stop", unit_name(tenant)], capture_output=True)

    st = read_state(tenant)
    st["state"] = "cancelled"
    st["message"] = "Preparação cancelada pelo usuário. Containers já criados não foram apagados automaticamente."
    st["cancelled_at"] = now()
    write_state(tenant, st)
    return st


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_session():
    expiry = int(time.time()) + SESSION_TTL
    payload = f"{expiry}:{secrets.token_urlsafe(18)}"
    sig = hmac.new(TOKEN.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{_b64(payload.encode())}.{_b64(sig)}"


def session_from_request(handler):
    if not TOKEN:
        return None
    cookies = {}
    for part in (handler.headers.get("Cookie") or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    value = cookies.get(SESSION_COOKIE, "")
    if "." not in value:
        return None
    payload_b64, sig_b64 = value.split(".", 1)
    try:
        payload = _unb64(payload_b64).decode()
        supplied_sig = _unb64(sig_b64)
        expected_sig = hmac.new(TOKEN.encode(), payload.encode(), hashlib.sha256).digest()
        expiry = int(payload.split(":", 1)[0])
    except Exception:
        return None
    if expiry < int(time.time()) or not hmac.compare_digest(supplied_sig, expected_sig):
        return None
    return value


def csrf_for_session(session):
    return _b64(hmac.new(TOKEN.encode(), f"csrf:{session}".encode(), hashlib.sha256).digest())


def token_auth(handler, qs):
    if not TOKEN:
        return False
    candidates = []
    legacy = qs.get("t", [""])[0].strip()
    if legacy:
        candidates.append(legacy)
    bearer = (handler.headers.get("Authorization") or "").strip()
    if bearer.lower().startswith("bearer "):
        candidates.append(bearer[7:].strip())
    header_token = (handler.headers.get("X-CloudIF-Token") or "").strip()
    if header_token:
        candidates.append(header_token)
    return any(hmac.compare_digest(candidate, TOKEN) for candidate in candidates)


def valid_token(handler, qs):
    return bool(session_from_request(handler) or token_auth(handler, qs))


def button(url, label, danger=False):
    color = "#b00020" if danger else "#0b5fff"
    return f'<a class="btn" style="background:{color}" href="{html.escape(url)}">{html.escape(label)}</a>'


def form_button(action, label, csrf, danger=False, confirm=False):
    color = "#b00020" if danger else "#0b5fff"
    confirm_field = '<input type="hidden" name="confirm" value="1">' if confirm else ""
    return (
        f'<form method="post" action="{html.escape(action)}" style="display:inline">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf)}">'
        f'{confirm_field}'
        f'<button class="btn" style="background:{color};border:0;cursor:pointer" type="submit">'
        f'{html.escape(label)}</button></form>'
    )


def render_page(title, body, refresh=None):
    meta = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta}
<title>{html.escape(title)}</title>
<style>
body {{
  font-family: Arial, sans-serif;
  background: #f5f6fa;
  color: #1f2937;
  padding: 30px;
}}
.card {{
  max-width: 1000px;
  margin: auto;
  background: white;
  padding: 28px;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0,0,0,.08);
}}
.status {{
  display: inline-block;
  padding: 8px 12px;
  border-radius: 999px;
  background: #eef2ff;
  color: #1e40af;
  font-weight: bold;
}}
.btn {{
  display: inline-block;
  margin: 8px 8px 8px 0;
  padding: 12px 16px;
  color: white;
  border-radius: 8px;
  text-decoration: none;
  font-weight: bold;
}}
.ok {{
  padding: 14px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 10px;
}}
.warn {{
  padding: 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
}}
.err {{
  padding: 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
}}
pre {{
  background: #111827;
  color: #e5e7eb;
  padding: 16px;
  border-radius: 10px;
  overflow: auto;
  max-height: 440px;
}}
.small {{ color: #6b7280; }}
</style>
</head>
<body>
<div class="card">
{body}
</div>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Never persist authentication tokens embedded in legacy query strings.
        message = fmt % args
        message = re.sub(r"([?&]t=)[^&\s]+", r"\1<redacted>", message)
        print(f"[{now()}] {self.client_address[0]} - {message}", flush=True)

    def send_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, title, body, refresh=None, clear_session=False):
        page = render_page(title, body, refresh).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if clear_session:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; Path=/cloudif/supabase/; HttpOnly; Secure; SameSite=Strict")
        self.send_security_headers()
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def redirect(self, url, session=None):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        if session:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}={session}; Max-Age={SESSION_TTL}; Path=/cloudif/supabase/; HttpOnly; Secure; SameSite=Strict")
        self.send_security_headers()
        self.end_headers()

    def parse_request_path(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        return parsed, qs

    def tenant_from(self, path, prefix):
        m = re.match(rf"^{re.escape(prefix)}/([^/]+)$", path)
        if not m:
            return None
        tenant = urllib.parse.unquote(m.group(1)).strip()
        if not TENANT_RE.match(tenant):
            return None
        return tenant

    def render_status(self, tenant, qs):
        st = refresh_state(tenant)
        session = session_from_request(self)
        csrf = csrf_for_session(session) if session else ""

        launch = f"/cloudif/supabase/launch/{tenant}"
        status = f"/cloudif/supabase/status/{tenant}"
        cancel = f"/cloudif/supabase/cancel/{tenant}"

        state = st.get("state", "unknown")

        if state == "ready":
            box = f"""
<div class="ok">
<b>Ambiente pronto.</b><br>
Você será redirecionado para o Supabase.
</div>
<p>{button(public_url(tenant), "Abrir Supabase")}</p>
<script>
setTimeout(function() {{
  window.location.href = {json.dumps(public_url(tenant))};
}}, 1800);
</script>
"""
            refresh = 2
        elif state == "running":
            box = f"""
<div class="warn">
<b>Preparação em andamento.</b><br>
Uma operação já está ativa para este usuário. Para evitar conflito em containers e volumes,
uma nova tentativa foi bloqueada.
</div>
<p>
{button(status, "Atualizar status")}
{form_button(cancel, "Cancelar preparação", csrf, danger=True)}
</p>
<p class="small">Esta página atualiza automaticamente a cada 5 segundos.</p>
"""
            refresh = 5
        elif state == "confirm_cancel":
            box = f"""
<div class="err">
<b>Confirmar cancelamento?</b><br>
Cancelar interrompe a preparação em andamento. Containers já criados podem continuar existindo
e depois poderão ser reparados pelo launch.
</div>
<p>
{button(status, "Não cancelar")}
{form_button(cancel, "Sim, cancelar agora", csrf, danger=True, confirm=True)}
</p>
"""
            refresh = None
        elif state == "cancelled":
            box = f"""
<div class="warn">
<b>Preparação cancelada.</b><br>
Você pode iniciar uma nova checagem/reparo quando desejar.
</div>
<p>
{form_button(launch, "Iniciar novamente", csrf)}
{button(public_url(tenant), "Tentar abrir Supabase")}
</p>
"""
            refresh = None
        elif state == "failed":
            box = f"""
<div class="err">
<b>A preparação falhou.</b><br>
Você pode tentar reparar. Se houver uma operação presa, cancele antes.
</div>
<p>
{form_button(launch, "Tentar reparar", csrf)}
{form_button(cancel, "Cancelar operação presa", csrf, danger=True)}
</p>
"""
            refresh = None
        else:
            box = f"""
<div class="warn">
<b>Ambiente ainda não preparado ou estado desconhecido.</b>
</div>
<p>{form_button(launch, "Iniciar preparação", csrf)}</p>
"""
            refresh = None

        log = html.escape(tail_log(tenant, 120))

        body = f"""
<h1>CloudIF Supabase</h1>
<p><span class="status">Status: {html.escape(state)}</span></p>
<p>{form_button("/cloudif/supabase/logout", "Encerrar sessão", csrf, danger=True)}</p>
{box}

<h2>Detalhes</h2>
<ul>
<li><b>Tenant:</b> {html.escape(tenant)}</li>
<li><b>Mensagem:</b> {html.escape(str(st.get("message", "")))}</li>
<li><b>Unit:</b> {html.escape(str(st.get("unit", unit_name(tenant))))}</li>
<li><b>Ação:</b> {html.escape(str(st.get("action", "-")))}</li>
<li><b>URL pública:</b> {html.escape(public_url(tenant))}</li>
<li><b>Atualizado:</b> {html.escape(str(st.get("updated_at", "-")))}</li>
</ul>

<h2>Log</h2>
<pre>{log}</pre>
"""
        self.send_html(200, "CloudIF Supabase", body, refresh)


    def do_HEAD(self):

        """

        Suporte CloudIF: responde HEAD para health-checks/proxies.

        Não dispara criação de tenant.

        """

        try:

            self.send_response(200)

            self.send_header("Content-Type", "text/plain; charset=utf-8")

            self.send_header("Cache-Control", "no-store")
            self.send_security_headers()

            self.end_headers()

        except Exception:

            pass


    def do_GET(self):
        parsed, qs = self.parse_request_path()

        if parsed.path == "/health":
            return self.send_json(
                200,
                {
                    "ok": True,
                    "service": "cloudif-supabase-launch-api",
                    "mode": "status-cancel",
                    "ensure": ENSURE,
                    "public_host": PUBLIC_HOST,
                    "public_prefix": PUBLIC_PREFIX,
                    "token_configured": bool(TOKEN),
                },
            )

        tenant = self.tenant_from(parsed.path, "/cloudif/supabase/status")
        if tenant is not None:
            session = session_from_request(self)
            if not session and token_auth(self, qs):
                session = make_session()
                return self.redirect(f"/cloudif/supabase/status/{tenant}", session=session)
            if not session:
                return self.send_json(403, {"ok": False, "error": "invalid_session"})
            return self.render_status(tenant, {})

        if parsed.path == "/cloudif/supabase/logout":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Cache-Control", "no-store")
            self.send_security_headers()
            self.end_headers()
            return

        for prefix in ("/cloudif/supabase/launch", "/cloudif/supabase/cancel"):
            if self.tenant_from(parsed.path, prefix) is not None:
                self.send_response(405)
                self.send_header("Allow", "POST")
                self.send_header("Cache-Control", "no-store")
                self.send_security_headers()
                self.end_headers()
                return

        return self.send_json(404, {"ok": False, "error": "not_found", "path": parsed.path})

    def do_POST(self):
        parsed, qs = self.parse_request_path()
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"ok": False, "error": "invalid_content_length"})
        if length < 0 or length > 8192:
            return self.send_json(413, {"ok": False, "error": "request_too_large"})
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            return self.send_json(415, {"ok": False, "error": "unsupported_media_type"})
        raw = self.rfile.read(length).decode("utf-8", errors="strict")
        form = urllib.parse.parse_qs(raw, keep_blank_values=True)
        params = {**qs, **form}

        if parsed.path == "/cloudif/supabase/logout":
            session = session_from_request(self)
            if not session:
                return self.send_json(403, {"ok": False, "error": "invalid_session"})
            supplied_csrf = params.get("csrf", [""])[0]
            if not supplied_csrf or not hmac.compare_digest(supplied_csrf, csrf_for_session(session)):
                return self.send_json(403, {"ok": False, "error": "invalid_csrf"})
            body = """
<h1>Sessão encerrada</h1>
<div class="ok"><b>A sessão da Launch API foi encerrada com segurança.</b></div>
<p class="small">Retorne ao portal para iniciar uma nova sessão quando necessário.</p>
"""
            return self.send_html(200, "Sessão encerrada", body, clear_session=True)

        routes = {
            "/cloudif/supabase/launch": "launch",
            "/cloudif/supabase/cancel": "cancel",
        }
        for prefix, action in routes.items():
            tenant = self.tenant_from(parsed.path, prefix)
            if tenant is None:
                continue
            session = session_from_request(self)
            header_authenticated = token_auth(self, {})
            if not session and not header_authenticated:
                return self.send_json(403, {"ok": False, "error": "invalid_session"})
            if session:
                supplied_csrf = params.get("csrf", [""])[0]
                if not supplied_csrf or not hmac.compare_digest(supplied_csrf, csrf_for_session(session)):
                    return self.send_json(403, {"ok": False, "error": "invalid_csrf"})

            if action == "launch":
                st = refresh_state(tenant)
                if st.get("state") == "ready" and tenant_ready(tenant):
                    return self.redirect(public_url(tenant))
                if st.get("state") != "running":
                    start_job(tenant, "ensure")
                return self.render_status(tenant, params)

            if params.get("confirm", ["0"])[0] != "1":
                st = read_state(tenant)
                st["state"] = "confirm_cancel"
                st["message"] = "Confirme se deseja cancelar a preparação em andamento."
                write_state(tenant, st)
                return self.render_status(tenant, params)

            stop_job(tenant)
            return self.render_status(tenant, params)

        return self.send_json(404, {"ok": False, "error": "not_found", "path": parsed.path})


if __name__ == "__main__":
    print(f"[{now()}] CloudIF launch API listening on {HOST}:{PORT}", flush=True)
    print(f"[{now()}] mode=status-cancel ensure={ENSURE}", flush=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
