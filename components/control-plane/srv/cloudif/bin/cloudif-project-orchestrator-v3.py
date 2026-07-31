#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

BASE = Path("/srv/cloudif")
PROJECT_DIR = Path("/var/lib/cloudif/projects")
PROJECT_ACCESS = Path("/var/lib/cloudif/project-access")
APP_LOG = Path("/var/log/cloudif/projects")
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_ACCESS.mkdir(parents=True, exist_ok=True)
APP_LOG.mkdir(parents=True, exist_ok=True)


def canonical_repo_name(slug):
    slug = re.sub(r"[^a-z0-9]+", "-", str(slug or "").lower()).strip("-")
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def slugify(name):
    s = (name or "").strip().lower()
    repl = {
        "á":"a","à":"a","ã":"a","â":"a","ä":"a",
        "é":"e","è":"e","ê":"e","ë":"e",
        "í":"i","ì":"i","î":"i","ï":"i",
        "ó":"o","ò":"o","õ":"o","ô":"o","ö":"o",
        "ú":"u","ù":"u","û":"u","ü":"u",
        "ç":"c",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"^[._-]+|[._-]+$", "", s)
    return s[:54] or "projeto"

def run(cmd, timeout=None):
    start = time.time()
    try:
        p = subprocess.run(shlex.split(cmd) if isinstance(cmd, str) else cmd, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return {"ok": p.returncode == 0, "returncode": p.returncode, "seconds": round(time.time() - start, 2), "output": p.stdout[-8000:]}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "returncode": 124, "seconds": round(time.time() - start, 2), "output": "TIMEOUT"}

def read_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception:
        return {}

def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

def add_lines(path, values):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = []
    if p.exists():
        old = [x.strip() for x in p.read_text(errors="ignore").splitlines() if x.strip() and not x.strip().startswith("#")]
    seen = {x.lower() for x in old}
    for v in values:
        v = v.strip()
        if v and v.lower() not in seen:
            old.append(v)
            seen.add(v.lower())
    p.write_text("\n".join(old) + ("\n" if old else ""))

def tenant_exists(tenant):
    return (BASE / "tenants" / tenant).is_dir()

def ensure_supabase_tenant(tenant, username):
    if tenant_exists(tenant):
        return {"ok": True, "message": "Tenant já existe."}
    ensure = Path("/usr/local/sbin/cloudif-tenant-ensure-bg.sh")
    if not ensure.exists():
        return {"ok": False, "message": "cloudif-tenant-ensure-bg.sh não encontrado."}
    return run(f"{shlex.quote(str(ensure))} {shlex.quote(tenant)} create {shlex.quote(username)}", timeout=1800)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--allow-user", action="append", default=[])
    ap.add_argument("--allow-group", action="append", default=[])
    ap.add_argument("--skip-supabase", action="store_true")
    ap.add_argument("--skip-forja", action="store_true")
    args = ap.parse_args()

    project_slug = slugify(args.name)
    tenant = slugify(args.tenant)

    if args.tenant == "__new__":
        tenant = project_slug

    project_file = PROJECT_DIR / f"{project_slug}.json"

    project = read_json(project_file)
    if project and project.get("tenant") and project.get("tenant") != tenant:
        # Evita colisão de nomes entre tenants.
        project_slug = f"{tenant}-{project_slug}"[:62]
        project_file = PROJECT_DIR / f"{project_slug}.json"
        project = read_json(project_file)

    project.update({
        "project_slug": project_slug,
        "app_name": args.name,
        "tenant": tenant,
        "requested_by": args.user,
        "owner": args.user,
        "description": args.description,
        "supabase_url": f"https://{tenant}.cloudiff.duckdns.org/project/default",
        "forgejo_expected": f"https://cloudiff.duckdns.org/git/cloudif/{canonical_repo_name(project_slug)}",
        "komodo_url": "https://komodoiff.duckdns.org/",
        "updated_at": now(),
    })

    steps = project.setdefault("steps", [])

    if args.allow_user:
        add_lines(PROJECT_ACCESS / f"{project_slug}.users", args.allow_user)
    if args.allow_group:
        add_lines(PROJECT_ACCESS / f"{project_slug}.groups", args.allow_group)

    # Dono sempre fica liberado.
    add_lines(PROJECT_ACCESS / f"{project_slug}.users", [args.user])

    if not args.skip_supabase:
        res = ensure_supabase_tenant(tenant, args.user)
        project["supabase"] = res
        steps.append({"time": now(), "title": "ensure supabase tenant", "result": res})

    write_json(project_file, project)

    if not args.skip_forja:
        client = BASE / "bin" / "cloudif-forja-client.py"
        if client.exists():
            res = run(f"{shlex.quote(str(client))} project-ensure --file {shlex.quote(str(project_file))}", timeout=180)
            project["forja_client"] = res
            steps.append({"time": now(), "title": "forja project ensure", "result": res})
            try:
                parsed = json.loads(res.get("output", "{}"))
                project["forja_response"] = parsed
                if parsed.get("project"):
                    project.update(parsed["project"])
            except Exception:
                pass
        else:
            project["forja_client"] = {"ok": False, "message": "cloudif-forja-client.py não encontrado."}

    project["status"] = "ok" if project.get("supabase", {}).get("ok", True) else "attention"
    project["finished_at"] = now()
    write_json(project_file, project)

    print(json.dumps({"ok": True, "project": project, "project_file": str(project_file)}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
