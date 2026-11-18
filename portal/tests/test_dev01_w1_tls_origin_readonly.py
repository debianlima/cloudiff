"""Synthetic-only transport checks; never calls the network."""
import importlib.util
from pathlib import Path
import ssl
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'scripts' / 'audit-w1-tls-routing-readonly.py'
S = importlib.util.spec_from_file_location('cloudiff_tls_origin_readonly', SOURCE)
MOD = importlib.util.module_from_spec(S)
S.loader.exec_module(MOD)


class AuditTlsOriginTests(unittest.TestCase):
    def test_hostname_is_numeric_and_stage_scoped(self):
        self.assertEqual(MOD.hostname(1002, 'w1'), '1002-w1-preview.cloudiff.duckdns.org')
        self.assertEqual(MOD.hostname(1002, 'd1'), '1002-d1.cloudiff.duckdns.org')
        for bad in (0, -1, 1000000, '1002', True):
            with self.assertRaises(ValueError): MOD.hostname(bad, 'w1')
        with self.assertRaises(ValueError): MOD.hostname(1002, 'production')

    def test_only_private_rfc1918_and_loopback(self):
        for good in ('10.62.91.2', '172.16.0.1', '172.31.255.255', '192.168.1.1', '127.0.0.1'):
            self.assertEqual(MOD.private_ipv4(good), good)
        for bad in ('8.8.8.8', '100.64.0.1', '169.254.169.254', '0.0.0.0', '240.0.0.1', '255.255.255.255', '::1', 'example.org'):
            with self.assertRaises(ValueError): MOD.private_ipv4(bad)

    def test_http_status_only(self):
        self.assertEqual(MOD.parse_http_status(b'HTTP/1.1 502 Bad Gateway\r\n'), 502)
        self.assertEqual(MOD.parse_http_status(b'HTTP/1.0 200 OK\r\n'), 200)
        for bad in (b'HTTP/2 200\n', b'HTTP/1.1 999\n', b'hello\n', b'HTTP/1.1 200 OK\r\nExtra', b'x'*161):
            with self.assertRaises(ValueError): MOD.parse_http_status(bad)

    def test_tls_invalid_blocks_even_when_origin_ok(self):
        def probe(ip, port, host, tls):
            if tls: raise ssl.SSLCertVerificationError('synthetic')
            return 200
        result = MOD.audit(1002, 'w1', '10.62.91.3', '10.62.91.2', probe=probe)
        self.assertEqual(result['tls']['state'], 'CERTIFICATE_INVALID')
        self.assertFalse(result['transport_ok'])
        self.assertFalse(result['application_verified'])

    def test_gateway_502_blocks_when_tls_valid(self):
        result = MOD.audit(1002, 'w1', '10.62.91.3', '10.62.91.2', probe=lambda ip, port, host, tls: 200 if tls else 502)
        self.assertEqual(result['gateway']['classification'], 'UPSTREAM_UNAVAILABLE')
        self.assertFalse(result['transport_ok'])

    def test_http200_is_not_application_proof(self):
        result = MOD.audit(1002, 'w1', '10.62.91.3', '10.62.91.2', probe=lambda *a:200)
        self.assertTrue(result['transport_ok'])
        self.assertFalse(result['application_verified'])

    def test_auth_and_redirect_fail_closed(self):
        for status in (301,302,401,403):
            r = MOD.audit(1002, 'd1', '10.62.91.3', probe=lambda *args: status)
            self.assertFalse(r['transport_ok'])

    def test_gateway_required_for_w1(self):
        with self.assertRaises(ValueError): MOD.audit(1002, 'w1', '10.62.91.3')

    def test_invalid_private_addresses_rejected_before_probe(self):
        with self.assertRaises(ValueError): MOD.audit(1002, 'w1', '8.8.8.8', '10.62.91.2')
        with self.assertRaises(ValueError): MOD.audit(1002, 'w1', '10.62.91.3', '8.8.8.8')

    def test_d1_never_assumes_gateway_route(self):
        calls=[]
        r=MOD.audit(1002,'d1','10.62.91.3',probe=lambda *args:calls.append(args) or 502)
        self.assertEqual(len(calls),1)
        self.assertFalse(r['transport_ok'])
        self.assertEqual(r['gateway']['classification'],'NOT_APPLICABLE')


if __name__=='__main__': unittest.main()
