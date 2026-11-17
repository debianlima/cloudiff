#!/usr/bin/env python3
"""Audit a known CloudIFF W1 gateway and expected upstreams, without mutation.

Never equate the gateway's synthetic /__cloudif_health 200 to project health.
Only private IPv4 gateway addresses and explicit project numbers are accepted.
No credentials, response bodies, Docker exec or deployment actions are used.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

NUM_RE = re.compile(r"[0-9]{4,5}\Z")
STAGES = {"w1": "w1-preview-web"}


def validate_gateway_ip(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError("gateway must be a literal IPv4 address") from exc
    # IPv4Address.is_private also includes some reserved ranges. Restrict
    # contact to explicit RFC1918/loopback blocks rather than reserved networks.
    allowed = tuple(ipaddress.IPv4Network(network) for network in
                    ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"))
    if not any(address in network for network in allowed):
        raise ValueError("gateway must be RFC1918 or loopback IPv4")
    return str(address)


def validate_numbers(value: str) -> list[str]:
    numbers = [part.strip() for part in value.split(",")]
    if (not numbers or len(numbers) > 25 or any(not NUM_RE.fullmatch(n) for n in numbers)
            or len(set(numbers)) != len(numbers)):
        raise ValueError("provide 1 to 25 distinct 4/5-digit public project numbers")
    return numbers


def parse_containers(output: str) -> dict[str, str]:
    result = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", parts[0]):
            raise ValueError("unexpected docker ps output")
        if parts[0] in result:
            raise ValueError("duplicate container name")
        result[parts[0]] = parts[1].strip()[:128]
    return result


def docker_containers() -> dict[str, str]:
    # Docker format extracts only names and statuses, never env or inspect JSON.
    result = subprocess.run(
        ["docker", "ps", "--all", "--format", "{{.Names}}\t{{.Status}}"],
        text=True, capture_output=True, timeout=12, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("docker read-only inventory unavailable")
    return parse_containers(result.stdout)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_status(host: str, port: int, project_number: str, path: str, timeout: float) -> int | None:
    # Explicitly avoid proxy environments and redirects; no response body read.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        headers={"Host": f"{project_number}-w1-preview.cloudiff.duckdns.org"},
        method="GET",
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def classify(container_state: str | None, response_code: int | None) -> str:
    if container_state is None:
        return "missing_expected_container"
    if container_state.lower().startswith("restarting"):
        return "container_restarting"
    if not container_state.startswith("Up "):
        return "container_not_running"
    if response_code in (502, 503, 504) or response_code is None:
        return "upstream_unavailable"
    if response_code in (401, 403):
        return "upstream_reachable_auth_or_forbidden_not_app_verified"
    if response_code is not None and 200 <= response_code < 300:
        return "http_reachable_app_not_verified"
    if response_code is not None and 300 <= response_code < 400:
        return "redirect_requires_review"
    return "http_error_requires_review"


def audit(host: str, port: int, numbers: list[str], containers: dict[str, str], timeout: float) -> dict:
    health = http_status(host, port, numbers[0], "/__cloudif_health", timeout)
    checks = []
    for number in numbers:
        container = f"cloudif-p{number}-w1-preview-web"
        state = containers.get(container)
        status = http_status(host, port, number, "/", timeout)
        checks.append({
            "public_number": number,
            "expected_container": container,
            "container_status": state,
            "gateway_root_http_status": status,
            "classification": classify(state, status),
        })
    return {
        "schema": "cloudiff-w1-readonly-audit/1",
        "gateway_ip": host,
        "gateway_port": port,
        "gateway_self_health_status": health,
        "self_health_proves_upstreams": False,
        "application_e2e_verified": False,
        "release_authorized": False,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-ip", required=True)
    parser.add_argument("--gateway-port", type=int, default=18150)
    parser.add_argument("--public-numbers", required=True,
                        help="Explicit comma-separated list, e.g. 1001,1021")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    try:
        host = validate_gateway_ip(args.gateway_ip)
        numbers = validate_numbers(args.public_numbers)
        if not 1 <= args.gateway_port <= 65535 or not 0.1 <= args.timeout <= 10:
            raise ValueError("invalid port or timeout")
        containers = docker_containers()
        report = audit(host, args.gateway_port, numbers, containers, args.timeout)
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    report["ok"] = all(c["classification"] in (
        "upstream_reachable_auth_or_forbidden_not_app_verified",
        "http_reachable_app_not_verified",
    ) for c in report["checks"])
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
