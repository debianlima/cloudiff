#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"
KONG_FILE="$TDIR/volumes/api/kong.yml"

cd "$TDIR"

getenv() {
  grep -E "^$1=" "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true
}

ANON_KEY="$(getenv ANON_KEY)"
SERVICE_ROLE_KEY="$(getenv SERVICE_ROLE_KEY)"
DASHBOARD_USERNAME="$(getenv DASHBOARD_USERNAME)"
DASHBOARD_PASSWORD="$(getenv DASHBOARD_PASSWORD)"

[ -n "$ANON_KEY" ] || { echo "ERRO: ANON_KEY vazio em $ENV"; exit 1; }
[ -n "$SERVICE_ROLE_KEY" ] || { echo "ERRO: SERVICE_ROLE_KEY vazio em $ENV"; exit 1; }
[ -n "$DASHBOARD_USERNAME" ] || { echo "ERRO: DASHBOARD_USERNAME vazio em $ENV"; exit 1; }
[ -n "$DASHBOARD_PASSWORD" ] || { echo "ERRO: DASHBOARD_PASSWORD vazio em $ENV"; exit 1; }

mkdir -p "$(dirname "$KONG_FILE")"
cp -a "$KONG_FILE" "$KONG_FILE.bkp-v134-$(date +%F-%H%M%S)" 2>/dev/null || true

cat > "$KONG_FILE" <<EOF
_format_version: "2.1"
_transform: true

consumers:
  - username: anon
    keyauth_credentials:
      - key: ${ANON_KEY}

  - username: service_role
    keyauth_credentials:
      - key: ${SERVICE_ROLE_KEY}

  - username: dashboard
    basicauth_credentials:
      - username: ${DASHBOARD_USERNAME}
        password: ${DASHBOARD_PASSWORD}

acls:
  - consumer: anon
    group: anon

  - consumer: service_role
    group: admin

plugins:
  - name: cors

services:
  - name: auth-v1-open
    url: http://auth:9999/verify
    routes:
      - name: auth-v1-open
        strip_path: true
        paths:
          - /auth/v1/verify
    plugins:
      - name: cors

  - name: auth-v1-open-callback
    url: http://auth:9999/callback
    routes:
      - name: auth-v1-open-callback
        strip_path: true
        paths:
          - /auth/v1/callback
    plugins:
      - name: cors

  - name: auth-v1-open-authorize
    url: http://auth:9999/authorize
    routes:
      - name: auth-v1-open-authorize
        strip_path: true
        paths:
          - /auth/v1/authorize
    plugins:
      - name: cors

  - name: auth-v1
    url: http://auth:9999/
    routes:
      - name: auth-v1-all
        strip_path: true
        paths:
          - /auth/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: false
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon

  - name: rest-v1
    url: http://rest:3000/
    routes:
      - name: rest-v1-all
        strip_path: true
        paths:
          - /rest/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: true
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon

  - name: realtime-v1
    url: http://realtime:4000/socket/
    routes:
      - name: realtime-v1-all
        strip_path: true
        paths:
          - /realtime/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: false
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon

  - name: storage-v1
    url: http://storage:5000/
    routes:
      - name: storage-v1-all
        strip_path: true
        paths:
          - /storage/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: true
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon

  - name: functions-v1
    url: http://functions:9000/
    routes:
      - name: functions-v1-all
        strip_path: true
        paths:
          - /functions/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: false
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon

  - name: meta
    url: http://meta:8080/
    routes:
      - name: meta-all
        strip_path: true
        paths:
          - /pg/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: true
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin

  - name: studio
    url: http://studio:3000/
    routes:
      - name: studio-all
        strip_path: false
        paths:
          - /
    plugins:
      - name: basic-auth
        config:
          hide_credentials: true
EOF

echo "kong.yml v134 escrito para tenant=$TENANT"
