#!/usr/bin/env bash
set -Eeuo pipefail

TENANT="${1:?tenant}"
PROJECT="${2:?project}"
WEBHOOK_ENDPOINT="${3:-}"

BASE="/srv/cloudif"
TDIR="$BASE/tenants/$TENANT"
ENV="$TDIR/.env"

echo "============================================================"
echo " CLOUDIF - SUPABASE PROJECT HOOKS"
echo "============================================================"
date -Is
echo "TENANT=$TENANT"
echo "PROJECT=$PROJECT"
echo "WEBHOOK_ENDPOINT=$WEBHOOK_ENDPOINT"

test -d "$TDIR" || { echo "ERRO: tenant não existe: $TDIR"; exit 1; }
test -f "$ENV" || { echo "ERRO: .env não existe: $ENV"; exit 1; }

POSTGRES_PORT="$(grep -E '^POSTGRES_PORT=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"
POSTGRES_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' "$ENV" | tail -1 | cut -d= -f2- | tr -d '"' || true)"

[ -n "$POSTGRES_PORT" ] || { echo "ERRO: POSTGRES_PORT vazio"; exit 1; }
[ -n "$POSTGRES_PASSWORD" ] || { echo "ERRO: POSTGRES_PASSWORD vazio"; exit 1; }

cd "$TDIR"

cat > /tmp/cloudif-project-hooks.sql <<SQL
CREATE SCHEMA IF NOT EXISTS cloudif;

CREATE TABLE IF NOT EXISTS cloudif.project_links (
  project text NOT NULL,
  tenant text NOT NULL,
  repo_url text DEFAULT '',
  stack_name text DEFAULT '',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  PRIMARY KEY(project, tenant)
);

CREATE TABLE IF NOT EXISTS cloudif.project_webhooks (
  id bigserial PRIMARY KEY,
  project text NOT NULL,
  tenant text NOT NULL,
  table_schema text DEFAULT '',
  table_name text DEFAULT '',
  events text[] DEFAULT ARRAY['INSERT','UPDATE','DELETE'],
  endpoint text DEFAULT '',
  enabled boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloudif.webhook_events (
  id bigserial PRIMARY KEY,
  project text NOT NULL,
  tenant text NOT NULL,
  table_schema text NOT NULL,
  table_name text NOT NULL,
  event text NOT NULL,
  row_data jsonb,
  old_data jsonb,
  created_at timestamptz DEFAULT now(),
  delivered_at timestamptz,
  delivery_status text DEFAULT 'pending',
  delivery_error text DEFAULT ''
);

CREATE OR REPLACE FUNCTION cloudif.enqueue_webhook_event()
RETURNS trigger
LANGUAGE plpgsql
AS \$\$
DECLARE
  v_project text;
  v_tenant text;
BEGIN
  v_project := TG_ARGV[0];
  v_tenant := TG_ARGV[1];

  INSERT INTO cloudif.webhook_events (
    project, tenant, table_schema, table_name, event, row_data, old_data
  )
  VALUES (
    v_project,
    v_tenant,
    TG_TABLE_SCHEMA,
    TG_TABLE_NAME,
    TG_OP,
    CASE WHEN TG_OP IN ('INSERT','UPDATE') THEN to_jsonb(NEW) ELSE NULL END,
    CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN to_jsonb(OLD) ELSE NULL END
  );

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;

  RETURN NEW;
END;
\$\$;

CREATE OR REPLACE FUNCTION cloudif.ensure_table_webhook(
  p_project text,
  p_tenant text,
  p_table_schema text,
  p_table_name text
)
RETURNS void
LANGUAGE plpgsql
AS \$\$
DECLARE
  v_trigger_name text;
BEGIN
  v_trigger_name := 'cloudif_' || regexp_replace(p_project, '[^a-zA-Z0-9_]+', '_', 'g') || '_' || p_table_name || '_wh';

  EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', v_trigger_name, p_table_schema, p_table_name);

  EXECUTE format(
    'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION cloudif.enqueue_webhook_event(%L, %L)',
    v_trigger_name,
    p_table_schema,
    p_table_name,
    p_project,
    p_tenant
  );
END;
\$\$;

INSERT INTO cloudif.project_links(project, tenant, repo_url, stack_name, updated_at)
VALUES ('${PROJECT}', '${TENANT}', '', '', now())
ON CONFLICT(project, tenant) DO UPDATE SET updated_at=now();

INSERT INTO cloudif.project_webhooks(project, tenant, endpoint, enabled, updated_at)
VALUES ('${PROJECT}', '${TENANT}', '${WEBHOOK_ENDPOINT}', true, now())
ON CONFLICT DO NOTHING;
SQL

docker compose --env-file .env exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
  psql -h 127.0.0.1 -p "$POSTGRES_PORT" -U postgres -d postgres < /tmp/cloudif-project-hooks.sql

echo
echo "OK: estrutura cloudif criada/garantida no tenant=$TENANT project=$PROJECT"
echo
echo "Para ativar trigger em uma tabela específica:"
echo "SELECT cloudif.ensure_table_webhook('$PROJECT', '$TENANT', 'public', 'nome_da_tabela');"
