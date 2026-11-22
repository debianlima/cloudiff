from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'components/control-plane/usr/local/sbin/cloudif-config-backup.sh'

class ConfigBackupIncludesApprovalsTests(unittest.TestCase):
    def test_portal_and_approval_databases_are_sqlite_backed_up_and_checked(self):
        source=SCRIPT.read_text()
        self.assertIn("'/var/lib/cloudif/portal/cloudif-portal.db'",source)
        self.assertIn("'/var/lib/cloudif/approvals/approvals.db'",source)
        self.assertIn("'$DEST/cloudif-portal.db'",source)
        self.assertIn("'$DEST/approvals.db'",source)
        self.assertIn("a.backup(b)",source)
        self.assertIn("pragma quick_check",source)
        self.assertIn("BACKUP_SOURCE_MISSING",source)
        self.assertIn("BACKUP_QUICK_CHECK_FAILED",source)

if __name__=='__main__':unittest.main()
