#!/usr/bin/env python3
"""Standalone offline prototype: per-project monotonic ACL revision/lock gate.

NOT WIRED TO CLOUDIFF PRODUCTION. Import only inside sandbox tests.
The upstream caller MUST authenticate and derive `verified_source` out-of-band.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Callable

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


class GateError(Exception):
    def __init__(self, code: str):
        self.code=code
        super().__init__(code)


def authoritative_request(request: dict[str, Any]) -> tuple[str, int, str]:
    """Validate shape, reject ambiguous or stale snapshot preconditions."""
    if not isinstance(request,dict):raise GateError('invalid_request')
    allowed = {"project","acl_revision","owner","acl","stack_ids","repo_id","server_id"}
    if set(request) - allowed:raise GateError("unexpected_fields")
    project=request.get('project')
    revision=request.get('acl_revision')
    owner=request.get('owner')
    acl=request.get('acl')
    if not isinstance(project,str) or not SLUG.fullmatch(project):raise GateError('invalid_project')
    if type(revision) is not int or not (1<=revision<2**62):raise GateError('revision_required')
    if not isinstance(owner,str) or not owner.strip() or len(owner)>256 or any(ord(ch)<32 for ch in owner):raise GateError('invalid_owner')
    if not isinstance(acl,list):raise GateError('invalid_acl')
    entries=[]
    seen=set()
    for member in acl:
        if not isinstance(member,dict) or set(member)!={'type','subject'}:raise GateError('invalid_acl_member')
        typ,subject=member['type'],member['subject']
        if not isinstance(typ,str) or typ not in ('user','group'):raise GateError('invalid_acl_member')
        if not isinstance(subject,str) or not subject.strip() or len(subject)>256 or any(ord(ch)<32 for ch in subject):raise GateError('invalid_acl_member')
        token=(typ,subject.casefold())
        if token in seen:raise GateError('duplicate_acl_member')
        seen.add(token)
        entries.append({'type':typ,'subject':subject})
    ids=request.get('stack_ids')
    repo=request.get('repo_id')
    server=request.get('server_id','')
    if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x.strip() for x in ids):raise GateError('resource_required')
    if len(set(ids))!=len(ids):raise GateError('duplicate_resource')
    if not isinstance(repo,str) or not repo.strip():raise GateError('resource_required')
    if not isinstance(server,str):raise GateError('invalid_resource')
    # Project, principal, membership and target resources are jointly versioned.
    canonical={'project':project,'owner':owner.strip().casefold(),
               'acl':sorted(({'type':x['type'],'subject':x['subject'].casefold()} for x in entries),key=lambda x:(x['type'],x['subject'])),
               'stack_ids':sorted(ids),'repo_id':repo,'server_id':server}
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return project,revision,digest


def _state_load(filename: Path) -> dict[str,Any] | None:
    if filename.is_symlink():raise GateError('unsafe_state_link')
    if not filename.exists():return None
    # A hardlinked / foreign-owned state file must never be read or overwritten.
    # This offline research guard does not establish multi-process pathname trust.
    try: metadata = filename.lstat()
    except OSError as exc: raise GateError('unreadable_state') from exc
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077):
        raise GateError('unsafe_state_file')
    try:
        data=json.loads(filename.read_text())
    except (OSError,ValueError) as exc:
        raise GateError('unreadable_state') from exc
    if not isinstance(data,dict) or data.get('schema')!=2 or data.get('status') not in ('ready','applying'):
        raise GateError('legacy_migration_required')
    if type(data.get('revision')) is not int or not isinstance(data.get('digest'),str):raise GateError('unreadable_state')
    return data


def _fsync_dir(root: Path):
    flags=os.O_RDONLY|getattr(os,'O_DIRECTORY',0)
    fd=os.open(str(root),flags)
    try:os.fsync(fd)
    finally:os.close(fd)


def _atomic_json(filename: Path, data:dict[str,Any]):
    """Write complete state or retain previous bytes after crash before rename."""
    fd,name=tempfile.mkstemp(prefix='.acl-pending-',dir=filename.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            os.fchmod(out.fileno(),0o600)
            json.dump(data,out,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name,filename)
        _fsync_dir(filename.parent)
    finally:
        if os.path.exists(name):os.unlink(name)


@contextlib.contextmanager
def _project_lock(root:Path,project:str):
    if root.is_symlink():raise GateError('unsafe_state_root')
    if not root.exists():root.mkdir(parents=True,mode=0o700)
    if not root.is_dir():raise GateError('invalid_state_root')
    mode=root.stat().st_mode & 0o777
    if mode & 0o077:raise GateError('insecure_state_permissions')
    path=root/(project+'.lock')
    flags=os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)
    try:fd=os.open(path,flags,0o600)
    except OSError as exc:raise GateError('lock_unavailable') from exc
    try:
        metadata=os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_uid != os.geteuid():
            raise GateError('unsafe_lock_file')
        if metadata.st_mode & 0o077:raise GateError('insecure_lock_permissions')
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        try:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)


def apply_revision(root:Path, request:dict[str,Any],verified_source:str,
                   apply:Callable[[dict[str,Any],list],dict[str,Any]]) -> dict[str,Any]:
    """Serializes one project's apply, rejects stale/conflicting replays.

    A failed/partial external apply leaves status='applying' for manual reconcile.
    Source must be attested by the authenticated HTTP caller, not request fields.
    """
    project,revision,digest=authoritative_request(request)
    if verified_source not in ('portal','replay'):raise GateError('untrusted_source')
    root=Path(root)
    with _project_lock(root,project):
        filename=root/(project+'.json')
        state=_state_load(filename)
        if state is not None and state['status']=='applying':raise GateError('manual_recovery_required')
        if state is not None and revision<state['revision']:raise GateError('stale_acl_revision')
        if state is not None and revision==state['revision'] and digest!=state['digest']:
            raise GateError('revision_digest_conflict')
        if verified_source=='replay' and (state is None or state['revision']!=revision or state['digest']!=digest):
            raise GateError('unauthorized_replay')
        prior=state or None
        staged={'schema':2,'status':'applying','revision':revision,'digest':digest,
                'prior':prior,'request':request}
        _atomic_json(filename,staged)
        try:out=apply(request, list((state or {}).get('targets') or []))
        except Exception as exc:
            # Do not automatically re-run after ambiguous partial external writes.
            raise GateError('apply_interrupted_manual_recovery') from exc
        if not isinstance(out,dict) or out.get('ok') is not True:
            raise GateError('apply_failed_manual_recovery')
        targets=out.get('targets')
        if not isinstance(targets,list):raise GateError('invalid_apply_result_manual_recovery')
        new={'schema':2,'status':'ready','revision':revision,'digest':digest,
             'request':request,'targets':targets}
        _atomic_json(filename,new)
        return {'ok':True,'project':project,'revision':revision,'status':'ready',
                'replayed':verified_source=='replay'}
