#!/usr/bin/env bash
set -Eeuo pipefail

CONF="${1:-/srv/cloudif/router/conf.d/default.conf}"
ROUTER="${CLOUDIF_ROUTER_CONTAINER:-cloudif-tenant-router}"
AUTHZ_UPSTREAM="${CLOUDIF_AUTHZ_UPSTREAM:-10.62.92.7:18093}"
STAMP="$(date +%F-%H%M%S)"

echo "------------------------------------------------------------"
echo " CloudIF Apply Router AuthZ v244"
echo "------------------------------------------------------------"
echo "CONF=$CONF"
echo "AUTHZ_UPSTREAM=$AUTHZ_UPSTREAM"

test -f "$CONF" || { echo "ERRO: não existe $CONF"; exit 1; }

cp -a "$CONF" "$CONF.bkp-apply-authz-v244-$STAMP"

python3 - "$CONF" "$AUTHZ_UPSTREAM" <<'PY'
from pathlib import Path
import re
import sys

conf = Path(sys.argv[1])
authz_upstream = sys.argv[2]
txt = conf.read_text(errors="ignore")

patterns = [
    r'\n\s*# CloudIF v250 root redirect BEGIN.*?# CloudIF v250 root redirect END\n',
    r'\n\s*# CloudIF v256 router warmup BEGIN.*?# CloudIF v256 router warmup END\n',

    r'\n\s*# CloudIF v22[0-9] forward-auth locations BEGIN.*?# CloudIF v22[0-9] forward-auth locations END\n',
    r'\n\s*# CloudIF v22[0-9] project-auth BEGIN.*?# CloudIF v22[0-9] project-auth END\n',
    r'\n\s*# CloudIF v23[0-9] authz locations BEGIN.*?# CloudIF v23[0-9] authz locations END\n',
    r'\n\s*# CloudIF v23[0-9] tenant-auth BEGIN.*?# CloudIF v23[0-9] tenant-auth END\n',
    r'\n\s*# CloudIF v244 authz locations BEGIN.*?# CloudIF v244 authz locations END\n',
    r'\n\s*# CloudIF v244 tenant-auth BEGIN.*?# CloudIF v244 tenant-auth END\n',
]
for pat in patterns:
    txt = re.sub(pat, '\n', txt, flags=re.S)

authz_locations = '''
    # CloudIF v244 authz locations BEGIN

    location = /cloudiff/authz {{
        internal;
        proxy_pass http://__AUTHZ_UPSTREAM__/authz;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";

        proxy_set_header Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Uri $request_uri;
        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header X-Original-URL https://$http_host$request_uri;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_intercept_errors on;
        recursive_error_pages on;
        error_page 301 302 303 307 308 = @cloudif_authz_as_401_v244;
    }}

    location @cloudif_authz_as_401_v244 {{
        internal;
        return 401;
    }}

    location ^~ /outpost.goauthentik.io/ {{
        proxy_pass http://10.62.91.2:9000/outpost.goauthentik.io/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_set_header X-Original-URL https://$http_host$request_uri;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-Uri $request_uri;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location @cloudif_authentik_signin_v244 {{
        internal;
        return 302 /outpost.goauthentik.io/start?rd=https://$http_host$request_uri;
    }}

    location @cloudif_forbidden_v244 {{
        internal;
        default_type text/html;

        if ($cloudif_authz_reason = tenant-provisioning) {{
            return 202 '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="5"><title>CloudIF preparando ambiente</title><style>body{margin:0;background:#0f172a;color:#e5e7eb;font-family:system-ui,Arial}.box{max-width:680px;margin:10vh auto;padding:28px}.card{background:#172033;border:1px solid #334155;border-radius:18px;padding:28px;box-shadow:0 20px 50px #0005}.bar{height:14px;background:#334155;border-radius:999px;overflow:hidden}.fill{height:100%;width:72%;background:linear-gradient(90deg,#22c55e,#38bdf8);animation:p 2s ease-in-out infinite alternate}@keyframes p{from{width:35%}to{width:88%}}.steps{line-height:1.9}.ok{color:#86efac}.wait{color:#7dd3fc}small{color:#94a3b8}</style></head><body><div class="box"><div class="card"><h2>CloudIF está preparando seu ambiente</h2><p>Estamos concluindo a configuração necessária para abrir este recurso.</p><div class="bar"><div class="fill"></div></div><div class="steps"><div class="ok">✓ Identidade reconhecida</div><div class="ok">✓ Permissões verificadas</div><div class="wait">● Inicializando serviços do tenant</div><div>○ Validando banco e API</div><div>○ Abrindo o ambiente</div></div><p><b>Tenant:</b> $cloudif_tenant<br><b>Ação:</b> $cloudif_provision_action<br><b>Status:</b> $cloudif_provision_message</p><small>A página atualiza automaticamente a cada 5 segundos. Caso permaneça nesta etapa por mais de dois minutos, volte ao Portal CloudIF e tente novamente.</small></div></div></body></html>';
        }}

        return 403 'CloudIF: sessão autenticada, mas sem permissão para este tenant.<br>Tenant: $cloudif_tenant<br>Motivo: $cloudif_authz_reason<br>';
    }}

    # CloudIF v244 authz locations END

'''.replace('__AUTHZ_UPSTREAM__', authz_upstream).replace('{{', '{').replace('}}', '}')

auth_snippet = '''        # CloudIF v244 tenant-auth BEGIN
        auth_request /cloudiff/authz;
        error_page 401 = @cloudif_authentik_signin_v244;
        error_page 403 = @cloudif_forbidden_v244;

        auth_request_set $auth_cookie $upstream_http_set_cookie;
        add_header Set-Cookie $auth_cookie always;

        auth_request_set $authentik_username $upstream_http_x_authentik_username;
        auth_request_set $authentik_email $upstream_http_x_authentik_email;
        auth_request_set $authentik_groups $upstream_http_x_authentik_groups;
        auth_request_set $cloudif_authz_reason $upstream_http_x_cloudif_authz_reason;
        auth_request_set $cloudif_tenant $upstream_http_x_cloudif_tenant;
        auth_request_set $cloudif_provision_action $upstream_http_x_cloudif_provision_action;
        auth_request_set $cloudif_provision_message $upstream_http_x_cloudif_provision_message;

        add_header X-CloudIF-AuthZ $cloudif_authz_reason always;

        proxy_set_header X-authentik-username $authentik_username;
        proxy_set_header X-authentik-email $authentik_email;
        proxy_set_header X-authentik-groups $authentik_groups;
        # CloudIF v244 tenant-auth END
'''


# CloudIF v250: tenant ativo abre o Studio; domínio institucional abre o Portal.
root_redirect_v250 = """
    # CloudIF v250 root redirect BEGIN
    location = / {
        if ($cloudif_kong_port != "") { return 302 /project/default; }
        return 302 /cloudiff/portal/;
    }
    # CloudIF v250 root redirect END

"""
authz_locations = authz_locations + root_redirect_v250


# CloudIF v256: adiciona named location de warmup no router
router_warmup_v256 = """
    # CloudIF v256 router warmup BEGIN

    # Evita entregar HTML inicial do Supabase antes dos assets/API estarem estáveis.
    # Primeira passagem: define cookie curto e mostra tela leve.
    # Segunda passagem: libera o proxy normal.
    location @cloudif_router_warmup_v256 {
        internal;
        default_type text/html;
        add_header Set-Cookie "cloudif_router_warmup=1; Path=/; Max-Age=20; Secure; HttpOnly; SameSite=Lax" always;
        return 202 '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="5"><title>CloudIF preparando ambiente</title><style>body{margin:0;background:#0f172a;color:#e5e7eb;font-family:system-ui,Arial}.box{max-width:680px;margin:10vh auto;padding:28px}.card{background:#172033;border:1px solid #334155;border-radius:18px;padding:28px;box-shadow:0 20px 50px #0005}.bar{height:14px;background:#334155;border-radius:999px;overflow:hidden}.fill{height:100%;width:72%;background:linear-gradient(90deg,#22c55e,#38bdf8);animation:p 2s ease-in-out infinite alternate}@keyframes p{from{width:35%}to{width:88%}}.steps{line-height:1.9}.ok{color:#86efac}.wait{color:#7dd3fc}small{color:#94a3b8}</style></head><body><div class="box"><div class="card"><h2>CloudIF está preparando seu ambiente</h2><p>Estamos concluindo a configuração necessária para abrir este recurso.</p><div class="bar"><div class="fill"></div></div><div class="steps"><div class="ok">✓ Identidade reconhecida</div><div class="ok">✓ Permissões verificadas</div><div class="wait">● Inicializando serviços do tenant</div><div>○ Validando banco e API</div><div>○ Abrindo o ambiente</div></div><p><b>Status:</b> Aguarde 5 segundos para estabilizar o ambiente.</p><small>A página atualiza automaticamente. Caso permaneça nesta etapa por mais de dois minutos, volte ao Portal CloudIFF e tente novamente.</small></div></div></body></html>';
    }

    # CloudIF v256 router warmup END

"""
authz_locations = authz_locations + router_warmup_v256

marker = "    location = /health"
if marker not in txt:
    raise SystemExit("ERRO: não achei location = /health")
txt = txt.replace(marker, authz_locations + marker, 1)

lines = txt.splitlines()
out = []
inserted = 0
in_protected = False
depth = 0

for i, line in enumerate(lines):
    s = line.strip()

    if s == "location ^~ /project/ {":
        in_protected = True
        depth = line.count("{") - line.count("}")
        out.append(line)
        out.append("""
        # CloudIF v256 router warmup antes do Supabase HTML
        if ($cookie_cloudif_router_warmup = "") {
            return 418;
        }
        error_page 418 = @cloudif_router_warmup_v256;""")
        lookahead = "\n".join(lines[i:i+55])
        if "CloudIF v244 tenant-auth BEGIN" not in lookahead and "CloudIF v233 tenant-auth BEGIN" not in lookahead:
            out.append(auth_snippet.rstrip("\n"))
            inserted += 1
        continue

    if s == "location ^~ /api/ {":
        in_protected = True
        depth = line.count("{") - line.count("}")
        out.append(line)
        lookahead = "\n".join(lines[i:i+55])
        if "CloudIF v244 tenant-auth BEGIN" not in lookahead:
            out.append(auth_snippet.rstrip("\n"))
            inserted += 1
        continue

    if in_protected:
        # Evita que tenant sem porta volte para login antes do guard iniciar criação.
        if "cloudif_kong_port" in line and "return" in line:
            out.append("        # CloudIF v244 disabled missing-kong early return: " + line.strip())
        else:
            out.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            in_protected = False
        continue

    out.append(line)

if inserted < 2:
    raise SystemExit(f"ERRO: esperava proteger /project/ e /api/, mas inseri {inserted}")

conf.write_text("\n".join(out) + "\n")
print(f"OK: CloudIF AuthZ v244 aplicado em {inserted} locations.")
PY

docker exec "$ROUTER" nginx -t
docker exec "$ROUTER" nginx -s reload

if [ -x /srv/cloudif/bin/cloudif-tune-router-nginx-limits-v238.sh ]; then
  /srv/cloudif/bin/cloudif-tune-router-nginx-limits-v238.sh
fi

echo "OK: AuthZ v244 aplicado ao router."

# CloudIF v253 missing upstream post-apply BEGIN
if [ -x /srv/cloudif/bin/cloudif-apply-router-missing-upstream-v253.sh ]; then
  /srv/cloudif/bin/cloudif-apply-router-missing-upstream-v253.sh /srv/cloudif/router/conf.d/default.conf || {
    echo "ERRO: CloudIF missing upstream guard v253 falhou" >&2
    exit 1
  }
fi
# CloudIF v253 missing upstream post-apply END
