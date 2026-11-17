#!/usr/bin/env python3
"""Generate a *candidate* isolated W1 Paperclip stack (no deployment).

Security contract: inputs must be immutable image IDs/digests provided by
verified, authorized build and image-ownership checks; no credentials are read.
The public hostname is served by a NEW preview app, not by the existing private
Paperclip application. Full E2E and backup/rollback gates are still required.
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re

COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
IMAGE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
NGINX_IMAGE_RE = re.compile(r"nginx:1\.27\.5-alpine@sha256:[0-9a-f]{64}\Z")
PROXY_CONFIG_PATH = "/srv/cloudif/paperclip-w1-1025/proxy.conf"
WEB_NAME = "cloudif-p1025-preview-web"
APP_NAME = "cloudif-p1025-preview-app"
DATA_VOLUME = "cloudif-p1025-w1-paperclip-data"
HOST = "1025-w1-preview.cloudiff.duckdns.org"


def validate_commit(value: str) -> str:
    if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
        raise ValueError("immutable_full_source_commit_required")
    return value


def validate_image_id(value: str) -> str:
    if not isinstance(value, str) or not IMAGE_ID_RE.fullmatch(value):
        raise ValueError("verified_immutable_paperclip_image_id_required")
    return value


def validate_nginx_image(value: str) -> str:
    if not isinstance(value, str) or not NGINX_IMAGE_RE.fullmatch(value):
        raise ValueError("verified_immutable_nginx_image_digest_required")
    return value


def nginx_proxy_config() -> str:
    """Route only the isolated Preview; reject unexpected host headers.

    This file is loaded by nginx from conf.d within its http context, so a
    map may precede the server block. Never rely on untrusted forwarded-proto
    supplied by the client to decide authentication or cookie security.
    """
    return f"""map $http_upgrade $cloudiff_w1_connection {{
  default upgrade;
  '' close;
}}
server {{
  listen 80;
  server_name {HOST};
  server_tokens off;
  if ($host != {HOST}) {{ return 421; }}
  client_max_body_size 8m;
  # Docker embedded DNS: app is a service on preview-private, not the host.
  # Variable-based proxy_pass resolves when the app container starts/restarts.
  resolver 127.0.0.11 valid=10s ipv6=off;
  set $cloudiff_preview_upstream app;
  location / {{
    proxy_pass http://$cloudiff_preview_upstream:3100;
    proxy_http_version 1.1;
    proxy_set_header Host {HOST};
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $cloudiff_w1_connection;
    proxy_read_timeout 120s;
  }}
}}
"""


def compose_plan(*, source_commit: str, native_image_id: str, nginx_image: str) -> dict:
    commit = validate_commit(source_commit)
    image = validate_image_id(native_image_id)
    proxy = validate_nginx_image(nginx_image)
    labels = {
        "org.cloudiff.project": "paperclip",
        "org.cloudiff.public-number": "1025",
        "org.cloudiff.stage": "preview",
        "org.cloudiff.stage-number": "1",
        "org.cloudiff.source-preview-bridge": "true",
        "org.cloudiff.source-commit": commit,
    }
    return {
        "name": "cloudif-p1025-preview",
        "services": {
            "app": {
                "image": image,  # local immutable image ID built from exact reviewed commit
                "pull_policy": "never",
                "container_name": APP_NAME,
                "restart": "unless-stopped",
                "environment": {
                    "PAPERCLIP_DEPLOYMENT_MODE": "authenticated",
                    "PAPERCLIP_DEPLOYMENT_EXPOSURE": "private",
                    "PAPERCLIP_HOME": "/paperclip",
                    "PAPERCLIP_INSTANCE_ID": "preview-w1-1025",
                    "PAPERCLIP_CONFIG": "/paperclip/instances/preview-w1-1025/config.json",
                    "HOST": "0.0.0.0",
                    "PORT": "3100",
                },
                "volumes": [{"type": "volume", "source": DATA_VOLUME, "target": "/paperclip"}],
                "networks": ["preview-private"],
                "security_opt": ["no-new-privileges:true"],
                "labels": labels,
                "healthcheck": {"test": ["CMD-SHELL", "curl --fail --silent --show-error http://127.0.0.1:3100/api/health >/dev/null"],
                                "interval": "10s", "timeout": "5s", "retries": 12, "start_period": "45s"},
            },
            "web": {
                "image": proxy,
                "pull_policy": "never",
                "container_name": WEB_NAME,
                "restart": "unless-stopped",
                "depends_on": {"app": {"condition": "service_healthy"}},
                "volumes": [{"type": "bind", "source": PROXY_CONFIG_PATH,
                             "target": "/etc/nginx/conf.d/default.conf", "read_only": True,
                             "bind": {"create_host_path": False}}],
                "read_only": True,
                "tmpfs": ["/tmp", "/var/cache/nginx", "/var/run"],
                "security_opt": ["no-new-privileges:true"],
                "networks": ["preview-private", "cloudif-publications"],
                "labels": labels,
                "healthcheck": {"test": ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ && wget -q -O /dev/null http://127.0.0.1/api/health"],
                                "interval": "10s", "timeout": "5s", "retries": 12, "start_period": "20s"},
            },
        },
        "volumes": {DATA_VOLUME: {"name": DATA_VOLUME}},
        "networks": {
            "preview-private": {"name": "cloudif-p1025-w1-internal", "internal": True},
            "cloudif-publications": {"external": True},
        },
    }


def write_candidate(output_dir: str, plan: dict, proxy_config: str) -> tuple[str, str]:
    """Materialize files only inside current working tree, refusing overwrite.

    This deliberately does not touch /etc/komodo, /srv/cloudif or Docker.
    Runtime deployment always requires separately approved G0-G5 gates.
    """
    root = pathlib.Path.cwd().resolve(strict=True)
    path = pathlib.Path(output_dir)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.parts[0] == ".":
        raise ValueError("candidate_output_must_be_relative_subdirectory")
    output = root / path
    for parent in (root, *(root.joinpath(*path.parts[:i]) for i in range(1, len(path.parts)))):
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("candidate_output_parent_must_exist_and_not_be_symlink")
    if output.is_symlink():
        raise ValueError("candidate_output_parent_must_exist_and_not_be_symlink")
    if output.exists():
        raise ValueError("candidate_output_already_exists")
    try:
        output.mkdir(mode=0o700)
        for name, content in (
            ("compose.json", json.dumps(plan, sort_keys=True, indent=2) + "\n"),
            ("proxy.conf", proxy_config),
        ):
            file = output / name
            with file.open("x", encoding="utf-8") as stream:
                stream.write(content)
            file.chmod(0o600)
    except BaseException:
        for name in ("compose.json", "proxy.conf"):
            (output / name).unlink(missing_ok=True)
        output.rmdir()
        raise
    return str(output / "compose.json"), str(output / "proxy.conf")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--native-image-id", required=True)
    parser.add_argument("--nginx-image", required=True)
    parser.add_argument("--output-dir", help="Create a new local directory with compose.json and proxy.conf")
    args = parser.parse_args()
    try:
        plan = compose_plan(source_commit=args.source_commit, native_image_id=args.native_image_id,
                            nginx_image=args.nginx_image)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output_dir:
        try:
            output_files = write_candidate(args.output_dir, plan, nginx_proxy_config())
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps({"offline_candidate_files": output_files, "deployed": False}))
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
