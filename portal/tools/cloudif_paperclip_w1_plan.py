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
    """Route only the isolated preview service, never the private host:3100."""
    return f"""server {{
  listen 80;
  server_name {HOST};
  server_tokens off;
  client_max_body_size 8m;
  location / {{
    proxy_pass http://app:3100;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 120s;
  }}
}}
""".replace("$connection_upgrade", '"upgrade"')


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
                "healthcheck": {"test": ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/api/health"],
                                "interval": "10s", "timeout": "5s", "retries": 12, "start_period": "20s"},
            },
        },
        "volumes": {DATA_VOLUME: {"name": DATA_VOLUME}},
        "networks": {
            "preview-private": {"name": "cloudif-p1025-w1-internal", "internal": True},
            "cloudif-publications": {"external": True},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--native-image-id", required=True)
    parser.add_argument("--nginx-image", required=True)
    args = parser.parse_args()
    try:
        plan = compose_plan(source_commit=args.source_commit, native_image_id=args.native_image_id,
                            nginx_image=args.nginx_image)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
