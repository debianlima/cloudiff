#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:?ação obrigatória: check|sync|integrate}"
PROJECT="${2:?slug do projeto obrigatório}"
TENANT="${3:-}"
ACTOR="${4:-unknown}"

FORJA_ENV="/etc/cloudif/forja-agent-client.env"
KOMODO_ENV="/etc/cloudif/komodo-agent-client.env"
PORTAL_DB="${CLOUDIF_PORTAL_DB:-/var/lib/cloudif/portal/cloudif-portal.db}"

echo "============================================================"
echo " CloudIF Project Integrate v22b"
echo "============================================================"
echo "ACTION=$ACTION"
echo "PROJECT=$PROJECT"
echo "TENANT=$TENANT"
echo "ACTOR=$ACTOR"
echo "DATE=$(date -Is)"
echo

get_project_field() {
  local field="$1"
  python3 - "$PORTAL_DB" "$PROJECT" "$field" <<'PY'
import sqlite3, sys
db, slug, field = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    con = sqlite3.connect(db, timeout=10)
    con.row_factory = sqlite3.Row
    row = con.execute("select * from projects where slug=?", (slug,)).fetchone()
    con.close()
    if row and field in row.keys():
        print(row[field] or "")
except Exception:
    print("")
PY
}

PROJECT_NAME="$(get_project_field name)"
REPO_URL="$(get_project_field repo_url)"

[ -n "$PROJECT_NAME" ] || PROJECT_NAME="$PROJECT"

PAYLOAD_FILE="$(mktemp /tmp/cloudif-project-payload.XXXXXX.json)"
trap 'rm -f "$PAYLOAD_FILE"' EXIT

python3 - "$PROJECT" "$PROJECT_NAME" "$TENANT" "$ACTOR" "$REPO_URL" "$ACTION" > "$PAYLOAD_FILE" <<'PY'
import json, sys
project, name, tenant, actor, repo_url, action = sys.argv[1:]
print(json.dumps({
  "project": project,
  "name": name,
  "tenant": tenant,
  "actor": actor,
  "repo_url": repo_url,
  "action": action,
  "source": "cloudif-portal"
}, ensure_ascii=False))
PY

echo "===== Payload ====="
cat "$PAYLOAD_FILE"
echo

call_get() {
  local url="$1"
  local token="${2:-}"
  if [ -n "$token" ]; then
    curl -sS --connect-timeout 5 --max-time 25 -H "Authorization: Bearer $token" "$url"
  else
    curl -sS --connect-timeout 5 --max-time 25 "$url"
  fi
}

call_post() {
  local url="$1"
  local token="${2:-}"
  local outfile="$3"

  if [ -n "$token" ]; then
    curl -sS --connect-timeout 5 --max-time 90 \
      -o "$outfile" -w '%{http_code}' \
      -X POST \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $token" \
      --data-binary "@$PAYLOAD_FILE" \
      "$url" || true
  else
    curl -sS --connect-timeout 5 --max-time 90 \
      -o "$outfile" -w '%{http_code}' \
      -X POST \
      -H "Content-Type: application/json" \
      --data-binary "@$PAYLOAD_FILE" \
      "$url" || true
  fi
}

if [ ! -f "$FORJA_ENV" ]; then
  echo "ERRO: não existe $FORJA_ENV"
  exit 1
fi

set -a
. "$FORJA_ENV"
set +a

FORJA_AGENT_URL="${FORJA_AGENT_URL:-}"
FORJA_AGENT_TOKEN="${FORJA_AGENT_TOKEN:-}"

if [ -z "$FORJA_AGENT_URL" ]; then
  echo "ERRO: FORJA_AGENT_URL vazio em $FORJA_ENV"
  exit 1
fi

echo "===== 1. Checando Forja Agent / Forgejo ====="
call_get "$FORJA_AGENT_URL/health" "$FORJA_AGENT_TOKEN"
echo
call_get "$FORJA_AGENT_URL/status" "$FORJA_AGENT_TOKEN" || true
echo

if [ "$ACTION" = "check" ]; then
  echo
  echo "===== 2. Checando Komodo Agent ====="
  if [ -f "$KOMODO_ENV" ]; then
    set -a
    . "$KOMODO_ENV"
    set +a

    KOMODO_AGENT_URL="${KOMODO_AGENT_URL:-}"
    KOMODO_AGENT_TOKEN="${KOMODO_AGENT_TOKEN:-}"

    if [ -n "$KOMODO_AGENT_URL" ]; then
      call_get "$KOMODO_AGENT_URL/health" "$KOMODO_AGENT_TOKEN" || true
      echo
      call_get "$KOMODO_AGENT_URL/status" "$KOMODO_AGENT_TOKEN" || true
      echo
    else
      echo "KOMODO_AGENT_URL vazio."
    fi
  else
    echo "Arquivo $KOMODO_ENV não existe."
  fi

  echo
  echo "OK: check concluído."
  exit 0
fi

echo
echo "===== 2. Sincronizando Forgejo via Forja Agent /project/ensure ====="
FORGEJO_CODE="$(call_post "$FORJA_AGENT_URL/project/ensure" "$FORJA_AGENT_TOKEN" /tmp/cloudif-v22b-forgejo-response.json)"
echo "HTTP=$FORGEJO_CODE"
cat /tmp/cloudif-v22b-forgejo-response.json 2>/dev/null || true
echo

case "$FORGEJO_CODE" in
  200|201|202)
    echo "OK: Forgejo sincronizado."
    ;;
  *)
    echo "ERRO: Forgejo/Forja Agent falhou em /project/ensure."
    exit 2
    ;;
esac

if [ "$ACTION" = "sync" ]; then
  echo
  echo "OK: sync concluiu apenas Forgejo."
  exit 0
fi

echo
echo "===== 3. Integrando Komodo ====="

if [ ! -f "$KOMODO_ENV" ]; then
  echo "ERRO: não existe $KOMODO_ENV"
  exit 3
fi

set -a
. "$KOMODO_ENV"
set +a

KOMODO_AGENT_URL="${KOMODO_AGENT_URL:-}"
KOMODO_AGENT_TOKEN="${KOMODO_AGENT_TOKEN:-}"

if [ -z "$KOMODO_AGENT_URL" ]; then
  echo "ERRO: KOMODO_AGENT_URL vazio em $KOMODO_ENV"
  exit 3
fi

echo "Komodo Agent: $KOMODO_AGENT_URL"

KOMODO_CODE="$(call_post "$KOMODO_AGENT_URL/komodo/project/ensure" "$KOMODO_AGENT_TOKEN" /tmp/cloudif-v22b-komodo-response.json)"
echo "HTTP=$KOMODO_CODE"
cat /tmp/cloudif-v22b-komodo-response.json 2>/dev/null || true
echo

case "$KOMODO_CODE" in
  200|201|202)
    echo "OK: Komodo integrado."
    ;;
  *)
    echo "ERRO: Komodo Agent não confirmou integração."
    echo "Provável causa: /etc/cloudif/komodo-agent.env na forja ainda está sem KOMODO_API_TOKEN ou KOMODO_API_KEY."
    exit 4
    ;;
esac

echo
echo "OK: integração Forgejo + Komodo finalizada."
