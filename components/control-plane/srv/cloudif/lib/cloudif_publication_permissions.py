"""Project-scoped permissions for CloudIFF publication promotion.

Global Admin/Professor capabilities and project ownership are implicit. Explicit
rows only delegate Homologation/Production to users already linked to a project.
"""
from __future__ import annotations

import re
import sqlite3
from time import gmtime, strftime
from typing import Any

ADMIN_GROUPS={'cloudif-tenants-admin'}
PROFESSOR_GROUPS={'cloudif-professor','cloudif-professores'}


def _now()->str:
    return strftime('%Y-%m-%dT%H:%M:%SZ',gmtime())


def _username(user:dict[str,Any]|None)->str:
    return str((user or {}).get('username') or '').strip().lower()


def _groups(user:dict[str,Any]|None)->set[str]:
    return {str(x).strip().lower() for x in ((user or {}).get('groups') or []) if str(x).strip()}


def is_admin(user:dict[str,Any]|None)->bool:
    return bool((user or {}).get('admin')) or bool(_groups(user).intersection(ADMIN_GROUPS))


def is_professor(user:dict[str,Any]|None)->bool:
    return bool((user or {}).get('professor')) or bool(_groups(user).intersection(PROFESSOR_GROUPS))


def owner(con:sqlite3.Connection,slug:str)->str:
    row=con.execute('select * from projects where slug=?',(slug,)).fetchone()
    if not row:return ''
    keys=set(row.keys()) if hasattr(row,'keys') else set()
    if 'owner' in keys and row['owner']:return str(row['owner']).strip().lower()
    if 'created_by' in keys and row['created_by']:return str(row['created_by']).strip().lower()
    return ''


def ensure_schema(con:sqlite3.Connection)->None:
    con.execute('''CREATE TABLE IF NOT EXISTS project_publication_permissions(
      project_slug TEXT NOT NULL,
      username TEXT NOT NULL,
      can_homologate INTEGER NOT NULL DEFAULT 0,
      can_publish INTEGER NOT NULL DEFAULT 0,
      granted_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(project_slug,username)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS publication_permission_migrations(
      name TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    )''')
    migrated=con.execute("select 1 from publication_permission_migrations where name='legacy_homologators_v1'").fetchone()
    if migrated:return
    tables={str(row[0]) for row in con.execute("select name from sqlite_master where type='table'")}
    if 'project_homologators' in tables:
        con.execute('''INSERT OR IGNORE INTO project_publication_permissions(
          project_slug,username,can_homologate,can_publish,granted_by,created_at,updated_at
        ) SELECT project_slug,lower(username),1,0,created_by,created_at,created_at
          FROM project_homologators''')
    con.execute("insert into publication_permission_migrations(name,applied_at) values('legacy_homologators_v1',?)",(_now(),))


def _grant(con:sqlite3.Connection,slug:str,username:str)->tuple[bool,bool]:
    ensure_schema(con)
    # Delegation never outlives membership: stale legacy grants are inert.
    if username not in _explicit_members(con,slug):return False,False
    row=con.execute('select can_homologate,can_publish from project_publication_permissions where project_slug=? and username=?',(slug,username)).fetchone()
    return (bool(row[0]),bool(row[1])) if row else (False,False)


def can_homologate(con:sqlite3.Connection,slug:str,user:dict[str,Any])->bool:
    who=_username(user)
    if is_admin(user) or is_professor(user) or (who and who==owner(con,slug)):return True
    return bool(who and _grant(con,slug,who)[0])


def can_publish(con:sqlite3.Connection,slug:str,user:dict[str,Any])->bool:
    who=_username(user)
    if is_admin(user) or is_professor(user) or (who and who==owner(con,slug)):return True
    return bool(who and _grant(con,slug,who)[1])


def can_manage_permissions(user:dict[str,Any])->bool:
    return bool(is_admin(user) or is_professor(user))


def _explicit_members(con:sqlite3.Connection,slug:str)->set[str]:
    rows=con.execute("select subject from project_acl where slug=? and lower(subject_type)='user'",(slug,)).fetchall()
    members={str(row[0] or '').strip().lower() for row in rows if str(row[0] or '').strip()}
    project_owner=owner(con,slug)
    if project_owner:members.add(project_owner)
    return members


def snapshot(con:sqlite3.Connection,slug:str,user:dict[str,Any])->dict[str,Any]:
    ensure_schema(con)
    project_owner=owner(con,slug);current=_username(user);members=_explicit_members(con,slug)
    grants={str(row['username']):row for row in con.execute(
        'select username,can_homologate,can_publish,granted_by,updated_at from project_publication_permissions where project_slug=? order by username',(slug,)
    ).fetchall()}
    # Stale grants are intentionally hidden; only current project members are manageable.
    if current and (is_admin(user) or is_professor(user)):members.add(current)
    rows=[]
    for name in sorted(members):
        implicit_owner=bool(project_owner and name==project_owner)
        implicit_current_admin=bool(name==current and is_admin(user))
        implicit_current_prof=bool(name==current and is_professor(user))
        locked=implicit_owner or implicit_current_admin or implicit_current_prof
        grant=grants.get(name)
        source='Dono do projeto' if implicit_owner else ('Administrador' if implicit_current_admin else ('Professor' if implicit_current_prof else 'Membro do projeto'))
        rows.append({
            'username':name,'source':source,'locked':locked,
            'homologate':True if locked else bool(grant and grant['can_homologate']),
            'publish':True if locked else bool(grant and grant['can_publish']),
            'explicit':bool(grant),'current':name==current,
        })
    return {
        'owner':project_owner,'users':rows,
        'canManagePermissions':can_manage_permissions(user),
        'policy':{'admin':True,'professor':True,'owner':True,'adminImmutable':True},
    }


def set_permissions(con:sqlite3.Connection,slug:str,user:dict[str,Any],entries:list[dict[str,Any]])->dict[str,Any]:
    ensure_schema(con)
    if not can_manage_permissions(user):raise PermissionError('Somente Administrador ou Professor pode alterar permissões de publicação.')
    allowed=_explicit_members(con,slug);project_owner=owner(con,slug);actor=_username(user) or 'portal'
    normalized={}
    for entry in entries or []:
        if not isinstance(entry,dict):continue
        name=str(entry.get('username') or '').strip().lower()
        if not name:continue
        if not re.fullmatch(r'[a-z0-9._@-]{2,128}',name):raise ValueError('Nome de usuário inválido: '+name[:40])
        if name not in allowed:raise PermissionError(f'O usuário {name} não está vinculado ao projeto.')
        if name==project_owner:continue
        normalized[name]=(bool(entry.get('homologate')),bool(entry.get('publish')))
    now=_now()
    existing={str(row[0]) for row in con.execute('select username from project_publication_permissions where project_slug=?',(slug,)).fetchall()}
    for name in existing-set(normalized):
        con.execute('delete from project_publication_permissions where project_slug=? and username=?',(slug,name))
    for name,(hom,pub) in normalized.items():
        if not hom and not pub:
            con.execute('delete from project_publication_permissions where project_slug=? and username=?',(slug,name));continue
        con.execute('''insert into project_publication_permissions(project_slug,username,can_homologate,can_publish,granted_by,created_at,updated_at)
            values(?,?,?,?,?,?,?) on conflict(project_slug,username) do update set
            can_homologate=excluded.can_homologate,can_publish=excluded.can_publish,granted_by=excluded.granted_by,updated_at=excluded.updated_at''',
            (slug,name,int(hom),int(pub),actor,now,now))
    # Keep the legacy homologator table synchronized so old readers cannot resurrect removed grants.
    tables={str(row[0]) for row in con.execute("select name from sqlite_master where type='table'")}
    if 'project_homologators' in tables:
        con.execute('delete from project_homologators where project_slug=?',(slug,))
        for name,(hom,_pub) in normalized.items():
            if hom:con.execute('insert into project_homologators(project_slug,username,created_by,created_at) values(?,?,?,?)',(slug,name,actor,now))
    con.commit()
    return snapshot(con,slug,user)


def replace_homologators(con:sqlite3.Connection,slug:str,user:dict[str,Any],usernames:list[str])->dict[str,Any]:
    ensure_schema(con)
    if not can_manage_permissions(user):raise PermissionError('Somente Administrador ou Professor pode alterar homologadores.')
    clean=[]
    for raw in usernames or []:
        name=str(raw or '').strip().lower()
        if not name:continue
        if not re.fullmatch(r'[a-z0-9._@-]{2,128}',name):raise ValueError('Nome de usuário inválido: '+name[:40])
        if name not in clean:clean.append(name)
    actor=_username(user) or 'portal';now=_now();project_owner=owner(con,slug)
    existing=[str(row[0]) for row in con.execute('select username from project_publication_permissions where project_slug=?',(slug,)).fetchall()]
    for name in existing:
        if name==project_owner:continue
        con.execute('update project_publication_permissions set can_homologate=?,granted_by=?,updated_at=? where project_slug=? and username=?',(1 if name in clean else 0,actor,now,slug,name))
    for name in clean:
        if name==project_owner:continue
        con.execute('''insert into project_publication_permissions(project_slug,username,can_homologate,can_publish,granted_by,created_at,updated_at)
          values(?,?,1,0,?,?,?) on conflict(project_slug,username) do update set can_homologate=1,granted_by=excluded.granted_by,updated_at=excluded.updated_at''',(slug,name,actor,now,now))
    con.execute('delete from project_publication_permissions where project_slug=? and can_homologate=0 and can_publish=0',(slug,))
    tables={str(row[0]) for row in con.execute("select name from sqlite_master where type='table'")}
    if 'project_homologators' in tables:
        con.execute('delete from project_homologators where project_slug=?',(slug,))
        for name in clean:con.execute('insert into project_homologators(project_slug,username,created_by,created_at) values(?,?,?,?)',(slug,name,actor,now))
    con.commit()
    return snapshot(con,slug,user)
