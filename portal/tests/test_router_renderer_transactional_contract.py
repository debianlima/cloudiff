from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
RENDERER=ROOT/'components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh'

class RouterRendererTransactionalContractTests(unittest.TestCase):
    def test_renderer_has_lock_backup_and_rollback(self):
        src=RENDERER.read_text()
        for marker in (
            'CLOUDIF_ROUTER_RENDER_LOCK',
            'flock -w "$LOCK_TIMEOUT" 9',
            'rollback_router_render()',
            'trap rollback_router_render ERR INT TERM HUP EXIT',
            'ROLLBACK_ARMED=1',
            'cat "$BACKUP" > "$CONF"',
        ):
            self.assertIn(marker,src)

    def test_academic_hook_runs_inside_transaction_before_closure(self):
        src=RENDERER.read_text()
        hook=src.index('academic project access telemetry post-render BEGIN')
        closure=src.index('CloudIF transactional render closure BEGIN')
        self.assertLess(hook,closure)
        self.assertIn('/srv/cloudif/bin/cloudif-apply-router-academic-access-v1.sh',src)

    def test_transaction_closure_revalidates_portal_and_nginx(self):
        src=RENDERER.read_text()
        closure=src.split('# CloudIF transactional render closure BEGIN',1)[1]
        for marker in (
            "'location = /cloudiff/portal-auth {'",
            "'location @cloudif_portal_forbidden_v134 {'",
            "'location ^~ /cloudiff/portal/ {'",
            'docker exec cloudif-tenant-router nginx -t',
            'docker exec cloudif-tenant-router nginx -s reload',
            'ROLLBACK_ARMED=0',
            'trap - ERR INT TERM HUP EXIT',
        ):
            self.assertIn(marker,closure)

if __name__=='__main__':
    unittest.main()
