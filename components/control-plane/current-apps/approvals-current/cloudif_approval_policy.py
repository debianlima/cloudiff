#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any


def init_tables(connection: sqlite3.Connection) -> None:
    connection.executescript('''
    create table if not exists approval_policies(
      policy_id text primary key,
      project_slug text not null,
      action text not null,
      requested_by text not null,
      created_by text not null,
      creator_role text not null,
      source_approval_id text not null,
      created_at integer not null,
      revoked_at integer,
      revoked_by text,
      revoke_reason text
    );
    create unique index if not exists idx_approval_policy_active_scope
      on approval_policies(project_slug,action,requested_by)
      where revoked_at is null;
    create index if not exists idx_approval_policy_project
      on approval_policies(project_slug,created_at desc);
    create table if not exists approval_policy_requests(
      approval_id text primary key,
      requested_by_human text not null,
      requester_role text not null,
      requested_at integer not null
    );
    ''')


def active_policy(connection: sqlite3.Connection, project_slug: str, action: str, requested_by: str) -> dict[str, Any] | None:
    row=connection.execute('''select * from approval_policies
      where project_slug=? and action=? and requested_by=? and revoked_at is null
      order by created_at desc limit 1''',(project_slug,action,requested_by)).fetchone()
    return dict(row) if row else None


def request_persistent(connection: sqlite3.Connection, approval_id: str, human: str, role: str, now: int | None = None) -> None:
    timestamp=int(now or time.time())
    connection.execute('''insert into approval_policy_requests(approval_id,requested_by_human,requester_role,requested_at)
      values(?,?,?,?) on conflict(approval_id) do update set requested_by_human=excluded.requested_by_human,
      requester_role=excluded.requester_role,requested_at=excluded.requested_at''',(approval_id,human,role,timestamp))


def pending_request(connection: sqlite3.Connection, approval_id: str) -> dict[str, Any] | None:
    row=connection.execute('select * from approval_policy_requests where approval_id=?',(approval_id,)).fetchone()
    return dict(row) if row else None


def activate_from_approval(connection: sqlite3.Connection, approval: sqlite3.Row | dict[str, Any], now: int | None = None) -> dict[str, Any] | None:
    approval_id=str(approval['approval_id'])
    request=pending_request(connection,approval_id)
    if not request:return None
    existing=active_policy(connection,str(approval['project_slug']),str(approval['action']),str(approval['requested_by']))
    if existing:
        connection.execute('delete from approval_policy_requests where approval_id=?',(approval_id,))
        return existing
    timestamp=int(now or time.time());policy_id='pol_'+uuid.uuid4().hex[:20]
    connection.execute('''insert into approval_policies(policy_id,project_slug,action,requested_by,created_by,creator_role,source_approval_id,created_at)
      values(?,?,?,?,?,?,?,?)''',(policy_id,approval['project_slug'],approval['action'],approval['requested_by'],request['requested_by_human'],request['requester_role'],approval_id,timestamp))
    connection.execute('delete from approval_policy_requests where approval_id=?',(approval_id,))
    row=connection.execute('select * from approval_policies where policy_id=?',(policy_id,)).fetchone()
    return dict(row) if row else None


def list_policies(connection: sqlite3.Connection, status: str='active') -> list[dict[str, Any]]:
    if status=='active':rows=connection.execute('select * from approval_policies where revoked_at is null order by created_at desc').fetchall()
    else:rows=connection.execute('select * from approval_policies order by created_at desc').fetchall()
    return [dict(row) for row in rows]


def revoke(connection: sqlite3.Connection, policy_id: str, revoked_by: str, reason: str='', now: int | None = None) -> dict[str, Any]:
    timestamp=int(now or time.time())
    row=connection.execute('select * from approval_policies where policy_id=?',(policy_id,)).fetchone()
    if not row:raise LookupError('policy_not_found')
    if row['revoked_at']:
        return {'ok':True,'policy_id':policy_id,'revoked':True,'idempotent':True,'revoked_at':int(row['revoked_at'])}
    connection.execute('update approval_policies set revoked_at=?,revoked_by=?,revoke_reason=? where policy_id=? and revoked_at is null',(timestamp,revoked_by,str(reason or '')[:500],policy_id))
    return {'ok':True,'policy_id':policy_id,'revoked':True,'idempotent':False,'revoked_at':timestamp}
