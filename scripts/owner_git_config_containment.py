#!/usr/bin/env python3
"""Owner-only G4 interim mitigation for authenticated Git-origin config readability.

Does NOT rotate tokens, alter Git URLs, or read content into stdout.
Apply requires privileged host owner, explicit roots, exact expected count,
an owner-matching service identity and a protected rollback manifest.
"""
import argparse
import hashlib
import json
import os
import pwd
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

URL_LINE=re.compile(rb'^\s*(?:url|pushurl)\s*=\s*(.*?)\s*$',re.IGNORECASE)
FLAGS=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_CLOEXEC',0)


def _assert_trusted_ancestors(path, uid, stop=None):
    cur=Path(path).absolute()
    while True:
        st=os.lstat(cur)
        if (not stat.S_ISDIR(st.st_mode) or
                stat.S_ISLNK(st.st_mode) or
                st.st_uid not in (0,uid) or st.st_mode & 0o022):
            raise PermissionError('untrusted_directory_component')
        if (stop is not None and cur==Path(stop).absolute()) or (
                stop is None and cur==Path('/')):
            return
        cur=cur.parent


def _is_authenticated_url(raw):
    raw=raw.strip()
    if raw.startswith(b'"') and raw.endswith(b'"'):
        raw=raw[1:-1]
    if not raw or any(c<33 or c==127 for c in raw):
        raise ValueError('unsafe_git_remote_url')
    try:
        u=urlsplit(raw.decode('utf-8','strict'))
        if u.scheme in ('http','https') and not u.hostname:
            raise ValueError('malformed_git_remote_url')
        return bool(u.scheme in ('http','https') and u.hostname and (
            u.username is not None or u.password is not None
        ))
    except (UnicodeError,ValueError):
        # Fail closed: malformed URLs cannot be safely classified.
        raise ValueError('unparseable_git_remote_url') from None


def _read_candidate(path, uid, root):
    path=Path(path).absolute()
    _assert_trusted_ancestors(path.parent,uid,root)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('symlink_config_not_allowed')
    fd=os.open(path,FLAGS)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1):
            raise ValueError('not_single_regular_file')
        data=os.read(fd,1024*1024+1)
        if len(data)>1024*1024:
            raise ValueError('config_too_large')
        has_auth=any(_is_authenticated_url(m.group(1))
                     for line in data.splitlines()
                     if (m:=URL_LINE.match(line)))
        return {
            'path':str(path),'mode':stat.S_IMODE(st.st_mode),
            'owner_uid':st.st_uid,'group_gid':st.st_gid,
            'inode':st.st_ino,'device':st.st_dev,
            'sha256':hashlib.sha256(data).hexdigest(),
            'auth':bool(has_auth),
        }
    finally:
        os.close(fd)


def build_plan(roots,service_uid):
    plan=[]
    for raw_root in roots:
        root=Path(raw_root).absolute()
        _assert_trusted_ancestors(root,service_uid,stop=root)
        for cfg in root.rglob('config'):
            if cfg.parent.name!='.git':
                continue
            plan.append(_read_candidate(cfg,service_uid,root))
    paths=[v['path'] for v in plan]
    if len(paths)!=len(set(paths)):
        raise ValueError('duplicate_config_from_overlapping_roots')
    return sorted(plan,key=lambda x:x['path'])


def _manifest_write(path,body,uid):
    path=Path(path).absolute()
    _assert_trusted_ancestors(path.parent,uid,stop=path.parent)
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags,0o600)
    try:
        raw=json.dumps(body,sort_keys=True,indent=2).encode()
        os.write(fd,raw)
        os.fchmod(fd,0o600)
        os.fsync(fd)
    finally:
        os.close(fd)


def _chmod_checked(entry,desired,root,uid,expected):
    path=Path(entry['path'])
    if not path.is_relative_to(Path(root).absolute()):
        raise PermissionError('config_outside_approved_root')
    current=_read_candidate(path,uid,root)
    for field in ('owner_uid','inode','device','sha256'):
        if current[field]!=entry[field]:
            raise RuntimeError('config_changed_since_inventory')
    if current['owner_uid']!=uid:
        raise PermissionError('service_user_not_file_owner')
    if current['mode']!=expected:
        raise RuntimeError('file_mode_changed_since_inventory')
    fd=os.open(path,FLAGS)
    try:
        st=os.fstat(fd)
        if st.st_ino!=entry['inode'] or st.st_dev!=entry['device']:
            raise RuntimeError('config_replaced')
        os.fchmod(fd,desired)
        os.fsync(fd)
        if stat.S_IMODE(os.fstat(fd).st_mode)!=desired:
            raise RuntimeError('mode_change_not_verified')
    finally:
        os.close(fd)


def apply_plan(rows,roots,uid,expected_count,manifest):
    affected=[x for x in rows if x['auth']]
    if len(affected)!=expected_count:
        raise RuntimeError('authenticated_config_count_mismatch')
    if not affected:
        raise RuntimeError('no_authenticated_configs_to_protect')
    if any(x['owner_uid']!=uid for x in affected):
        raise PermissionError('service_user_not_file_owner')
    for row in affected:
        if not any(Path(row['path']).is_relative_to(Path(r).absolute()) for r in roots):
            raise PermissionError('path_not_in_allowed_roots')
    items=[dict(x,new_mode=x['mode']&0o600) for x in affected]
    record={'version':1,'service_uid':uid,'roots':[str(Path(r).absolute()) for r in roots],'files':items}
    _manifest_write(manifest,record,uid)
    updated=[]
    try:
        for x in items:
            root=next(r for r in roots if Path(x['path']).is_relative_to(Path(r).absolute()))
            _chmod_checked(x,x['new_mode'],root,uid,x['mode'])
            updated.append(x)
    except Exception:
        for x in reversed(updated):
            try:
                root=next(r for r in roots if Path(x['path']).is_relative_to(Path(r).absolute()))
                _chmod_checked(x,x['mode'],root,uid,x['new_mode'])
            except Exception:
                pass  # Owner must inspect protected manifest; never erase it.
        raise
    return {'configs_tightened':len(items),'manifest_created':True,'secrets_printed':False}


def rollback(manifest,uid,roots):
    fd=os.open(manifest,FLAGS)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_mode&0o077 or st.st_uid!=os.geteuid():
            raise PermissionError('manifest_not_root_private')
        data=os.read(fd,1024*1024)
    finally:
        os.close(fd)
    record=json.loads(data)
    if record.get('version')!=1 or record.get('service_uid')!=uid:
        raise ValueError('manifest_identity_mismatch')
    approved=[str(Path(r).absolute()) for r in roots]
    if record.get('roots')!=approved:
        raise PermissionError('manifest_root_mismatch')
    # Preflight the whole manifest before changing the first file.
    for x in record['files']:
        root=next((r for r in roots if Path(x['path']).is_relative_to(Path(r).absolute())),None)
        if root is None:
            raise PermissionError('rollback_outside_roots')
        current=_read_candidate(x['path'],uid,root)
        for field in ('owner_uid','inode','device','sha256'):
            if current[field]!=x[field]:
                raise RuntimeError('rollback_file_changed')
        if current['mode']!=x['new_mode']:
            raise RuntimeError('rollback_file_mode_changed')
    for x in record['files']:
        root=next(r for r in roots if Path(x['path']).is_relative_to(Path(r).absolute()))
        _chmod_checked(x,x['mode'],root,uid,x['new_mode'])
    return {'configs_restored':len(record['files']),'secrets_printed':False}


def main():
    p=argparse.ArgumentParser(description='Owner-only G4 Git config permission containment')
    p.add_argument('action',choices=('plan','apply','rollback'))
    p.add_argument('--root',action='append',required=True)
    p.add_argument('--service-user',required=True)
    p.add_argument('--manifest')
    p.add_argument('--expect-count',type=int)
    p.add_argument('--confirm-world-readable-rollback',action='store_true')
    a=p.parse_args()
    uid=pwd.getpwnam(a.service_user).pw_uid
    if a.action!='plan' and os.geteuid()!=0:
        raise SystemExit('BLOCKED_OWNER_ROOT_REQUIRED')
    if a.action in ('apply','rollback') and not a.manifest:
        raise SystemExit('BLOCKED_MANIFEST_REQUIRED')
    if a.action=='apply' and (a.expect_count is None or a.expect_count<1):
        raise SystemExit('BLOCKED_EXPECT_COUNT_REQUIRED')
    roots=[str(Path(r).absolute()) for r in a.root]
    # Production CLI always checks the whole ancestry, unlike synthetic
    # unit tests that can exercise library functions under /tmp.
    for root in roots:
        _assert_trusted_ancestors(root,uid)
    if a.action in ('apply','rollback'):
        parent=Path(a.manifest).absolute().parent
        _assert_trusted_ancestors(parent,uid)
        st=os.stat(parent)
        if st.st_uid!=0 or stat.S_IMODE(st.st_mode)&0o077:
            raise SystemExit('BLOCKED_ROOT_PRIVATE_MANIFEST_DIRECTORY_REQUIRED')
    if a.action=='rollback' and not a.confirm_world_readable_rollback:
        raise SystemExit('BLOCKED_EXPLICIT_INSECURE_ROLLBACK_CONFIRMATION_REQUIRED')
    if a.action=='rollback':
        result=rollback(a.manifest,uid,roots)
    else:
        rows=build_plan(roots,uid)
        selected=[x for x in rows if x['auth']]
        result={'configs_scanned':len(rows),'configs_with_userinfo':len(selected),
                'configs_needing_private_mode':sum(bool(x['mode']&0o077) for x in selected),
                'service_owner_mismatch':sum(x['owner_uid']!=uid for x in selected),
                'secrets_printed':False,'rotation_completed':False}
        if a.action=='apply':
            result=apply_plan(rows,roots,uid,a.expect_count,a.manifest)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
