#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path

def split_csv(s):
    out = []
    for x in (s or "").replace(";", ",").split(","):
        x = x.strip()
        if x:
            out.append(x)
    return out

def norm(s):
    return (s or "").strip().lower()

def load_env_file(path):
    data = {}
    p = Path(path)
    if not p.exists():
        return data
    for line in p.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data

def load_access_dir(tenant, access_dir):
    """
    Formato simples:
      /var/lib/cloudif/tenant-access/<tenant>.users
      /var/lib/cloudif/tenant-access/<tenant>.groups

    Cada linha: um usuário ou grupo.
    Comentários com #.
    """
    users = set()
    groups = set()
    base = Path(access_dir)
    for suffix, target in [(".users", users), (".groups", groups)]:
        p = base / f"{tenant}{suffix}"
        if not p.exists():
            continue
        for line in p.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            target.add(norm(line))
    return users, groups

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["access", "create"], required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--groups", default="")
    ap.add_argument("--env", default="/etc/cloudif/cloudif-access.env")
    args = ap.parse_args()

    cfg = {}
    cfg.update(os.environ)
    cfg.update(load_env_file(args.env))

    tenant = norm(args.tenant)
    username = norm(args.username)
    groups_raw = split_csv(args.groups)
    groups_norm = {norm(g) for g in groups_raw}

    admin_users = {norm(x) for x in split_csv(cfg.get("CLOUDIF_ADMIN_USERS", ""))}
    admin_groups = {norm(x) for x in split_csv(cfg.get("CLOUDIF_ADMIN_GROUPS", ""))}
    create_groups = {norm(x) for x in split_csv(cfg.get("CLOUDIF_TENANT_CREATE_GROUPS", ""))}
    owner_can_create = cfg.get("CLOUDIF_OWNER_CAN_CREATE", "0").strip() == "1"
    access_dir = cfg.get("CLOUDIF_TENANT_ACCESS_DIR", "/var/lib/cloudif/tenant-access")

    is_admin = username in admin_users or bool(groups_norm.intersection(admin_groups))
    is_owner = username == tenant

    if args.mode == "access":
        allow_users, allow_groups = load_access_dir(tenant, access_dir)
        if is_admin:
            print("ALLOW admin")
            return 0
        if is_owner:
            print("ALLOW owner")
            return 0
        if username in allow_users:
            print("ALLOW tenant-user-allowlist")
            return 0
        if groups_norm.intersection(allow_groups):
            print("ALLOW tenant-group-allowlist")
            return 0
        print("DENY no-access")
        return 1

    if args.mode == "create":
        if is_admin:
            print("ALLOW admin-create")
            return 0
        if groups_norm.intersection(create_groups):
            print("ALLOW create-group")
            return 0
        if owner_can_create and is_owner:
            print("ALLOW owner-create")
            return 0
        print("DENY no-create-permission")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
