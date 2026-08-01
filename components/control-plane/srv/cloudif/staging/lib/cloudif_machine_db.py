#!/usr/bin/env python3
import os, sqlite3
from pathlib import Path

BACKEND=os.environ.get('CLOUDIF_MACHINE_DB_BACKEND','postgresql').strip().lower()
SQLITE_PATH=Path(os.environ.get('CLOUDIF_MACHINE_SQLITE_PATH','/var/lib/cloudif-machine-admin/controller.db'))

def _pg_connect():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    raw=psycopg2.connect(
        host=os.environ.get('CLOUDIF_MACHINE_DB_HOST','127.0.0.1'),
        port=int(os.environ.get('CLOUDIF_MACHINE_DB_PORT','55432')),
        dbname=os.environ.get('CLOUDIF_MACHINE_DB_NAME','cloudif_machine_admin'),
        user=os.environ.get('CLOUDIF_MACHINE_DB_USER','cloudif_machine_admin'),
        password=os.environ.get('CLOUDIF_MACHINE_DB_PASSWORD',''),
        connect_timeout=8,
        application_name=os.environ.get('CLOUDIF_MACHINE_DB_APP','cloudif-machine-admin'),
    )
    return PgConnection(raw,RealDictCursor)

class PgConnection:
    def __init__(self,raw,cursor_factory): self.raw=raw; self.cursor_factory=cursor_factory
    def execute(self,sql,params=()):
        cur=self.raw.cursor(cursor_factory=self.cursor_factory)
        cur.execute(sql.replace('?', '%s'),params)
        return cur
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()


def connect():
    if BACKEND in {'postgres','postgresql','pg'}: return _pg_connect()
    SQLITE_PATH.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(SQLITE_PATH,timeout=30); c.row_factory=sqlite3.Row; c.execute('pragma busy_timeout=30000'); return c

PG_SCHEMA='''
create table if not exists machines(
 machine_id text primary key, hostname text not null, state text not null,
 first_seen text not null,last_seen text not null,public_key_b64 text not null,
 inventory_hash text default '', inventory_json text default '{}', policy_version integer not null default 0,
 policy_json text default '{}', message text default ''
);
create table if not exists inventory_events(
 id bigserial primary key, machine_id text not null, created_at text not null,
 inventory_hash text not null, inventory_json text not null
);
create table if not exists guardian_events(
 id bigserial primary key, machine_id text not null, created_at text not null,
 severity text not null, event text not null, message text default '', detail_json text default '{}'
);
create table if not exists certificate_history(
 id bigserial primary key, machine_id text not null, cert_id text not null,
 name text not null, source text not null, fingerprint_sha256 text not null,
 subject text default '', issuer text default '', not_before text default '', not_after text default '',
 first_seen text not null, last_seen text not null, state text not null, days_remaining integer,
 unique(machine_id, cert_id, fingerprint_sha256)
);
create table if not exists certificate_alerts(
 id bigserial primary key, machine_id text not null, cert_id text not null,
 alert_key text not null unique, severity text not null, state text not null,
 opened_at text not null, updated_at text not null, resolved_at text,
 message text not null, detail_json text default '{}', dispatch_hash text default '',
 last_notified_at text, notify_count integer not null default 0
);
create index if not exists idx_inventory_events_machine_created on inventory_events(machine_id,created_at desc);
create index if not exists idx_guardian_events_machine_created on guardian_events(machine_id,created_at desc);
create index if not exists idx_cert_history_machine_cert on certificate_history(machine_id,cert_id,last_seen desc);
create index if not exists idx_cert_alerts_state_updated on certificate_alerts(state,updated_at desc);
'''

SQLITE_SCHEMA='''
create table if not exists machines(machine_id text primary key, hostname text not null, state text not null,first_seen text not null,last_seen text not null,public_key_b64 text not null,inventory_hash text default '',inventory_json text default '{}',policy_version integer not null default 0,policy_json text default '{}',message text default '');
create table if not exists inventory_events(id integer primary key autoincrement,machine_id text not null,created_at text not null,inventory_hash text not null,inventory_json text not null);
create table if not exists guardian_events(id integer primary key autoincrement,machine_id text not null,created_at text not null,severity text not null,event text not null,message text default '',detail_json text default '{}');
create table if not exists certificate_history(id integer primary key autoincrement,machine_id text not null,cert_id text not null,name text not null,source text not null,fingerprint_sha256 text not null,subject text default '',issuer text default '',not_before text default '',not_after text default '',first_seen text not null,last_seen text not null,state text not null,days_remaining integer,unique(machine_id,cert_id,fingerprint_sha256));
create table if not exists certificate_alerts(id integer primary key autoincrement,machine_id text not null,cert_id text not null,alert_key text not null unique,severity text not null,state text not null,opened_at text not null,updated_at text not null,resolved_at text,message text not null,detail_json text default '{}',dispatch_hash text default '',last_notified_at text,notify_count integer not null default 0);
'''

def init_schema():
    c=connect()
    if BACKEND in {'postgres','postgresql','pg'}:
        for stmt in [x.strip() for x in PG_SCHEMA.split(';') if x.strip()]: c.execute(stmt)
    else:
        c.executescript(SQLITE_SCHEMA)
    c.commit(); c.close()

def table_columns(c,table):
    if BACKEND in {'postgres','postgresql','pg'}:
        return {r['column_name'] for r in c.execute('select column_name from information_schema.columns where table_schema=current_schema() and table_name=?',(table,)).fetchall()}
    return {r[1] for r in c.execute(f'pragma table_info({table})')}
