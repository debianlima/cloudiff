from pathlib import Path
import unittest

SCRIPT = Path('components/control-plane/srv/cloudif/bin/cloudif-create-tenant.real.sh')


class TenantPortAllocatorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text()

    def test_registry_allocation_has_global_lock(self):
        for marker in (
            'REGISTRY_LOCK="$LOCK_ROOT/tenant-registry.lock"',
            'exec 8>"$REGISTRY_LOCK"',
            'flock -x 8',
            'flock -u 8',
        ):
            self.assertIn(marker, self.source)

    def test_allocator_checks_registry_and_live_listeners(self):
        for marker in (
            'port_registered()', 'port_listening()', 'port_unavailable()',
            'ss -H -ltn', 'next_free_port()', 'bundle_available()',
        ):
            self.assertIn(marker, self.source)
        self.assertIn('while port_unavailable "$candidate"', self.source)
        self.assertIn('bundle_available "$KONG" "$KONG_SSL" "$POOL_TX" "$POOL_SESS" "$INBUCKET"', self.source)

    def test_first_dynamic_port_is_not_reused(self):
        self.assertNotIn('max_kong > 8110', self.source)
        self.assertNotIn('max_studio > 30100', self.source)
        self.assertNotIn('max_db > 54400', self.source)
        self.assertIn('KONG=8110', self.source)
        self.assertIn('KONG=$((KONG + 1))', self.source)
        self.assertIn('STUDIO="$(next_free_port 30100)"', self.source)
        self.assertIn('DB="$(next_free_port 54400)"', self.source)

    def test_registry_rejects_duplicate_assignment(self):
        for marker in (
            'tenant_port_assignment_conflict:$TENANT:$port',
            'if [ "$duplicates" -ne 1 ]',
            'tenant_registry_row_missing:$TENANT',
        ):
            self.assertIn(marker, self.source)

    def test_tenant_lookup_uses_exact_csv_field(self):
        self.assertIn('$1==tenant', self.source)
        allocation = self.source[:self.source.index('if [ ! -f "$SRC/docker-compose.yml" ]')]
        self.assertNotIn('grep "^${TENANT},"', allocation)


if __name__ == '__main__':
    unittest.main()
