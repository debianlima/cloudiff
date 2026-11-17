"""No-network regressions for the W1 gateway upstream audit."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[2] / 'scripts' / 'audit-w1-gateway-upstreams-readonly.py'
spec = importlib.util.spec_from_file_location('w1_audit', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GatewayReadOnlyAudit(unittest.TestCase):
    def test_explicit_project_ids_and_private_gateway_only(self):
        self.assertEqual(mod.validate_numbers('1001,1021,1025'), ['1001', '1021', '1025'])
        self.assertEqual(mod.validate_gateway_ip('10.62.91.2'), '10.62.91.2')
        for bad in ('', '1001,1001', 'abc', '1001,anything'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mod.validate_numbers(bad)
        for bad in ('example.org', '8.8.8.8', '0.0.0.0', '169.254.1.3'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mod.validate_gateway_ip(bad)

    def test_docker_inventory_has_only_nonsecret_metadata(self):
        fake = mock.Mock(returncode=0, stdout='cloudif-p1025-w1-preview-web\tUp 3 days (healthy)\n')
        with mock.patch.object(mod.subprocess, 'run', return_value=fake) as runner:
            result = mod.docker_containers()
        self.assertEqual(result, {'cloudif-p1025-w1-preview-web': 'Up 3 days (healthy)'})
        args = runner.call_args.args[0]
        self.assertEqual(args[:3], ['docker', 'ps', '--all'])
        self.assertNotIn('inspect', args)

    def test_reject_unexpected_inventory_and_double_name(self):
        for bad in ('badline', 'x\tUp\nx\tExited', 'bad name\tUp'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mod.parse_containers(bad)

    def test_gateway_health_is_not_application_health(self):
        statuses = {'/__cloudif_health': 200, '/': 502}
        with mock.patch.object(mod, 'http_status', side_effect=lambda h,p,n,path,t: statuses[path]):
            result = mod.audit('10.62.91.2', 18150, ['1021'], {}, 3.0)
        self.assertEqual(result['gateway_self_health_status'], 200)
        self.assertFalse(result['self_health_proves_upstreams'])
        self.assertEqual(result['checks'][0]['classification'], 'missing_expected_container')

    def test_classifications_deny_false_success(self):
        cases = [
            (None, 502, 'missing_expected_container'),
            ('Restarting (1)', 502, 'container_restarting'),
            ('Exited (1)', 502, 'container_not_running'),
            ('Up 3d', 502, 'upstream_unavailable'),
            ('Up 3d', 200, 'http_reachable_app_not_verified'),
            ('Up 3d', 403, 'upstream_reachable_auth_or_forbidden_not_app_verified'),
            ('Up 3d', 302, 'redirect_requires_review'),
        ]
        for state,code,expected in cases:
            with self.subTest(state=state, code=code):
                self.assertEqual(mod.classify(state,code),expected)

    def test_no_mutating_docker_operations(self):
        content = SOURCE.read_text()
        for forbidden in ('docker compose up', 'docker run', 'docker exec',
                          'docker restart', 'docker rm', 'docker stop',
                          'sudo ', 'chmod 777'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == '__main__':
    unittest.main()
