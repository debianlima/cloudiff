#!/usr/bin/env python3
"""Forja root-only read-only Docker runtime metadata for Paperclip W1.

No secrets, Docker environment, files, logs, credentials or full Docker inspect
are printed. No privilege escalation. Only call from an authorized root session.
"""
from __future__ import annotations
import json
import os
import re
import socket
import subprocess

TARGET = "cloudif-p1025-preview-web"
FILES = {
    "root_index_html": "/var/www/html/index.html",
    "root_index_php": "/var/www/html/index.php",
    "ui_source_index": "/var/www/html/ui/index.html",
    "ui_built_index": "/var/www/html/ui/dist/index.html",
    "paperclip_server_built": "/var/www/html/server/dist-runtime/index.mjs",
    "generic_node_entry": "/var/www/html/api/server.js",
    "workspace_manifest": "/var/www/html/pnpm-workspace.yaml",
}
SAFE_IMAGE = re.compile(r"^[A-Za-z0-9_./:@+-]{1,180}$")
SAFE_MOUNT = re.compile(r"^/(?:etc/komodo/stacks|srv/cloudif)/[A-Za-z0-9_./-]{1,220}$")
SAFE_COMMIT = re.compile(r"^[0-9a-f]{40}$")

def cmd(argv):
    """Return only exact short output; command is deterministic and strict allowlist."""
    if len(argv) < 2 or argv[0] != "docker":
        return None
    if argv[1] == "inspect":
        if (len(argv) != 5 or argv[2] != "--format" or argv[4] != TARGET):
            return None
        if argv[3] not in (
            "{{.Config.Image}}",
            "{{.State.Status}}",
            "{{range .Mounts}}{{if eq .Destination \"/var/www/html\"}}{{.Source}}{{end}}{{end}}",
            "{{index .Config.Labels \"org.cloudiff.project\"}}",
            "{{index .Config.Labels \"org.cloudiff.stage\"}}",
            '{{index .Config.Labels "org.cloudiff.public-number"}}',
            '{{index .Config.Labels "org.cloudiff.stage-number"}}',
            '{{index .Config.Labels "org.cloudiff.source-preview-bridge"}}',
            '{{index .Config.Labels "org.cloudiff.source-commit"}}',
        ):
            return None
    elif argv[1] == "exec":
        if not(len(argv) == 7 and argv[2] == TARGET and argv[3:5] == ["test", "-f"]
               and argv[5] in FILES.values() and argv[6] == "--end-probe"):
            return None
        argv = argv[:6]
    else:
        return None
    try:
        p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if argv[1] == "exec":
        return p.returncode == 0 if p.returncode in (0,1) else None
    return p.stdout.strip()[:250] if p.returncode == 0 and len(p.stdout) < 400 else None

def report():
    o = {"schema": "cloudiff-paperclip-w1-owner-runtime-readonly/1",
         "host": socket.gethostname().split(".")[0], "target": TARGET,
         "credentials_read": False, "runtime_mutated": False,
         "docker_environment_read": False, "secrets_read": False,
         "status": "BLOCKED"}
    if o["host"] != "forja":
        o["status"] = "BLOCKED_WRONG_HOST"; return o
    if os.geteuid() != 0:
        o["status"] = "BLOCKED_REQUIRES_AUTHORIZED_ROOT"; return o
    docker = lambda template: cmd(["docker","inspect","--format",template,TARGET])
    status = docker("{{.State.Status}}")
    image = docker("{{.Config.Image}}")
    source = docker('{{range .Mounts}}{{if eq .Destination "/var/www/html"}}{{.Source}}{{end}}{{end}}')
    project = docker('{{index .Config.Labels "org.cloudiff.project"}}')
    stage = docker('{{index .Config.Labels "org.cloudiff.stage"}}')
    public_number = docker('{{index .Config.Labels "org.cloudiff.public-number"}}')
    stage_number = docker('{{index .Config.Labels "org.cloudiff.stage-number"}}')
    bridge = docker('{{index .Config.Labels "org.cloudiff.source-preview-bridge"}}')
    source_commit = docker('{{index .Config.Labels "org.cloudiff.source-commit"}}')
    if any(x is None for x in (status,image,source,project,stage,public_number,stage_number,bridge,source_commit)):
        o["status"] = "BLOCKED_DOCKER_INSPECT"; return o
    o["container_running"] = status == "running"
    o["project_label_expected"] = project == "paperclip"
    o["preview_label_expected"] = stage == "preview"
    o["public_number_expected"] = public_number == "1025"
    o["stage_number_expected"] = stage_number == "1"
    o["preview_bridge_marker_expected"] = (bridge or "").lower() == "true"
    # No raw label value is emitted: only syntax/availability of the commit.
    o["immutable_source_commit_labeled"] = bool(SAFE_COMMIT.fullmatch(source_commit or ""))
    o["image"] = image if SAFE_IMAGE.fullmatch(image or "") else "IMAGE_NOT_SANITIZED"
    o["mount_source"] = source if SAFE_MOUNT.fullmatch(source or "") else "MOUNT_NOT_SANITIZED"
    o["mount_looks_like_paperclip_checkout"] = source == "/etc/komodo/stacks/cloudif-paperclip"
    if not all(o[k] for k in ("container_running", "project_label_expected",
                                "preview_label_expected", "public_number_expected",
                                "stage_number_expected", "preview_bridge_marker_expected")):
        o["status"] = "BLOCKED_TARGET_IDENTITY"; return o
    files = {}
    for key,path in FILES.items():
        files[key] = cmd(["docker","exec",TARGET,"test","-f",path,"--end-probe"])
    o["files_exist"] = files
    o["status"] = "METADATA_ONLY_NOT_A_RUNTIME_FIX"
    return o

if __name__ == "__main__":
    data = report()
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if data["status"] == "METADATA_ONLY_NOT_A_RUNTIME_FIX" else 2)
