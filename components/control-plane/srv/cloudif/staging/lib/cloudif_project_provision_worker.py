#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOG = Path("/var/log/cloudif/project-provision.log")

def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + " " + str(msg) + "\n")

def run(cmd, timeout=180):
    log("RUN " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        log(f"RC={p.returncode}")
        if p.stdout:
            log("STDOUT " + p.stdout[-4000:])
        if p.stderr:
            log("STDERR " + p.stderr[-4000:])
        return p.returncode
    except subprocess.TimeoutExpired:
        log("TIMEOUT " + " ".join(cmd))
        return 124
    except Exception as e:
        log("ERROR " + repr(e))
        return 999

def main():
    job_file = Path(sys.argv[1])
    job = json.loads(job_file.read_text(encoding="utf-8"))
    log(f"START job={job_file} slug={job.get('slug')} tenant={job.get('tenant')}")

    candidates = [
        "/usr/local/sbin/cloudif-project-provision.sh",
        "/usr/local/sbin/cloudif-provision-project.sh",
        "/root/cloudif-project-provision.sh",
        "/root/cloudif-provision-project.sh",
    ]

    found = [c for c in candidates if Path(c).exists() and os.access(c, os.X_OK)]

    if not found:
        log("NO_EXTERNAL_PROVISION_SCRIPT_FOUND metadata_saved_only")
        log("DONE")
        return

    # Executa apenas o primeiro script real encontrado, com timeout, passando o JSON do job.
    rc = run([found[0], str(job_file)], timeout=240)
    if rc == 0 and job.get("template_kind") in ["onboarding", "links"]:
        trc = run(["/usr/local/sbin/cloudif-project-template-apply.py", str(job_file)], timeout=420)
        log(f"TEMPLATE_RC={trc}")
        if trc == 0:
            prc = run(["/usr/local/sbin/cloudif-project-initial-publish.py", str(job_file)], timeout=900)
            log(f"INITIAL_PUBLISH_RC={prc}")
    log("DONE")

if __name__ == "__main__":
    main()
