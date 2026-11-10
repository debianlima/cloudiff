from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SRC=(ROOT/'components/control-plane/srv/cloudif/bin/cloudif-apply-router-portal-v1.sh').read_text()

class RouterPortalApplyRollbackContractTests(unittest.TestCase):
    def test_apply_has_backup_and_automatic_rollback(self):
        self.assertIn('BACKUP="$BKDIR/default.conf.bkp-$NOW"',SRC)
        self.assertIn('rollback_portal_router()',SRC)
        self.assertIn('trap rollback_portal_router ERR INT TERM HUP',SRC)
        self.assertIn('cp -a "$BACKUP" "$CONF"',SRC)
        self.assertIn('docker exec "$ROUTER" nginx -t',SRC)
        self.assertIn('trap - ERR INT TERM HUP',SRC)

    def test_uid_propagation_survives_apply(self):
        self.assertIn('auth_request_set $authentik_uid $upstream_http_x_authentik_uid;',SRC)
        self.assertIn('proxy_set_header X-authentik-uid $authentik_uid;',SRC)

if __name__=='__main__': unittest.main()
