#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOMAIN = os.environ.get("CLOUDIF_DOMAIN", "cloudiff.duckdns.org").lower()
AUTHZ_URL = os.environ.get("CLOUDIF_AUTHZ_URL", "http://10.62.92.7:18092/authz")
LISTEN_HOST = os.environ.get("CLOUDIF_GUARD_HOST", "10.62.92.7")
LISTEN_PORT = int(os.environ.get("CLOUDIF_GUARD_PORT", "18093"))
BASE = os.environ.get("CLOUDIF_BASE", "/srv/cloudif")
STATUS_DIR = os.environ.get("CLOUDIF_STATUS_DIR", "/var/lib/cloudif/provision/status")
ENSURE_SCRIPT = os.environ.get("CLOUDIF_ENSURE_SCRIPT", "/usr/local/sbin/cloudif-tenant-ensure-bg.sh")

HEALTH_CACHE_TTL = int(os.environ.get("CLOUDIF_HEALTH_CACHE_TTL", "30"))
HEALTH_TIMEOUT = int(os.environ.get("CLOUDIF_GUARD_HEALTH_TIMEOUT", "8"))
HEALTH_RETRIES = int(os.environ.get("CLOUDIF_GUARD_HEALTH_RETRIES", "3"))
HEALTH_RETRY_SLEEP = int(os.environ.get("CLOUDIF_GUARD_HEALTH_RETRY_SLEEP", "2"))
RESTORE_COOLDOWN = int(os.environ.get("CLOUDIF_GUARD_RESTORE_COOLDOWN", "300"))
SUSPECT_SECONDS = int(os.environ.get("CLOUDIF_GUARD_SUSPECT_SECONDS", "45"))
READY_GRACE = int(os.environ.get("CLOUDIF_GUARD_READY_GRACE", "180"))
STABILIZE_SECONDS = int(os.environ.get("CLOUDIF_GUARD_STABILIZE_SECONDS", "20"))
WARMUP_SECONDS = int(os.environ.get("CLOUDIF_GUARD_WARMUP_SECONDS", "5"))
WARMUP_TTL = int(os.environ.get("CLOUDIF_GUARD_WARMUP_TTL", "20"))

HEALTH_CACHE = {}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def log(msg):
    print(msg, flush=True)

def clean_host(value):
    value = (value or "").strip().lower()
    if "," in value:
        value = value.split(",", 1)[0].strip()
    if ":" in value:
        value = value.split(":", 1)[0].strip()
    return value

def valid_tenant(tenant):
    return bool(re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", tenant or ""))

def tenant_from_request(host, uri):
    host = clean_host(host)
    uri = uri or "/"

    suffix = "." + DOMAIN
    if host.endswith(suffix):
        tenant = host[:-len(suffix)].strip(".").lower()
        if tenant and tenant not in {"www", "authiff", "cloudiff"} and valid_tenant(tenant):
            return tenant

    parts = uri.split("/")
    if len(parts) >= 3 and parts[1] == "supabase" and parts[2]:
        tenant = parts[2].lower()
        if valid_tenant(tenant):
            return tenant

    return ""

def env_value(path, key):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        return ""
    return ""

def status_path(tenant):
    return os.path.join(STATUS_DIR, f"{tenant}.env")

def read_status(tenant):
    data = {}
    path = status_path(tenant)
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "=" in line:
                    k, v = line.rstrip("\n").split("=", 1)
                    data[k] = v
        data["_mtime"] = os.path.getmtime(path)
    except FileNotFoundError:
        data["_mtime"] = 0
    return data

def write_status(tenant, action, state, message):
    os.makedirs(STATUS_DIR, exist_ok=True)
    path = status_path(tenant)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"TENANT={tenant}\n")
        f.write(f"ACTION={action}\n")
        f.write(f"STATE={state}\n")
        f.write(f"MESSAGE={message}\n")
        f.write(f"UPDATED_AT={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")

def tenant_port(tenant):
    env = os.path.join(BASE, "tenants", tenant, ".env")
    for key in ["KONG_HTTP_PORT", "KONG_PORT", "KONG_HTTP"]:
        val = env_value(env, key)
        if val:
            return val
    return ""

def run_cmd(cmd, timeout=5):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout, text=True)
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output
    except Exception as e:
        return 99, str(e)

def docker_compose_health(tenant):
    tdir = os.path.join(BASE, "tenants", tenant)
    if not os.path.isdir(tdir):
        return False, "Tenant não existe."

    # Inclui containers parados. Sem -a, uma stack completamente desligada
    # aparece como saída vazia e fica indistinguível de erro de descoberta.
    try:
        out = subprocess.check_output(
            ["bash", "-lc", f"cd {tdir!r} && docker compose ps -a --format json"],
            stderr=subprocess.STDOUT,
            timeout=10,
            text=True,
        )
    except Exception as e:
        return False, f"docker compose ps falhou: {e}"

    if not out.strip():
        return False, "docker compose ps vazio."

    records = []
    raw = out.strip()
    try:
        if raw.startswith("["):
            parsed = json.loads(raw)
            records = parsed if isinstance(parsed, list) else [parsed]
        else:
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    except Exception:
        # Compatibilidade defensiva com versões antigas do compose.
        joined = raw.lower()
        required = {key: key in joined for key in ("kong", "studio", "db")}
        bad_words = ["exited", "dead", "removing", "restarting"]
        if any(word in joined for word in bad_words):
            return False, "Há container em estado ruim: " + ", ".join(word for word in bad_words if word in joined)
        if not all(required.values()):
            return False, f"Serviços principais ausentes no compose: {required}"
        return True, "Containers principais do tenant estão presentes e não estão em estado ruim."

    by_service = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        service = str(record.get("Service") or record.get("service") or "").strip().lower()
        if not service:
            continue
        state = str(record.get("State") or record.get("state") or "").strip().lower()
        status = str(record.get("Status") or record.get("status") or "").strip().lower()
        health = str(record.get("Health") or record.get("health") or "").strip().lower()
        try:
            exit_code = int(record.get("ExitCode", record.get("exit_code", 0)) or 0)
        except Exception:
            exit_code = -1
        by_service[service] = {"state": state, "status": status, "health": health, "exit_code": exit_code}

    required_names = ("db", "kong", "studio")
    missing = [name for name in required_names if name not in by_service]
    if missing:
        return False, "Serviços principais ausentes no compose: " + ", ".join(missing)

    required = {name: by_service[name] for name in required_names}
    running_states = {"running", "up"}
    stopped_states = {"exited", "created", "stopped"}

    if all(item["state"] in running_states for item in required.values()):
        unhealthy = [name for name, item in required.items() if item["health"] == "unhealthy"]
        if unhealthy:
            return False, "Serviços principais não saudáveis: " + ", ".join(unhealthy)
        return True, "Containers principais do tenant estão em execução."

    # Uma stack desligada de forma limpa não é corrupção. O Guard pode
    # iniciar docker compose up preservando volumes e dados existentes.
    if all(item["state"] in stopped_states for item in required.values()) and required["db"]["exit_code"] == 0:
        return False, "STACK_STOPPED_CLEAN: db, kong e studio estão parados; PostgreSQL encerrou com código 0."

    details = ", ".join(
        f"{name}={item['state'] or 'unknown'}/exit-{item['exit_code']}"
        for name, item in required.items()
    )
    return False, "Estado intermediário ou anormal dos serviços principais: " + details

def kong_port_alive(tenant):
    port = tenant_port(tenant)
    if not port:
        return False, "Porta Kong não encontrada."

    url = f"http://127.0.0.1:{port}/"
    host = f"{tenant}.{DOMAIN}"

    try:
        req = urllib.request.Request(
            url,
            headers={"Host": host, "User-Agent": "CloudIF-Tenant-Guard-Health/249"},
            method="GET",
        )
        resp = urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT)
        code = resp.getcode()
        return True, f"Kong respondeu HTTP {code}."
    except urllib.error.HTTPError as e:
        # 401/403/404/3xx confirmam que o Kong respondeu. Para saúde do tenant, isso é suficiente.
        if e.code in {301, 302, 307, 308, 401, 403, 404}:
            return True, f"Kong respondeu HTTP {e.code}, considerado vivo."
        return False, f"Kong respondeu erro HTTP {e.code}."
    except Exception as e:
        return False, f"Kong não respondeu: {e}"


def tenant_health(tenant):
    now = time.time()

    cached = HEALTH_CACHE.get(tenant)
    if cached and cached[0] > now:
        return cached[1], cached[2]

    tdir = os.path.join(BASE, "tenants", tenant)

    if not os.path.isdir(tdir):
        result = ("missing", "Tenant ainda não existe.")
        HEALTH_CACHE[tenant] = (now + 2, *result)
        return result

    st = read_status(tenant)
    if st.get("STATE") == "ready" and st.get("_mtime", 0) and now - st["_mtime"] <= READY_GRACE:
        result = ("healthy", "Tenant marcado como pronto recentemente.")
        HEALTH_CACHE[tenant] = (now + HEALTH_CACHE_TTL, *result)
        return result

    compose_ok, compose_msg = docker_compose_health(tenant)
    kong_ok, kong_msg = kong_port_alive(tenant)

    if compose_ok and kong_ok:
        result = ("healthy", compose_msg + " " + kong_msg)
        HEALTH_CACHE[tenant] = (now + HEALTH_CACHE_TTL, *result)
        return result

    if kong_ok:
        # Kong vivo é suficiente para não disparar restore imediato. Pode ser container secundário lento.
        result = ("healthy", "Kong está vivo. " + kong_msg + " " + compose_msg)
        HEALTH_CACHE[tenant] = (now + 15, *result)
        return result

    if compose_msg.startswith("STACK_STOPPED_CLEAN:"):
        result = ("stopped", compose_msg + " " + kong_msg)
        HEALTH_CACHE[tenant] = (now + 2, *result)
        return result

    result = ("slow", compose_msg + " " + kong_msg)
    HEALTH_CACHE[tenant] = (now + 5, *result)
    return result

def existing_tenant_recovery_decision(health, state, age, current_action="", current_message=""):
    """Return the next recovery decision without performing side effects."""
    in_progress = {"running", "creating", "restoring", "waiting_health"}
    if health == "stopped":
        if state in in_progress and age < RESTORE_COOLDOWN:
            return {
                "action": current_action or "restore",
                "state": state or "restoring",
                "message": current_message or "Inicialização do tenant já está em andamento.",
                "write": False,
                "trigger": False,
            }
        return {
            "action": "restore",
            "state": "restoring",
            "message": "Tenant estava parado de forma limpa. Iniciando ambiente em segundo plano.",
            "write": True,
            "trigger": True,
        }
    if state in in_progress and age < RESTORE_COOLDOWN:
        return {
            "action": current_action or "checking",
            "state": state,
            "message": current_message or "Tarefa anterior ainda está em andamento.",
            "write": False,
            "trigger": False,
        }
    if state == "suspect" and age >= SUSPECT_SECONDS:
        return {
            "action": "restore",
            "state": "restoring",
            "message": "Falha confirmada. Restaurando ambiente em segundo plano.",
            "write": True,
            "trigger": True,
        }
    if state == "suspect":
        return {
            "action": "checking",
            "state": "suspect",
            "message": current_message or "Tenant instável. Aguardando confirmação antes de restaurar.",
            "write": False,
            "trigger": False,
        }
    return {
        "action": "checking",
        "state": "suspect",
        "message": "Tenant existe, mas respondeu lentamente. Aguardando estabilização antes de restaurar.",
        "write": True,
        "trigger": False,
    }


def warmup_path(tenant, username):
    safe_user = (username or "unknown").replace("/", "_")
    return os.path.join(STATUS_DIR, f"{tenant}.warmup.{safe_user}")

def need_warmup_once(tenant, username):
    """
    Retorna True uma única vez por janela curta.
    Serve para evitar liberar o Studio no primeiro retorno do Authentik,
    quando o navegador dispara várias chamadas e o proxy ainda pode estar estabilizando.
    """
    if WARMUP_SECONDS <= 0:
        return False

    path = warmup_path(tenant, username)
    now = time.time()

    try:
        mtime = os.path.getmtime(path)
        if now - mtime <= WARMUP_TTL:
            return False
    except FileNotFoundError:
        pass

    try:
        os.makedirs(STATUS_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(now))
    except Exception:
        pass

    return True



# CloudIF v2 create permission helpers BEGIN
def _cloudif_v2_split_csv(s):
    return [x.strip() for x in (s or "").replace(";", ",").split(",") if x.strip()]

def _cloudif_v2_norm(s):
    return (s or "").strip().lower()

def _cloudif_v2_admin_users():
    return {_cloudif_v2_norm(x) for x in _cloudif_v2_split_csv(os.environ.get("CLOUDIF_ADMIN_USERS", ""))}

def _cloudif_v2_admin_groups():
    base = {_cloudif_v2_norm(x) for x in _cloudif_v2_split_csv(os.environ.get("CLOUDIF_ADMIN_GROUPS", ""))}
    base.update({"cloudif-tenants-admin", "cloudif-professor", "domain admins", "enterprise admins", "administrators"})
    return base

def _cloudif_v2_create_groups():
    raw = os.environ.get("CLOUDIF_TENANT_CREATE_GROUPS", "CloudIF-Tenants,CloudIF-Tenants-Admin")
    return {_cloudif_v2_norm(x) for x in _cloudif_v2_split_csv(raw)}

def _cloudif_v2_can_create_tenant(username, groups, tenant):
    u = _cloudif_v2_norm(username)
    t = _cloudif_v2_norm(tenant)
    gs = {_cloudif_v2_norm(g) for g in _cloudif_v2_split_csv(groups)}
    if u in _cloudif_v2_admin_users() or gs.intersection(_cloudif_v2_admin_groups()):
        return True, "admin-create"
    if gs.intersection(_cloudif_v2_create_groups()):
        return True, "create-group"
    if os.environ.get("CLOUDIF_OWNER_CAN_CREATE", "0").strip() == "1" and u == t:
        return True, "owner-create"
    return False, "no-create-permission"
# CloudIF v2 create permission helpers END

def trigger_background(tenant, action, username):
    subprocess.Popen(
        [ENSURE_SCRIPT, tenant, action, username or "unknown"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def call_authz(headers):
    req_headers = {
        "Host": headers.get("Host", ""),
        "Cookie": headers.get("Cookie", ""),
        "X-Forwarded-Host": headers.get("X-Forwarded-Host", headers.get("Host", "")),
        "X-Forwarded-Proto": headers.get("X-Forwarded-Proto", "https"),
        "X-Forwarded-Uri": headers.get("X-Forwarded-Uri", headers.get("X-Original-URI", "/")),
        "X-Original-URI": headers.get("X-Original-URI", "/"),
        "X-Original-URL": headers.get("X-Original-URL", ""),
        "X-Real-IP": headers.get("X-Real-IP", ""),
        "X-Forwarded-For": headers.get("X-Forwarded-For", ""),
    }

    req = urllib.request.Request(AUTHZ_URL, headers=req_headers, method="GET")

    try:
        resp = OPENER.open(req, timeout=8)
        return resp.getcode(), resp.headers, ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        return e.code, e.headers, body
    except Exception as e:
        return 500, {"X-CloudIF-AuthZ-Reason": "guard-authz-error"}, str(e)

class Handler(BaseHTTPRequestHandler):
    server_version = "CloudIFTenantGuard/247"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/authz":
            self.send_response(404)
            self.end_headers()
            return

        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        uri = self.headers.get("X-Original-URI") or "/"
        tenant = tenant_from_request(host, uri)

        status, auth_headers, auth_body = call_authz(self.headers)

        if status != 204:
            self.send_response(status)
            for k in [
                "Set-Cookie",
                "X-CloudIF-AuthZ-Reason",
                "X-CloudIF-Tenant",
                "X-Authentik-Username",
                "X-Authentik-Email",
                "X-Authentik-Groups",
            ]:
                v = auth_headers.get(k)
                if v:
                    self.send_header(k, v)
            self.end_headers()
            if auth_body and self.command != "HEAD":
                self.wfile.write(auth_body.encode("utf-8"))
            return

        username = (auth_headers.get("X-Authentik-Username") or auth_headers.get("X-authentik-username") or "").strip().lower()
        email = (auth_headers.get("X-Authentik-Email") or auth_headers.get("X-authentik-email") or "").strip().lower()
        groups = auth_headers.get("X-Authentik-Groups") or auth_headers.get("X-authentik-groups") or ""

        if not tenant:
            self.send_response(403)
            self.send_header("X-CloudIF-AuthZ-Reason", "tenant-not-found")
            self.end_headers()
            return


        # CloudIF v255: warmup ANTES do health check pesado.
        # Isso evita tela branca/502 na primeira volta do Authentik.
        if need_warmup_once(tenant, username):
            self.send_response(403)
            self.send_header("X-CloudIF-AuthZ-Reason", "tenant-provisioning")
            self.send_header("X-CloudIF-Tenant", tenant)
            self.send_header("X-Authentik-Username", username)
            self.send_header("X-Authentik-Email", email)
            self.send_header("X-CloudIF-Provision-Action", "warmup")
            self.send_header("X-CloudIF-Provision-Health", "warmup")
            self.send_header("X-CloudIF-Provision-Message", f"Aguardando {WARMUP_SECONDS} segundos para estabilizar o ambiente.")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write((f"Aguardando {WARMUP_SECONDS} segundos para estabilizar o ambiente.\\n").encode("utf-8"))
            return


        health, msg = tenant_health(tenant)


        # CloudIF v253: evita liberar proxy durante janela curta de criação/restauração.
        st_recent = read_status(tenant)
        state_recent = st_recent.get("STATE", "")
        age_recent = time.time() - st_recent.get("_mtime", 0) if st_recent.get("_mtime", 0) else 999999

        if state_recent in {"running", "creating", "rendering", "restoring", "waiting_health"} and age_recent < STABILIZE_SECONDS:
            self.send_response(403)
            self.send_header("X-CloudIF-AuthZ-Reason", "tenant-provisioning")
            self.send_header("X-CloudIF-Tenant", tenant)
            self.send_header("X-Authentik-Username", username)
            self.send_header("X-Authentik-Email", email)
            self.send_header("X-CloudIF-Provision-Action", st_recent.get("ACTION", "waiting"))
            self.send_header("X-CloudIF-Provision-Health", "stabilizing")
            self.send_header("X-CloudIF-Provision-Message", st_recent.get("MESSAGE", "Ambiente estabilizando."))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(("Ambiente estabilizando. Aguarde alguns segundos e atualize a página.\n").encode("utf-8"))
            return


        if health == "healthy":
            self.send_response(204)
            for k, v in {
                "Set-Cookie": auth_headers.get("Set-Cookie", ""),
                "X-CloudIF-AuthZ-Reason": "tenant-ready",
                "X-CloudIF-Tenant": tenant,
                "X-Authentik-Username": username,
                "X-Authentik-Email": email,
                "X-Authentik-Groups": groups,
                "X-CloudIF-Provision-Action": "none",
                "X-CloudIF-Provision-Message": "Tenant pronto.",
            }.items():
                if v:
                    self.send_header(k, v)
            self.end_headers()
            return

        st = read_status(tenant)
        state = st.get("STATE", "")
        action = st.get("ACTION", "")
        age = time.time() - st.get("_mtime", 0) if st.get("_mtime", 0) else 999999

        if health == "missing":
            can_create, create_reason = _cloudif_v2_can_create_tenant(username, groups, tenant)
            if not can_create:
                self.send_response(403)
                self.send_header("X-CloudIF-AuthZ-Reason", "tenant-create-forbidden")
                self.send_header("X-CloudIF-Tenant", tenant)
                self.send_header("X-Authentik-Username", username)
                self.send_header("X-Authentik-Email", email)
                self.send_header("X-CloudIF-Provision-Action", "blocked")
                self.send_header("X-CloudIF-Provision-Health", "missing")
                self.send_header("X-CloudIF-Provision-Message", "Usuário autenticado, mas sem permissão para criar tenant CloudIF.")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(("CloudIF: você não tem permissão para criar tenant. Solicite entrada no grupo CloudIF-Tenants ou acesso a um tenant existente.\n").encode("utf-8"))
                return

            if state in {"running", "creating", "restoring", "waiting_health"} and age < RESTORE_COOLDOWN:
                action = action or "create"
                message = st.get("MESSAGE", "Criação já está em andamento.")
            else:
                action = "create"
                message = "Tenant não existe. Criando ambiente em segundo plano."
                write_status(tenant, action, "creating", message)
                trigger_background(tenant, action, username)

        else:
            decision = existing_tenant_recovery_decision(
                health,
                state,
                age,
                current_action=action,
                current_message=st.get("MESSAGE", ""),
            )
            action = decision["action"]
            message = decision["message"]
            if decision["write"]:
                write_status(tenant, action, decision["state"], message)
            if decision["trigger"]:
                trigger_background(tenant, action, username)

        self.send_response(403)
        self.send_header("X-CloudIF-AuthZ-Reason", "tenant-provisioning")
        self.send_header("X-CloudIF-Tenant", tenant)
        self.send_header("X-Authentik-Username", username)
        self.send_header("X-Authentik-Email", email)
        self.send_header("X-CloudIF-Provision-Action", action)
        self.send_header("X-CloudIF-Provision-Health", health)
        self.send_header("X-CloudIF-Provision-Message", message)
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(f"{message}\n{msg}\n".encode("utf-8"))

def main():
    os.makedirs(STATUS_DIR, exist_ok=True)
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    log(f"CloudIF Tenant Guard v247 ouvindo em {LISTEN_HOST}:{LISTEN_PORT}")
    log(f"AUTHZ_URL={AUTHZ_URL}")
    log(f"BASE={BASE}")
    log(f"HEALTH_RETRIES={HEALTH_RETRIES}")
    log(f"HEALTH_TIMEOUT={HEALTH_TIMEOUT}")
    log(f"RESTORE_COOLDOWN={RESTORE_COOLDOWN}")
    server.serve_forever()

if __name__ == "__main__":
    main()
