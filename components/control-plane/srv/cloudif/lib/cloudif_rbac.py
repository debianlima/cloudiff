from __future__ import annotations
import os, sqlite3
from dataclasses import dataclass
from typing import Iterable

DB_PATH=os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/qa/cloudif-portal.db')
ADMIN_GROUPS={x.strip().lower() for x in os.environ.get('CLOUDIF_ADMIN_GROUPS','cloudif-tenants-admin,cloudif-admin,domain admins').replace('|',',').split(',') if x.strip()}
ROLE_LEVEL={'none':0,'viewer':10,'read':10,'reader':10,'user':10,'developer':20,'editor':20,'write':20,'manager':30,'manage':30,'admin':40,'administrator':40,'owner':50,'dono':50,'proprietario':50,'proprietário':50}
ACTION_LEVEL={'project.view':10,'project.edit':20,'project.manage':30,'project.delete':50,'tenant.view':10,'tenant.manage':30,'tenant.delete':50,'admin.global':40}

def _groups(value)->set[str]:
    if isinstance(value,(list,tuple,set)): vals=value
    else: vals=str(value or '').replace('|',',').split(',')
    return {str(x).strip().lower() for x in vals if str(x).strip()}

def _identities(user)->set[str]:
    vals={str((user or {}).get(k) or '').strip().lower() for k in ('username','email','name')}
    return {x for x in vals if x}

def is_global_admin(user)->bool:
    return bool(_groups((user or {}).get('groups')) & ADMIN_GROUPS) or bool((user or {}).get('admin'))

def _level(role)->int:
    return ROLE_LEVEL.get(str(role or '').strip().lower(),0)

def _project_level(con, user, slug)->int:
    ids=_identities(user); groups=_groups((user or {}).get('groups'))
    row=con.execute('select owner from projects where slug=?',(slug,)).fetchone()
    if row and str(row[0] or '').strip().lower() in ids: return 50
    level=0
    for stype,subject,role in con.execute('select subject_type,subject_value,role from project_permissions where project=?',(slug,)):
        subject=str(subject or '').strip().lower()
        if (stype=='user' and subject in ids) or (stype=='group' and subject in groups): level=max(level,_level(role))
    for stype,subject in con.execute('select subject_type,subject from project_acl where slug=?',(slug,)):
        subject=str(subject or '').strip().lower()
        if (stype=='user' and subject in ids) or (stype=='group' and subject in groups): level=max(level,10)
    return level

def _tenant_level(con,user,tenant)->int:
    ids=_identities(user); groups=_groups((user or {}).get('groups')); level=0
    for stype,subject in con.execute('select subject_type,subject from tenant_acl where tenant=?',(tenant,)):
        subject=str(subject or '').strip().lower()
        if (stype=='user' and subject in ids) or (stype=='group' and subject in groups): level=max(level,10)
    return level

def authorize(user, action, *, project='', tenant='')->bool:
    if is_global_admin(user): return True
    need=ACTION_LEVEL.get(action,99)
    if action=='admin.global': return False
    with sqlite3.connect(DB_PATH) as con:
        level=_project_level(con,user,project) if action.startswith('project.') else _tenant_level(con,user,tenant)
    return level>=need

def explain(user, action, *, project='', tenant='')->dict:
    admin=is_global_admin(user)
    if admin: return {'allowed':True,'reason':'global_admin','level':40,'required':ACTION_LEVEL.get(action,99)}
    with sqlite3.connect(DB_PATH) as con:
        level=_project_level(con,user,project) if action.startswith('project.') else _tenant_level(con,user,tenant)
    need=ACTION_LEVEL.get(action,99)
    return {'allowed':level>=need,'reason':'resource_role','level':level,'required':need}
