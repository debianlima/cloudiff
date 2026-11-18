#!/usr/bin/env python3
"""Fail-closed TLS/SNI and origin transport check. Never accepts application health."""
import argparse
import ipaddress
import json
import re
import socket
import ssl
import sys

ALLOWED = tuple(ipaddress.IPv4Network(x) for x in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8'))


def private_ipv4(raw):
    try:
        ip = ipaddress.IPv4Address(raw)
    except ipaddress.AddressValueError as exc:
        raise ValueError('invalid_private_ipv4') from exc
    if not any(ip in net for net in ALLOWED):
        raise ValueError('address_not_rfc1918_or_loopback')
    return str(ip)


def hostname(project, stage):
    if type(project) is not int or not 1 <= project <= 999999:
        raise ValueError('invalid_project_id')
    if stage not in ('w1', 'd1'):
        raise ValueError('invalid_stage')
    label = f'{project}-w1-preview' if stage == 'w1' else f'{project}-d1'
    return label + '.cloudiff.duckdns.org'


def parse_http_status(status_line):
    if not isinstance(status_line, bytes) or len(status_line) > 160:
        raise ValueError('invalid_http_response')
    match = re.fullmatch(rb'HTTP/1\.[01] ([1-5][0-9]{2})(?: [^\r\n]*)?\r?\n', status_line)
    if not match:
        raise ValueError('invalid_http_response')
    return int(match.group(1))


def http_get_status(ip, port, host, tls, timeout=5):
    # No DNS, proxy, redirects, cookies, credentials, request body or response body.
    address = private_ipv4(ip)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid_port')
    if not re.fullmatch(r'[a-z0-9.-]{1,130}', host) or not host.endswith('.cloudiff.duckdns.org'):
        raise ValueError('invalid_hostname')
    request = (f'GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n'
               'Accept: text/html\r\n\r\n').encode('ascii')
    with socket.create_connection((address, port), timeout=timeout) as raw:
        raw.settimeout(timeout)
        if tls:
            context = ssl.create_default_context()
            with context.wrap_socket(raw, server_hostname=host) as verified:
                verified.sendall(request)
                return parse_http_status(verified.makefile('rb').readline(161))
        raw.sendall(request)
        return parse_http_status(raw.makefile('rb').readline(161))


def classify_http(status):
    if status is None:
        return 'NETWORK_OR_PROTOCOL_FAILURE'
    if status in (401, 403):
        return 'AUTH_OR_ACL_REQUIRED'
    if 200 <= status < 300:
        return 'HTTP_OK_NOT_APPLICATION_PROOF'
    if 300 <= status < 400:
        return 'REDIRECT_NOT_FOLLOWED'
    if status >= 500:
        return 'UPSTREAM_UNAVAILABLE'
    return 'HTTP_NOT_ACCEPTED'


def audit(project, stage, npm_ip, gateway_ip=None, npm_port=443, gateway_port=18150, probe=http_get_status):
    name = hostname(project, stage)
    private_ipv4(npm_ip)
    if gateway_ip is not None:
        private_ipv4(gateway_ip)
    if stage == 'w1' and gateway_ip is None:
        raise ValueError('w1_gateway_required')
    results = {'schema': 'cloudiff/tls-origin-audit/1', 'readonly': True,
               'host': name, 'stage': stage, 'application_verified': False}
    try:
        https_status = probe(npm_ip, npm_port, name, True)
        tls_state = 'VERIFIED'
    except ssl.SSLCertVerificationError:
        https_status, tls_state = None, 'CERTIFICATE_INVALID'
    except (OSError, ssl.SSLError, ValueError, TimeoutError):
        https_status, tls_state = None, 'TRANSPORT_ERROR'
    results['tls'] = {'state': tls_state, 'http': https_status,
                      'classification': classify_http(https_status)}
    if stage == 'w1':
        try:
            origin = probe(gateway_ip, gateway_port, name, False)
        except (OSError, ssl.SSLError, ValueError, TimeoutError):
            origin = None
        results['gateway'] = {'http': origin, 'classification': classify_http(origin)}
    else:
        results['gateway'] = {'classification': 'NOT_APPLICABLE'}
    origin_ok = results['gateway']['classification'] == 'HTTP_OK_NOT_APPLICATION_PROOF' if stage == 'w1' else True
    results['transport_ok'] = (tls_state == 'VERIFIED' and
                               classify_http(https_status) == 'HTTP_OK_NOT_APPLICATION_PROOF' and origin_ok)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=int, required=True)
    parser.add_argument('--stage', choices=('w1','d1'), default='w1')
    parser.add_argument('--npm-ip', required=True)
    parser.add_argument('--gateway-ip')
    args = parser.parse_args(argv)
    try:
        data = audit(args.project, args.stage, args.npm_ip, args.gateway_ip)
    except ValueError:
        print(json.dumps({'status': 'REJECTED_INPUT', 'readonly': True}))
        return 3
    print(json.dumps(data, sort_keys=True))
    return 0 if data['transport_ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
