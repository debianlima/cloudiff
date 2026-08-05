#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import time
from pathlib import Path

JOBDIR = Path(os.environ.get("CLOUDIF_PROJECT_JOB_DIR", "/srv/cloudif/jobs"))
LOCK_ROOT = Path(os.environ.get("CLOUDIF_PROJECT_LOCK_ROOT", "/run/cloudif-operation-locks"))
STALE_SECONDS = max(60, int(os.environ.get("CLOUDIF_PROJECT_JOB_STALE_SECONDS", "180")))
WORKER = Path("/srv/cloudif/lib/cloudif_project_provision_worker.py")


def unit_name(job_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(job_id or ""))[:32].strip("-")
    return "cloudif-project-provision-" + (safe or "recovery") + ".service"


def parse_time(value: str, fallback: float) -> float:
    value = str(value or "").strip()
    if not value:
        return fallback
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except ValueError:
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return fallback


def active(unit: str, job_path: Path) -> bool:
    state = subprocess.run(["/bin/systemctl", "is-active", "--quiet", unit], timeout=10)
    if state.returncode == 0:
        return True
    proc = subprocess.run(["/usr/bin/pgrep", "-af", "cloudif_project_provision_worker.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    return proc.returncode == 0 and str(job_path) in proc.stdout


def launch(path: Path, job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    unit = unit_name(job_id)
    lock_path = Path(str(job.get("project_lock") or LOCK_ROOT / ("project-" + str(job.get("slug") or "unknown") + ".lock")))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(mode=0o600, exist_ok=True)
    subprocess.run(["/bin/systemctl", "reset-failed", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    cmd = [
        "/usr/bin/systemd-run", "--quiet", "--collect", f"--unit={unit[:-8]}",
        "--property=Type=exec", "--property=RuntimeMaxSec=4h",
        "--property=NoNewPrivileges=true", "--setenv=PYTHONPATH=/srv/cloudif/lib",
        "/usr/bin/flock", "-x", str(lock_path),
        "/usr/bin/python3", str(WORKER), str(path),
    ]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return {"job": str(path), "unit": unit, "ok": result.returncode == 0, "error": (result.stderr or result.stdout or "")[-500:]}


def main() -> int:
    JOBDIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    results = []
    for path in sorted(JOBDIR.glob("project-provision-*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(job.get("status") or "")
        if status not in {"queued", "running"}:
            continue
        unit = str(job.get("systemd_unit") or unit_name(str(job.get("job_id") or "")))
        if active(unit, path):
            continue
        age = now - parse_time(str(job.get("updated_at") or job.get("created_at") or ""), path.stat().st_mtime)
        if status == "running" and age < STALE_SECONDS:
            continue
        results.append(launch(path, job))
    print(json.dumps({"ok": all(x["ok"] for x in results), "recovered": len(results), "results": results}, ensure_ascii=False, separators=(",", ":")))
    return 0 if all(x["ok"] for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
