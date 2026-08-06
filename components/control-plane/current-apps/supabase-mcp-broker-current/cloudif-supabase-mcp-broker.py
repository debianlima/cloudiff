#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import decimal
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.parse
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg2
from psycopg2 import sql
import requests

HOST = os.environ.get('CLOUDIF_SUPABASE_MCP_BROKER_HOST', '127.0.0.1')
PORT = int(os.environ.get('CLOUDIF_SUPABASE_MCP_BROKER_PORT', '18218'))
TOKEN = os.environ.get('CLOUDIF_SUPABASE_MCP_BROKER_TOKEN', '')
CONTROL_DB = Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB', '/var/lib/cloudif/control-plane/control-plane.db'))
TENANT_ROOT = Path(os.environ.get('CLOUDIF_TENANT_ROOT', '/srv/cloudif/tenants'))
STATE_DB = Path(os.environ.get('CLOUDIF_SUPABASE_MCP_STATE_DB', '/var/lib/cloudif/supabase-mcp-broker/executions.db'))
MAX_BODY = 1_048_576
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
TENANT_RE = re.compile(r'^[a-z0-9][a-z0-9-]{2,126}$')
IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]{0,62}$')
ENV_RE = re.compile(r'^[A-Z_][A-Z0-9_]{0,127}$')
BUCKET_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')
APPROVAL_OPERATIONS = {'records.change', 'sql.change', 'rls.change', 'schema.change', 'secrets.read'}
READ_ACTIONS = {
    'tables.list', 'records.select', 'sql.query', 'auth.users.list', 'storage.buckets.list',
    'storage.objects.list', 'storage.object.read', 'secrets.list', 'rls.inspect', 'schema.inspect',
    'logs.read', 'admin.config.read',
}
SERVICE_ALLOWLIST = {'db', 'auth', 'rest', 'storage', 'realtime', 'kong', 'studio', 'functions', 'meta', 'supavisor'}
ROLE_RANK = {
    'none': 0, 'viewer': 10, 'service': 40, 'member': 50, 'developer': 60, 'editor': 65,
    'maintainer': 80, 'admin': 90, 'administrator': 90, 'owner': 100,
}
SECRET_TOKENS = (
    'PASSWORD', 'SECRET', 'TOKEN', 'PRIVATE', 'JWT', 'SERVICE_ROLE', 'ANON_KEY', 'PUBLISHABLE_KEY',
    'API_KEY', 'ACCESS_KEY', 'SMTP_PASS', 'VAULT', 'CRYPTO_KEY', 'KEY_BASE', 'SIGNING_KEY',
)
SAFE_ENV_KEYS = {
    'API_EXTERNAL_URL', 'SITE_URL', 'SUPABASE_PUBLIC_URL', 'POSTGRES_DB', 'POSTGRES_HOST',
    'POSTGRES_PORT', 'POSTGRES_INTERNAL_PORT', 'KONG_HTTP_PORT', 'KONG_HTTPS_PORT', 'STUDIO_PORT',
    'REGION', 'STUDIO_DEFAULT_ORGANIZATION', 'STUDIO_DEFAULT_PROJECT', 'POOLER_TENANT_ID',
    'POOLER_PROXY_PORT_SESSION', 'POOLER_PROXY_PORT_TRANSACTION', 'PGRST_DB_SCHEMAS',
    'PGRST_DB_EXTRA_SEARCH_PATH', 'DISABLE_SIGNUP', 'ENABLE_EMAIL_SIGNUP', 'ENABLE_PHONE_SIGNUP',
    'ENABLE_ANONYMOUS_USERS', 'ENABLE_EMAIL_AUTOCONFIRM', 'ENABLE_PHONE_AUTOCONFIRM',
}
SENSITIVE_SCHEMA_RE = re.compile(
    r'(?i)(?:^|[^A-Za-z0-9_$])(?:auth|storage|vault|extensions|pg_catalog|information_schema|pg_toast|'
    r'realtime|_realtime|supabase_migrations|supabase_functions|pgsodium|graphql)\s*[.]'
)
FORBIDDEN_SQL = re.compile(
    r'\b(?:alter\s+system|create\s+(?:role|user|database|tablespace|extension|server|foreign\s+data\s+wrapper)|'
    r'alter\s+(?:role|user|database|tablespace)|drop\s+(?:role|user|database|tablespace)|'
    r'grant\b|revoke\b|copy\b|do\b|execute\b|'
    r'pg_(?:read_(?:binary_)?file|write_file|stat_file|ls_(?:dir|waldir|logdir|tmpdir|archive_statusdir)|'
    r'terminate_backend|cancel_backend|reload_conf|rotate_logfile|create_restore_point|switch_wal|'
    r'wal_replay_(?:pause|resume)|promote|log_backend_memory_contexts)|'
    r'lo_import|lo_export|dblink|postgres_fdw|file_fdw|security\s+definer)\b',
    re.IGNORECASE,
)
UNSAFE_FUNCTION_LANGUAGE = re.compile(r'\blanguage\s+(?:c|internal|plpython\w*|plperl\w*|pltcl\w*|pljava|plv8)\b', re.IGNORECASE)
RLS_ALLOWED = re.compile(
    r'^(?:create\s+policy\b|alter\s+policy\b|drop\s+policy\b|'
    r'alter\s+table\b[\s\S]*?\b(?:enable|disable|force|no\s+force)\s+row\s+level\s+security\b)',
    re.IGNORECASE,
)
SCHEMA_ALLOWED = re.compile(
    r'^(?:(?:create\s+(?:or\s+replace\s+)?|alter\s+|drop\s+)'
    r'(?:table|function|trigger|index|view|materialized\s+view|type|sequence)\b)',
    re.IGNORECASE,
)


def db_conn() -> sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('pragma busy_timeout=20000')
    return conn


def init_state() -> None:
    conn = db_conn()
    conn.execute('pragma journal_mode=delete')
    conn.executescript('''
    create table if not exists executions(
      execution_id text primary key,
      project_slug text not null,
      operation text not null,
      digest text not null,
      status text not null,
      result_json text not null default '{}',
      created_at integer not null,
      finished_at integer
    );
    create index if not exists idx_supabase_mcp_exec_project on executions(project_slug,created_at desc);
    ''')
    conn.commit()
    conn.close()
    os.chmod(STATE_DB, 0o600)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, value = line.split('=', 1)
        key = key.strip()
        if not ENV_RE.fullmatch(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def is_secret_name(name: str) -> bool:
    upper = str(name).upper()
    if upper in SAFE_ENV_KEYS:
        return False
    return any(token in upper for token in SECRET_TOKENS) or upper.endswith('_KEY')


def mask_secret(value: str) -> str:
    value = str(value)
    if not value:
        return '(vazio)'
    if len(value) <= 8:
        return '*' * len(value)
    return value[:3] + '*' * min(24, len(value) - 6) + value[-3:]


def project_context(slug: str, actor_user: str, actor_groups: list[str] | tuple[str, ...]) -> dict:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError('invalid_project_slug')
    conn = sqlite3.connect(f'file:{CONTROL_DB}?mode=ro', uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    project = conn.execute('select * from projects where slug=?', (slug,)).fetchone()
    if not project:
        conn.close()
        raise LookupError('project_not_found')
    rows = conn.execute('select subject_type,subject,role from project_acl where project_id=?', (project['project_id'],)).fetchall()
    conn.close()
    tenant = str(project['tenant'] or '').strip()
    if not TENANT_RE.fullmatch(tenant):
        raise ValueError('tenant_not_available')
    owner = str(project['owner'] or '').strip().casefold()
    user = str(actor_user or '').strip().casefold()
    groups = {str(x).strip().casefold() for x in (actor_groups or []) if str(x).strip()}
    role = 'service' if not user else 'none'
    if user and user == owner:
        role = 'owner'
    for row in rows:
        subject_type = str(row['subject_type'] or '').strip().casefold()
        subject = str(row['subject'] or '').strip().casefold()
        matches = (subject_type == 'user' and subject == user) or (subject_type == 'group' and subject in groups)
        if matches:
            candidate = str(row['role'] or 'viewer').strip().casefold()
            if ROLE_RANK.get(candidate, 0) > ROLE_RANK.get(role, 0):
                role = candidate
    if ROLE_RANK.get(role, 0) <= 0:
        raise PermissionError('project_access_denied')
    tenant_dir = TENANT_ROOT / tenant
    env_path = tenant_dir / '.env'
    if not tenant_dir.is_dir() or not env_path.is_file():
        raise LookupError('tenant_runtime_not_found')
    return {
        'project_id': project['project_id'], 'slug': slug, 'tenant': tenant,
        'owner': str(project['owner'] or ''), 'status': str(project['status'] or ''),
        'role': role, 'role_rank': ROLE_RANK.get(role, 0), 'actor_user': str(actor_user or ''),
        'actor_groups': sorted(groups), 'tenant_dir': tenant_dir, 'env': read_env(env_path),
    }


def require_role(ctx: dict, minimum: int, error: str = 'project_role_denied') -> None:
    if int(ctx.get('role_rank') or 0) < minimum:
        raise PermissionError(error)


def docker_inspect(name: str) -> dict:
    proc = subprocess.run(['docker', 'inspect', name], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    if proc.returncode:
        raise RuntimeError('tenant_service_unavailable')
    rows = json.loads(proc.stdout)
    if not rows:
        raise RuntimeError('tenant_service_unavailable')
    return rows[0]


def db_target(ctx: dict) -> tuple[str, int, str, str, str]:
    container = f"cloudif_{ctx['tenant']}-db-1"
    info = docker_inspect(container)
    networks = (info.get('NetworkSettings') or {}).get('Networks') or {}
    host = next((str(v.get('IPAddress') or '') for v in networks.values() if v.get('IPAddress')), '')
    if not host:
        raise RuntimeError('database_address_unavailable')
    env = ctx['env']
    password = env.get('POSTGRES_PASSWORD', '')
    database = env.get('POSTGRES_DB', 'postgres') or 'postgres'
    try:
        port = int(env.get('POSTGRES_INTERNAL_PORT') or env.get('POSTGRES_PORT') or 5432)
    except (TypeError, ValueError):
        raise RuntimeError('database_port_unavailable')
    if not (1 <= port <= 65535):
        raise RuntimeError('database_port_unavailable')
    if not password:
        raise RuntimeError('database_credentials_unavailable')
    return host, port, database, 'postgres', password


def postgres(ctx: dict, readonly: bool, timeout_ms: int = 5000, db_role: str = 'service_role'):
    host, port, database, user, password = db_target(ctx)
    if db_role not in {'service_role','postgres'}:
        raise ValueError('invalid_database_role')
    conn = psycopg2.connect(
        host=host, port=port, dbname=database, user=user, password=password,
        connect_timeout=5, application_name='cloudif_supabase_mcp_broker',
        options=f'-c statement_timeout={max(500, min(int(timeout_ms), 30000))}',
    )
    conn.set_session(readonly=readonly, autocommit=False)
    if db_role != 'postgres':
        with conn.cursor() as cur:
            cur.execute(sql.SQL('set local role {}').format(sql.Identifier(db_role)))
            cur.execute('set local row_security=on')
    return conn


def jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return {'encoding': 'base64', 'data': base64.b64encode(value).decode()}
    if isinstance(value, (list, tuple)):
        return [jsonable(x) for x in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    return str(value)


def query_rows(ctx: dict, statement, params=None, max_rows: int = 200, timeout_ms: int = 5000) -> dict:
    max_rows = max(1, min(int(max_rows), 500))
    with postgres(ctx, True, timeout_ms) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params or ())
            columns = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchmany(max_rows + 1) if cur.description else []
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return {'columns': columns, 'rows': [[jsonable(v) for v in row] for row in rows], 'row_count': len(rows), 'truncated': truncated}


def ident(name: str) -> str:
    name = str(name or '').strip()
    if not IDENT_RE.fullmatch(name):
        raise ValueError('invalid_identifier')
    return name


def compile_filters(filters: dict | None) -> tuple[list, list]:
    filters = filters or {}
    if not isinstance(filters, dict) or len(filters) > 32:
        raise ValueError('invalid_filters')
    clauses = []
    params = []
    operators = {'eq': '=', 'neq': '<>', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=', 'like': 'LIKE', 'ilike': 'ILIKE'}
    for key, raw in filters.items():
        column = ident(key)
        if raw is None:
            clauses.append(sql.SQL('{} IS NULL').format(sql.Identifier(column)))
            continue
        if isinstance(raw, list):
            if not raw or len(raw) > 100:
                raise ValueError('invalid_filter_list')
            clauses.append(sql.SQL('{} IN ({})').format(sql.Identifier(column), sql.SQL(',').join(sql.Placeholder() for _ in raw)))
            params.extend(raw)
            continue
        if isinstance(raw, dict):
            if set(raw) != {'op', 'value'} or str(raw['op']) not in operators:
                raise ValueError('invalid_filter_operator')
            op = operators[str(raw['op'])]
            clauses.append(sql.SQL('{} {} %s').format(sql.Identifier(column), sql.SQL(op)))
            params.append(raw['value'])
            continue
        clauses.append(sql.SQL('{} = %s').format(sql.Identifier(column)))
        params.append(raw)
    return clauses, params


def tables_list(ctx: dict, payload: dict) -> dict:
    include_system = bool(payload.get('include_system'))
    schemas = payload.get('schemas') or []
    if not isinstance(schemas, list) or len(schemas) > 20:
        raise ValueError('invalid_schemas')
    schemas = [ident(x) for x in schemas]
    where = ["table_type in ('BASE TABLE','VIEW')"]
    params = []
    if not include_system:
        where.append("table_schema not in ('pg_catalog','information_schema','pg_toast')")
    if schemas:
        where.append('table_schema = any(%s)')
        params.append(schemas)
    statement = f'''select table_schema,table_name,table_type
      from information_schema.tables where {' and '.join(where)}
      order by table_schema,table_name limit 1000'''
    result = query_rows(ctx, statement, params, 1000, 5000)
    return {'ok': True, 'project_slug': ctx['slug'], 'tables': [dict(zip(result['columns'], row)) for row in result['rows']], 'count': result['row_count']}


def records_select(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    schema = ident(payload.get('schema') or 'public')
    if schema.casefold() in {'auth','storage','vault','extensions','pg_catalog','information_schema','pg_toast','realtime','_realtime','supabase_migrations','supabase_functions','pgsodium','graphql'}: raise PermissionError('sensitive_schema_access_denied')
    table = ident(payload.get('table'))
    columns = payload.get('columns') or ['*']
    if not isinstance(columns, list) or not columns or len(columns) > 64:
        raise ValueError('invalid_columns')
    if columns == ['*']:
        selected = sql.SQL('*')
    else:
        selected = sql.SQL(',').join(sql.Identifier(ident(x)) for x in columns)
    clauses, params = compile_filters(payload.get('filters'))
    statement = sql.SQL('select {} from {}.{}').format(selected, sql.Identifier(schema), sql.Identifier(table))
    if clauses:
        statement += sql.SQL(' where ') + sql.SQL(' and ').join(clauses)
    order_by = payload.get('order_by') or []
    if not isinstance(order_by, list) or len(order_by) > 8:
        raise ValueError('invalid_order_by')
    if order_by:
        orders = []
        for item in order_by:
            item = str(item)
            direction = 'DESC' if item.startswith('-') else 'ASC'
            column = ident(item[1:] if item.startswith('-') else item)
            orders.append(sql.SQL('{} {}').format(sql.Identifier(column), sql.SQL(direction)))
        statement += sql.SQL(' order by ') + sql.SQL(',').join(orders)
    limit = max(1, min(int(payload.get('limit') or 100), 500))
    offset = max(0, min(int(payload.get('offset') or 0), 100000))
    statement += sql.SQL(' limit %s offset %s')
    params.extend([limit, offset])
    result = query_rows(ctx, statement, params, limit, int(payload.get('timeout_ms') or 5000))
    return {'ok': True, 'project_slug': ctx['slug'], 'schema': schema, 'table': table, **result}


def scan_sql(text: str) -> list[tuple[str, str]]:
    text = str(text or '')
    if not text.strip() or len(text.encode()) > 65536 or '\x00' in text:
        raise ValueError('invalid_sql')
    statements: list[tuple[str, str]] = []
    raw: list[str] = []
    skeleton: list[str] = []
    i = 0
    single = double = line_comment = False
    block_depth = 0
    dollar = ''
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            raw.append(ch); skeleton.append(' ')
            if ch == '\n':
                line_comment = False
            i += 1; continue
        if block_depth:
            raw.append(ch); skeleton.append(' ')
            if ch == '/' and nxt == '*':
                raw.append(nxt); skeleton.append(' '); block_depth += 1; i += 2; continue
            if ch == '*' and nxt == '/':
                raw.append(nxt); skeleton.append(' '); block_depth -= 1; i += 2; continue
            i += 1; continue
        if dollar:
            if text.startswith(dollar, i):
                raw.extend(dollar); skeleton.extend(' ' * len(dollar)); i += len(dollar); dollar = ''
            else:
                raw.append(ch); skeleton.append(' '); i += 1
            continue
        if single:
            raw.append(ch); skeleton.append(' ')
            if ch == "'":
                if nxt == "'":
                    raw.append(nxt); skeleton.append(' '); i += 2; continue
                single = False
            i += 1; continue
        if double:
            raw.append(ch)
            if ch == '"':
                if nxt == '"':
                    raw.append(nxt); skeleton.append('"'); i += 2; continue
                double = False; skeleton.append(' ')
            else:
                skeleton.append(ch)
            i += 1; continue
        if ch == '-' and nxt == '-':
            raw.extend((ch, nxt)); skeleton.extend((' ', ' ')); line_comment = True; i += 2; continue
        if ch == '/' and nxt == '*':
            raw.extend((ch, nxt)); skeleton.extend((' ', ' ')); block_depth = 1; i += 2; continue
        if ch == "'":
            raw.append(ch); skeleton.append(' '); single = True; i += 1; continue
        if ch == '"':
            raw.append(ch); skeleton.append(' '); double = True; i += 1; continue
        if ch == '$':
            match = re.match(r'\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$', text[i:])
            if match:
                dollar = match.group(0); raw.extend(dollar); skeleton.extend(' ' * len(dollar)); i += len(dollar); continue
        if ch == ';':
            current = ''.join(raw).strip(); code = re.sub(r'\s+', ' ', ''.join(skeleton)).strip()
            if current:
                statements.append((current, code))
            raw = []; skeleton = []; i += 1; continue
        raw.append(ch); skeleton.append(ch); i += 1
    if single or double or dollar or block_depth:
        raise ValueError('unterminated_sql_literal')
    current = ''.join(raw).strip(); code = re.sub(r'\s+', ' ', ''.join(skeleton)).strip()
    if current:
        statements.append((current, code))
    if not statements or len(statements) > 10:
        raise ValueError('invalid_sql_statement_count')
    return statements


def validate_sql(text: str, mode: str) -> list[str]:
    statements = scan_sql(text)
    if mode == 'read' and len(statements) != 1:
        raise ValueError('read_sql_single_statement_required')
    normalized = []
    for raw, code in statements:
        low = code.casefold().strip()
        dequoted = code.replace('"', '')
        raw_dequoted = raw.replace('"', '')
        function_definition = bool(re.match(r'^\s*(?:create\s+(?:or\s+replace\s+)?|alter\s+)function\b', dequoted, re.IGNORECASE))
        if FORBIDDEN_SQL.search(dequoted) or (function_definition and FORBIDDEN_SQL.search(raw_dequoted)):
            raise PermissionError('forbidden_sql_capability')
        if SENSITIVE_SCHEMA_RE.search(dequoted) or (function_definition and SENSITIVE_SCHEMA_RE.search(raw_dequoted)):
            raise PermissionError('sensitive_schema_access_denied')
        if function_definition and UNSAFE_FUNCTION_LANGUAGE.search(raw_dequoted):
            raise PermissionError('unsafe_function_language')
        if re.match(r'^(?:begin|commit|rollback|savepoint|release|prepare\s+transaction|vacuum|cluster|reindex\s+system|set|reset)\b', low):
            raise PermissionError('transaction_control_not_allowed')
        if mode == 'read' and not re.match(r'^(?:select|with|show|explain|values)\b', low):
            raise PermissionError('read_only_sql_required')
        if mode == 'rls' and not RLS_ALLOWED.match(low):
            raise PermissionError('rls_statement_required')
        if mode == 'schema' and not SCHEMA_ALLOWED.match(low):
            raise PermissionError('schema_statement_required')
        normalized.append(raw)
    return normalized


def sql_query(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    statements = validate_sql(payload.get('sql'), 'read')
    result = query_rows(ctx, statements[0], (), int(payload.get('max_rows') or 200), int(payload.get('timeout_ms') or 5000))
    return {'ok': True, 'project_slug': ctx['slug'], 'read_only': True, **result}


def kong(ctx: dict) -> tuple[str, dict[str, str]]:
    env = ctx['env']
    port = int(env.get('KONG_HTTP_PORT') or 0)
    key = env.get('SERVICE_ROLE_KEY') or env.get('SUPABASE_SERVICE_KEY') or env.get('SUPABASE_SECRET_KEY')
    if not (1 <= port <= 65535) or not key:
        raise RuntimeError('supabase_admin_api_unavailable')
    return f'http://127.0.0.1:{port}', {'apikey': key, 'Authorization': 'Bearer ' + key}


def auth_users_list(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    base, headers = kong(ctx)
    page = max(1, min(int(payload.get('page') or 1), 100000))
    per_page = max(1, min(int(payload.get('per_page') or 50), 100))
    response = requests.get(base + '/auth/v1/admin/users', headers=headers, params={'page': page, 'per_page': per_page}, timeout=(3, 20))
    if response.status_code != 200:
        raise RuntimeError('supabase_auth_query_failed')
    body = response.json()
    users = body.get('users') if isinstance(body, dict) else body
    users = users if isinstance(users, list) else []
    email = str(payload.get('email') or '').strip().casefold()
    safe = []
    for user in users:
        if email and email not in str(user.get('email') or '').casefold():
            continue
        safe.append({k: jsonable(user.get(k)) for k in ('id', 'email', 'phone', 'role', 'created_at', 'updated_at', 'last_sign_in_at', 'confirmed_at', 'banned_until', 'is_anonymous')})
    return {'ok': True, 'project_slug': ctx['slug'], 'users': safe, 'count': len(safe), 'page': page, 'per_page': per_page}


def storage_buckets_list(ctx: dict) -> dict:
    require_role(ctx, 50)
    base, headers = kong(ctx)
    response = requests.get(base + '/storage/v1/bucket', headers=headers, timeout=(3, 20))
    if response.status_code != 200:
        raise RuntimeError('storage_bucket_query_failed')
    rows = response.json()
    rows = rows if isinstance(rows, list) else []
    safe = [{k: jsonable(item.get(k)) for k in ('id', 'name', 'public', 'file_size_limit', 'allowed_mime_types', 'created_at', 'updated_at')} for item in rows]
    return {'ok': True, 'project_slug': ctx['slug'], 'buckets': safe, 'count': len(safe)}


def storage_objects_list(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    bucket = str(payload.get('bucket') or '')
    if not BUCKET_RE.fullmatch(bucket):
        raise ValueError('invalid_bucket')
    prefix = str(payload.get('prefix') or '')
    if '..' in prefix.split('/') or len(prefix) > 512:
        raise ValueError('invalid_storage_prefix')
    limit = max(1, min(int(payload.get('limit') or 100), 1000))
    offset = max(0, min(int(payload.get('offset') or 0), 100000))
    sort_column = str(payload.get('sort_column') or 'name')
    if sort_column not in {'name', 'created_at', 'updated_at', 'last_accessed_at'}:
        raise ValueError('invalid_sort_column')
    order = str(payload.get('order') or 'asc').lower()
    if order not in {'asc', 'desc'}:
        raise ValueError('invalid_sort_order')
    base, headers = kong(ctx)
    endpoint = base + '/storage/v1/object/list/' + urllib.parse.quote(bucket, safe='')
    body = {'prefix': prefix, 'limit': limit, 'offset': offset, 'sortBy': {'column': sort_column, 'order': order}}
    response = requests.post(endpoint, headers={**headers, 'Content-Type': 'application/json'}, json=body, timeout=(3, 20))
    if response.status_code != 200:
        raise RuntimeError('storage_object_query_failed')
    rows = response.json()
    rows = rows if isinstance(rows, list) else []
    safe = [{k: jsonable(item.get(k)) for k in ('id', 'name', 'bucket_id', 'owner', 'created_at', 'updated_at', 'last_accessed_at', 'metadata')} for item in rows]
    return {'ok': True, 'project_slug': ctx['slug'], 'bucket': bucket, 'objects': safe, 'count': len(safe), 'prefix': prefix}


def storage_object_read(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    bucket = str(payload.get('bucket') or '')
    object_path = str(payload.get('path') or '').lstrip('/')
    if not BUCKET_RE.fullmatch(bucket) or not object_path or len(object_path) > 1024 or '..' in object_path.split('/'):
        raise ValueError('invalid_storage_object')
    max_bytes = max(1, min(int(payload.get('max_bytes') or 262144), 1048576))
    base, headers = kong(ctx)
    encoded = '/'.join(urllib.parse.quote(part, safe='') for part in object_path.split('/'))
    response = requests.get(base + '/storage/v1/object/authenticated/' + urllib.parse.quote(bucket, safe='') + '/' + encoded, headers=headers, timeout=(3, 30), stream=True)
    if response.status_code == 404:
        response.close()
        response = requests.get(base + '/storage/v1/object/' + urllib.parse.quote(bucket, safe='') + '/' + encoded, headers=headers, timeout=(3, 30), stream=True)
    if response.status_code != 200:
        response.close()
        raise RuntimeError('storage_object_read_failed')
    chunks = []
    total = 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        take = min(len(chunk), max_bytes + 1 - total)
        chunks.append(chunk[:take]); total += take
        if total > max_bytes:
            break
    content_type = response.headers.get('Content-Type', 'application/octet-stream')
    response.close()
    raw = b''.join(chunks)
    truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]
    try:
        text = raw.decode('utf-8')
        encoding = 'utf-8'; content = text
    except UnicodeDecodeError:
        encoding = 'base64'; content = base64.b64encode(raw).decode()
    return {
        'ok': True, 'project_slug': ctx['slug'], 'bucket': bucket, 'path': object_path,
        'content_type': content_type, 'size_returned': len(raw), 'truncated': truncated,
        'sha256': hashlib.sha256(raw).hexdigest(), 'encoding': encoding, 'content': content,
    }


def secrets_list(ctx: dict) -> dict:
    require_role(ctx, 80)
    rows = []
    for name in sorted(k for k in ctx['env'] if is_secret_name(k)):
        value = ctx['env'].get(name, '')
        rows.append({'name': name, 'masked': mask_secret(value), 'configured': bool(value), 'length': len(value)})
    return {'ok': True, 'project_slug': ctx['slug'], 'secrets': rows, 'count': len(rows), 'values_exposed': False}


def rls_inspect(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    schema = ident(payload.get('schema') or 'public')
    if schema.casefold() in {'auth','storage','vault','extensions','pg_catalog','information_schema','pg_toast','realtime','_realtime','supabase_migrations','supabase_functions','pgsodium','graphql'}: raise PermissionError('sensitive_schema_access_denied')
    table = str(payload.get('table') or '').strip()
    params = [schema]
    where = 'n.nspname=%s'
    if table:
        table = ident(table); where += ' and c.relname=%s'; params.append(table)
    statement = f'''select n.nspname as schema_name,c.relname as table_name,c.relrowsecurity as rls_enabled,
      c.relforcerowsecurity as rls_forced,p.polname as policy_name,p.polcmd as command,
      pg_get_expr(p.polqual,p.polrelid) as using_expression,pg_get_expr(p.polwithcheck,p.polrelid) as check_expression
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      left join pg_policy p on p.polrelid=c.oid
      where c.relkind in ('r','p') and {where}
      order by n.nspname,c.relname,p.polname'''
    result = query_rows(ctx, statement, params, 1000, 5000)
    return {'ok': True, 'project_slug': ctx['slug'], 'schema': schema, **result}


def schema_inspect(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 50)
    schema = ident(payload.get('schema') or 'public')
    if schema.casefold() in {'auth','storage','vault','extensions','pg_catalog','information_schema','pg_toast','realtime','_realtime','supabase_migrations','supabase_functions','pgsodium','graphql'}: raise PermissionError('sensitive_schema_access_denied')
    object_type = str(payload.get('object_type') or 'all').lower()
    if object_type not in {'all', 'table', 'view', 'function', 'trigger', 'index', 'type'}:
        raise ValueError('invalid_object_type')
    name = str(payload.get('name') or '').strip()
    if name:
        name = ident(name)
    result = {}
    if object_type in {'all', 'table', 'view'}:
        q = '''select table_schema as schema_name,table_name,table_type from information_schema.tables
          where table_schema=%s and (%s='' or table_name=%s) order by table_name'''
        result['relations'] = query_rows(ctx, q, [schema, name, name], 1000, 5000)['rows']
    if object_type in {'all', 'function'}:
        q = '''select n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid),p.provolatile,p.prosecdef
          from pg_proc p join pg_namespace n on n.oid=p.pronamespace
          where n.nspname=%s and (%s='' or p.proname=%s) order by p.proname'''
        result['functions'] = query_rows(ctx, q, [schema, name, name], 1000, 5000)['rows']
    if object_type in {'all', 'trigger'}:
        q = '''select trigger_schema,event_object_table,trigger_name,event_manipulation,action_timing,action_statement
          from information_schema.triggers where trigger_schema=%s and (%s='' or trigger_name=%s) order by trigger_name'''
        result['triggers'] = query_rows(ctx, q, [schema, name, name], 1000, 5000)['rows']
    if object_type in {'all', 'index'}:
        q = '''select schemaname,tablename,indexname,indexdef from pg_indexes
          where schemaname=%s and (%s='' or indexname=%s) order by indexname'''
        result['indexes'] = query_rows(ctx, q, [schema, name, name], 1000, 5000)['rows']
    if object_type in {'all', 'type'}:
        q = '''select n.nspname,t.typname,t.typtype,t.typcategory from pg_type t join pg_namespace n on n.oid=t.typnamespace
          where n.nspname=%s and (%s='' or t.typname=%s) order by t.typname'''
        result['types'] = query_rows(ctx, q, [schema, name, name], 1000, 5000)['rows']
    return {'ok': True, 'project_slug': ctx['slug'], 'schema': schema, 'object_type': object_type, 'objects': result}


def sanitize_logs(text: str, env: dict[str, str]) -> str:
    out = str(text)
    for name, value in env.items():
        if is_secret_name(name) and len(value) >= 6:
            out = out.replace(value, '<redacted>')
    out = re.sub(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}', '<jwt-redacted>', out)
    out = re.sub(r'(?i)\b(password|secret|token|api[_-]?key|authorization)(\s*[:=]\s*)([^\s,;]+)', r'\1\2<redacted>', out)
    return out[-120000:]


def logs_read(ctx: dict, payload: dict) -> dict:
    require_role(ctx, 80)
    service = str(payload.get('service') or 'db').strip().lower()
    if service not in SERVICE_ALLOWLIST:
        raise ValueError('invalid_service')
    lines = max(1, min(int(payload.get('lines') or 200), 1000))
    since_seconds = max(1, min(int(payload.get('since_seconds') or 3600), 604800))
    container = f"cloudif_{ctx['tenant']}-{service}-1"
    proc = subprocess.run(['docker', 'logs', '--tail', str(lines), '--since', f'{since_seconds}s', container], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if proc.returncode:
        raise RuntimeError('service_logs_unavailable')
    return {'ok': True, 'project_slug': ctx['slug'], 'service': service, 'lines': lines, 'logs': sanitize_logs(proc.stdout, ctx['env']), 'secrets_exposed': False}


def admin_config_read(ctx: dict) -> dict:
    require_role(ctx, 80)
    config = {k: v for k, v in sorted(ctx['env'].items()) if k in SAFE_ENV_KEYS and not is_secret_name(k)}
    services = []
    for service in sorted(SERVICE_ALLOWLIST):
        name = f"cloudif_{ctx['tenant']}-{service}-1"
        try:
            info = docker_inspect(name)
            state = info.get('State') or {}
            services.append({'service': service, 'status': state.get('Status'), 'health': (state.get('Health') or {}).get('Status'), 'running': bool(state.get('Running'))})
        except Exception:
            services.append({'service': service, 'status': 'missing', 'health': None, 'running': False})
    return {'ok': True, 'project_slug': ctx['slug'], 'tenant': ctx['tenant'], 'config': config, 'services': services, 'secret_values_exposed': False}


def record_change_plan(ctx: dict, payload: dict) -> dict:
    schema = ident(payload.get('schema') or 'public')
    table = ident(payload.get('table'))
    action = str(payload.get('action') or '').lower()
    if action not in {'insert', 'update', 'delete'}:
        raise ValueError('invalid_record_action')
    values = payload.get('values') or {}
    filters = payload.get('filters') or {}
    if action in {'insert', 'update'}:
        if not isinstance(values, dict) or not values or len(values) > 64:
            raise ValueError('invalid_values')
        for key in values:
            ident(key)
    if action in {'update', 'delete'} and not filters:
        raise ValueError('filters_required')
    clauses, params = compile_filters(filters)
    estimated = 1 if action == 'insert' else 0
    if action != 'insert':
        statement = sql.SQL('select count(*) from {}.{} where ').format(sql.Identifier(schema), sql.Identifier(table)) + sql.SQL(' and ').join(clauses)
        result = query_rows(ctx, statement, params, 1, 5000)
        estimated = int(result['rows'][0][0]) if result['rows'] else 0
        if estimated > 10000:
            raise PermissionError('record_change_too_large')
    return {'schema': schema, 'table': table, 'action': action, 'value_columns': sorted(values), 'filter_columns': sorted(filters), 'estimated_rows': estimated}


def sql_change_plan(payload: dict, mode: str) -> dict:
    statements = validate_sql(payload.get('sql'), mode)
    return {
        'statement_count': len(statements),
        'statement_types': [re.match(r'^\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)', x).group(1).upper() for x in statements],
        'sql_sha256': hashlib.sha256(str(payload.get('sql')).encode()).hexdigest(),
        'sql_bytes': len(str(payload.get('sql')).encode()),
    }


def secret_read_plan(ctx: dict, payload: dict) -> dict:
    names = payload.get('names') or []
    if not isinstance(names, list) or not names or len(names) > 20:
        raise ValueError('invalid_secret_names')
    clean = []
    for name in names:
        name = str(name).strip().upper()
        if not ENV_RE.fullmatch(name) or name not in ctx['env'] or not is_secret_name(name):
            raise ValueError('unknown_secret_name')
        clean.append(name)
    return {'names': sorted(set(clean)), 'count': len(set(clean)), 'values_exposed': False}


def canonical_plan(ctx: dict, operation: str, payload: dict) -> dict:
    if operation not in APPROVAL_OPERATIONS:
        raise ValueError('invalid_operation')
    minimum = 60 if operation == 'records.change' else 90
    require_role(ctx, minimum)
    if operation == 'records.change':
        summary = record_change_plan(ctx, payload)
    elif operation == 'sql.change':
        summary = sql_change_plan(payload, 'change')
    elif operation == 'rls.change':
        summary = sql_change_plan(payload, 'rls')
    elif operation == 'schema.change':
        summary = sql_change_plan(payload, 'schema')
    else:
        require_role(ctx, 100, 'owner_required_for_secret_values')
        summary = secret_read_plan(ctx, payload)
    canonical = {'project_slug': ctx['slug'], 'tenant': ctx['tenant'], 'operation': operation, 'payload': payload}
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()
    return {'ok': True, 'side_effect_free': True, 'project_slug': ctx['slug'], 'operation': operation, 'plan_digest': digest, 'summary': summary, 'approval_required': True}


def execute_record_change(ctx: dict, payload: dict) -> dict:
    plan = record_change_plan(ctx, payload)
    schema = plan['schema']; table = plan['table']; action = plan['action']
    values = payload.get('values') or {}; filters = payload.get('filters') or {}
    clauses, filter_params = compile_filters(filters)
    with postgres(ctx, False, int(payload.get('timeout_ms') or 15000)) as conn:
        with conn.cursor() as cur:
            if action == 'insert':
                keys = [ident(k) for k in values]
                statement = sql.SQL('insert into {}.{} ({}) values ({})').format(
                    sql.Identifier(schema), sql.Identifier(table), sql.SQL(',').join(sql.Identifier(k) for k in keys),
                    sql.SQL(',').join(sql.Placeholder() for _ in keys),
                )
                cur.execute(statement, [values[k] for k in keys])
            elif action == 'update':
                keys = [ident(k) for k in values]
                statement = sql.SQL('update {}.{} set {} where {}').format(
                    sql.Identifier(schema), sql.Identifier(table),
                    sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in keys),
                    sql.SQL(' and ').join(clauses),
                )
                cur.execute(statement, [values[k] for k in keys] + filter_params)
            else:
                statement = sql.SQL('delete from {}.{} where {}').format(sql.Identifier(schema), sql.Identifier(table), sql.SQL(' and ').join(clauses))
                cur.execute(statement, filter_params)
            affected = cur.rowcount
        conn.commit()
    return {'ok': True, 'operation': 'records.change', 'schema': schema, 'table': table, 'action': action, 'affected_rows': affected}


def execute_sql_change(ctx: dict, payload: dict, mode: str, operation: str) -> dict:
    statements = validate_sql(payload.get('sql'), mode)
    results = []
    with postgres(ctx, False, int(payload.get('timeout_ms') or 20000), db_role='postgres') as conn:
        with conn.cursor() as cur:
            for index, statement in enumerate(statements, 1):
                cur.execute(statement)
                row_count = cur.rowcount
                rows = []
                columns = []
                if cur.description:
                    columns = [d.name for d in cur.description]
                    rows = [[jsonable(v) for v in row] for row in cur.fetchmany(101)]
                    if len(rows) > 100:
                        rows = rows[:100]
                results.append({'index': index, 'row_count': row_count, 'columns': columns, 'rows': rows})
        conn.commit()
    return {'ok': True, 'operation': operation, 'statements': results, 'statement_count': len(statements)}


def execute_secret_read(ctx: dict, payload: dict) -> dict:
    plan = secret_read_plan(ctx, payload)
    return {'ok': True, 'operation': 'secrets.read', 'project_slug': ctx['slug'], 'secrets': {name: ctx['env'][name] for name in plan['names']}, 'count': plan['count'], 'one_time_delivery': True}


def execution_begin(execution_id: str, ctx: dict, operation: str, digest: str) -> dict | None:
    if not re.fullmatch(r'exec_[a-f0-9]{32}', execution_id):
        raise ValueError('invalid_execution_id')
    now = int(time.time())
    conn = db_conn(); conn.execute('begin immediate')
    row = conn.execute('select * from executions where execution_id=?', (execution_id,)).fetchone()
    if row:
        conn.commit(); conn.close()
        if row['project_slug'] != ctx['slug'] or row['operation'] != operation or row['digest'] != digest:
            raise PermissionError('execution_id_conflict')
        if row['status'] == 'success':
            if operation == 'secrets.read':
                raise PermissionError('secret_delivery_already_consumed')
            return json.loads(row['result_json'] or '{}')
        if row['status'] == 'running' and now - int(row['created_at']) < 900:
            raise RuntimeError('execution_in_progress')
        conn = db_conn(); conn.execute('begin immediate'); conn.execute('delete from executions where execution_id=?', (execution_id,)); conn.commit(); conn.close()
    conn = db_conn(); conn.execute('begin immediate')
    conn.execute('insert into executions(execution_id,project_slug,operation,digest,status,result_json,created_at) values(?,?,?,?,?,?,?)', (execution_id, ctx['slug'], operation, digest, 'running', '{}', now))
    conn.commit(); conn.close()
    return None


def execution_finish(execution_id: str, result: dict, success: bool) -> None:
    stored = result
    if result.get('operation') == 'secrets.read':
        stored = {'ok': success, 'operation': 'secrets.read', 'revealed_names': sorted((result.get('secrets') or {}).keys()), 'secret_values_stored': False}
    conn = db_conn()
    conn.execute('update executions set status=?,result_json=?,finished_at=? where execution_id=?', ('success' if success else 'failed', json.dumps(stored, ensure_ascii=False, separators=(',', ':')), int(time.time()), execution_id))
    conn.commit(); conn.close()


def execute_effect(ctx: dict, operation: str, payload: dict, digest: str, execution_id: str) -> dict:
    plan = canonical_plan(ctx, operation, payload)
    if not hmac.compare_digest(plan['plan_digest'], str(digest or '')):
        raise PermissionError('plan_digest_mismatch')
    previous = execution_begin(execution_id, ctx, operation, digest)
    if previous is not None:
        return {**previous, 'idempotent': True}
    try:
        if operation == 'records.change':
            result = execute_record_change(ctx, payload)
        elif operation == 'sql.change':
            result = execute_sql_change(ctx, payload, 'change', operation)
        elif operation == 'rls.change':
            result = execute_sql_change(ctx, payload, 'rls', operation)
        elif operation == 'schema.change':
            result = execute_sql_change(ctx, payload, 'schema', operation)
        else:
            result = execute_secret_read(ctx, payload)
        result.update({'project_slug': ctx['slug'], 'plan_digest': digest, 'execution_id': execution_id, 'idempotent': False})
        execution_finish(execution_id, result, True)
        return result
    except Exception as exc:
        execution_finish(execution_id, {'ok': False, 'operation': operation, 'error': type(exc).__name__}, False)
        raise


def read_action(ctx: dict, action: str, payload: dict) -> dict:
    if action == 'tables.list': return tables_list(ctx, payload)
    if action == 'records.select': return records_select(ctx, payload)
    if action == 'sql.query': return sql_query(ctx, payload)
    if action == 'auth.users.list': return auth_users_list(ctx, payload)
    if action == 'storage.buckets.list': return storage_buckets_list(ctx)
    if action == 'storage.objects.list': return storage_objects_list(ctx, payload)
    if action == 'storage.object.read': return storage_object_read(ctx, payload)
    if action == 'secrets.list': return secrets_list(ctx)
    if action == 'rls.inspect': return rls_inspect(ctx, payload)
    if action == 'schema.inspect': return schema_inspect(ctx, payload)
    if action == 'logs.read': return logs_read(ctx, payload)
    if action == 'admin.config.read': return admin_config_read(ctx)
    raise ValueError('unknown_read_action')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def out(self, code: int, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authed(self) -> bool:
        return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def do_GET(self):
        if self.path == '/health':
            try:
                conn = db_conn(); count = conn.execute('select count(*) from executions').fetchone()[0]; conn.close()
                return self.out(200, {'ok': True, 'service': 'cloudif-supabase-mcp-broker', 'executions': count})
            except Exception:
                return self.out(503, {'ok': False})
        return self.out(404, {'ok': False, 'error': 'not_found'})

    def do_POST(self):
        if not self.authed():
            return self.out(401, {'ok': False, 'error': 'unauthorized'})
        try:
            size = int(self.headers.get('Content-Length', '0') or '0')
            if size < 0 or size > MAX_BODY:
                raise ValueError('request_too_large')
            body = json.loads(self.rfile.read(size) if size else b'{}')
            if not isinstance(body, dict):
                raise ValueError('invalid_request')
            slug = str(body.get('project_slug') or '').strip()
            actor_user = str(body.get('actor_user') or '').strip()
            actor_groups = body.get('actor_groups') or []
            if not isinstance(actor_groups, list):
                raise ValueError('invalid_actor_groups')
            ctx = project_context(slug, actor_user, actor_groups)
            payload = body.get('payload') or {}
            if not isinstance(payload, dict):
                raise ValueError('invalid_payload')
            if self.path == '/v1/read':
                action = str(body.get('action') or '')
                if action not in READ_ACTIONS:
                    raise ValueError('unknown_read_action')
                result = read_action(ctx, action, payload)
            elif self.path == '/v1/plan':
                result = canonical_plan(ctx, str(body.get('operation') or ''), payload)
            elif self.path == '/v1/effect':
                result = execute_effect(ctx, str(body.get('operation') or ''), payload, str(body.get('plan_digest') or ''), str(body.get('execution_id') or ''))
            else:
                return self.out(404, {'ok': False, 'error': 'not_found'})
            result['actor_role'] = ctx['role']
            return self.out(200, result)
        except PermissionError as exc:
            return self.out(403, {'ok': False, 'error': str(exc)})
        except LookupError as exc:
            return self.out(404, {'ok': False, 'error': str(exc)})
        except ValueError as exc:
            return self.out(400, {'ok': False, 'error': str(exc)})
        except RuntimeError as exc:
            return self.out(409 if str(exc) == 'execution_in_progress' else 503, {'ok': False, 'error': str(exc)})
        except Exception:
            return self.out(500, {'ok': False, 'error': 'broker_internal_error'})


if __name__ == '__main__':
    init_state()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
