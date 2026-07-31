#!/usr/bin/env bash
set -euo pipefail

CONF="/srv/cloudif/router/conf.d/default.conf"
RENDER="/srv/cloudif/bin/cloudif-render-router.sh"

PUBLIC_HOST="cloudiff.duckdns.org"
ROUTER_IP="10.62.92.7"
ROUTER_PORT="8099"
ROUTER_BIND="${ROUTER_IP}:${ROUTER_PORT}"

NPM_IP="10.62.91.3"
TENANT="${1:-iff1742962}"

echo "============================================================"
echo " CLOUDIF - HARDEN TENANT ROUTER 8099"
echo " Conf:       $CONF"
echo " Bind novo:  $ROUTER_BIND"
echo " NPM IP:     $NPM_IP"
echo " Tenant:     $TENANT"
echo "============================================================"

if [ ! -f "$CONF" ]; then
  echo "ERRO: não encontrei $CONF"
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
cp -a "$CONF" "$CONF.bkp-bind-8099-$TS"

echo
echo "===== 1. AJUSTANDO BIND DO NGINX ATIVO ====="

python3 - "$CONF" "$ROUTER_BIND" "$PUBLIC_HOST" <<'PY'
from pathlib import Path
import sys
import re

path = Path(sys.argv[1])
router_bind = sys.argv[2]
public_host = sys.argv[3]

text = path.read_text()

# Troca qualquer listen da porta 8099 por bind explícito no IP privado.
text = re.sub(
    r'listen\s+(?:0\.0\.0\.0:|127\.0\.0\.1:|10\.\d+\.\d+\.\d+:)?8099\s*;',
    f'listen {router_bind};',
    text
)

# Se ainda existir "listen 8099;", troca também.
text = text.replace("listen 8099;", f"listen {router_bind};")

# Remove Port Guard antigo para recriar limpo.
text = re.sub(
    r'\n?\s*# BEGIN CloudIF Port Guard.*?# END CloudIF Port Guard\n?',
    '\n',
    text,
    flags=re.S
)

server_idx = text.find("server {")
if server_idx < 0:
    raise SystemExit("ERRO: não encontrei bloco server {")

insert_after = text.find("\n", server_idx)

guard = f'''
    # BEGIN CloudIF Port Guard
    absolute_redirect off;
    port_in_redirect off;
    server_name_in_redirect off;

    # Se alguém chegar com porta no Host, volta para a URL pública sem porta.
    if ($http_host ~* ":[0-9]+$") {{
        return 301 https://{public_host}$request_uri;
    }}

    proxy_headers_hash_max_size 2048;
    proxy_headers_hash_bucket_size 128;
    # END CloudIF Port Guard
'''

text = text[:insert_after+1] + guard + text[insert_after+1:]

# Reforça headers públicos.
text = text.replace("proxy_set_header Host $host;", f"proxy_set_header Host {public_host};")
text = text.replace("proxy_set_header Host $http_host;", f"proxy_set_header Host {public_host};")
text = text.replace("proxy_set_header X-Forwarded-Host $host;", f"proxy_set_header X-Forwarded-Host {public_host};")
text = text.replace("proxy_set_header X-Forwarded-Host $http_host;", f"proxy_set_header X-Forwarded-Host {public_host};")
text = text.replace("proxy_set_header X-Forwarded-Proto $scheme;", "proxy_set_header X-Forwarded-Proto https;")
text = text.replace("proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;", "proxy_set_header X-Forwarded-Proto https;")

path.write_text(text)
PY

echo
echo "===== 2. PATCH NO RENDER PARA NÃO VOLTAR 0.0.0.0:8099 ====="

if [ -f "$RENDER" ]; then
  cp -a "$RENDER" "$RENDER.bkp-bind-8099-$TS"

  sed -i -E \
    "s/listen[[:space:]]+(0\.0\.0\.0:|127\.0\.0\.1:|10\.[0-9]+\.[0-9]+\.[0-9]+:)?8099;/listen ${ROUTER_BIND};/g" \
    "$RENDER"

  sed -i \
    "s/listen 8099;/listen ${ROUTER_BIND};/g" \
    "$RENDER"

  if ! grep -q "cloudif-harden-router-8099.sh --no-firewall" "$RENDER"; then
    cat >> "$RENDER" <<'PATCH_RENDER'

# CloudIF hardening pós-render: garante que 8099 nunca volte para 0.0.0.0.
if [ -x /usr/local/sbin/cloudif-harden-router-8099.sh ]; then
  /usr/local/sbin/cloudif-harden-router-8099.sh --no-firewall >/dev/null 2>&1 || true
fi
PATCH_RENDER
  fi

  chmod +x "$RENDER"
else
  echo "AVISO: render script não encontrado: $RENDER"
fi

echo
echo "===== 3. TESTANDO E RECARREGANDO NGINX ====="

docker exec cloudif-tenant-router nginx -t
docker exec cloudif-tenant-router nginx -s reload || docker restart cloudif-tenant-router

sleep 3

echo
echo "===== 4. FIREWALL IDÊMPOTENTE PARA 8099 ====="

if [ "${1:-}" != "--no-firewall" ]; then
  iptables-save > "/root/iptables.before-cloudif-8099-$TS.save"

  # Remove regras antigas só da porta 8099 na INPUT para evitar duplicação/confusão.
  while iptables -S INPUT | grep -q -- '--dport 8099'; do
    RULE="$(iptables -S INPUT | grep -- '--dport 8099' | head -1 | sed 's/^-A /-D /')"
    iptables $RULE || break
  done

  iptables -I INPUT 1 -p tcp -s "$NPM_IP" --dport "$ROUTER_PORT" -j ACCEPT
  iptables -I INPUT 2 -p tcp -s 127.0.0.1/32 --dport "$ROUTER_PORT" -j ACCEPT
  iptables -I INPUT 3 -p tcp -i lo --dport "$ROUTER_PORT" -j ACCEPT
  iptables -I INPUT 4 -p tcp --dport "$ROUTER_PORT" -j DROP
fi

echo
echo "===== 5. RESULTADO DOS LISTENERS ====="
ss -ltnp "( sport = :89 or sport = :8099 or sport = :8101 )" || true

echo
echo "===== 6. REGRAS FIREWALL ====="
iptables -nvL INPUT --line-numbers | sed -n '1,40p'

echo
echo "===== 7. TESTES LOCAIS ====="

echo
echo "--- Router via IP privado correto ---"
curl -i --max-time 10 \
  -H "Host: ${PUBLIC_HOST}" \
  "http://${ROUTER_IP}:${ROUTER_PORT}/supabase/${TENANT}/" \
  2>/dev/null | sed -n '1,20p' || true

echo
echo "--- Router com Host contendo porta ---"
curl -i --max-time 10 \
  -H "Host: ${PUBLIC_HOST}:8099" \
  "http://${ROUTER_IP}:${ROUTER_PORT}/supabase/${TENANT}/" \
  2>/dev/null | sed -n '1,20p' || true

echo
echo "--- Público HTTPS ---"
curl -k -I --max-time 10 \
  "https://${PUBLIC_HOST}/supabase/${TENANT}/" \
  2>/dev/null | sed -n '1,40p' || true

echo
echo "============================================================"
echo " OK: router ajustado para ${ROUTER_BIND}"
echo "============================================================"
