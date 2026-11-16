"""Fail-closed hard-link tests: only private temporary files are accessed."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

SRC=Path(__file__).resolve().parents[2]/'components/runtime/current-apps/komodo-agent-current'
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from cloudif_publication_recovery_journal import PublicationRecoveryJournal


class JournalHardlinkSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.root.chmod(0o700)
        self.db=self.root/'journal.sqlite'

    def test_existing_hardlinked_database_is_rejected_before_chmod_or_write(self):
        original=self.root/'unrelated-owner-file.txt'
        original.write_text('DO_NOT_MODIFY\n',encoding='utf8')
        original.chmod(0o640)
        os.link(original,self.db)
        self.assertEqual(original.stat().st_nlink,2)
        with self.assertRaisesRegex(PermissionError,'journal_hardlinked_file_forbidden'):
            PublicationRecoveryJournal(self.db)
        self.assertEqual(original.read_text(encoding='utf8'),'DO_NOT_MODIFY\n')
        self.assertEqual(stat.S_IMODE(original.stat().st_mode),0o640)
        self.assertEqual(self.db.stat().st_ino,original.stat().st_ino)

    def test_existing_hardlinked_wal_and_shm_are_rejected(self):
        for suffix in ('-wal','-shm'):
            with self.subTest(suffix=suffix):
                original=self.root/('unrelated'+suffix+'.txt')
                original.write_text('MUST_STAY_PRIVATE\n',encoding='utf8')
                original.chmod(0o640)
                clone=Path(str(self.db)+suffix)
                os.link(original,clone)
                with self.assertRaisesRegex(PermissionError,'journal_hardlinked_file_forbidden'):
                    PublicationRecoveryJournal(self.db)
                self.assertEqual(original.read_text(encoding='utf8'),'MUST_STAY_PRIVATE\n')
                self.assertEqual(stat.S_IMODE(original.stat().st_mode),0o640)
                clone.unlink()
                if self.db.exists():self.db.unlink()

    def test_single_linked_database_remains_usable_after_restart(self):
        with PublicationRecoveryJournal(self.db) as journal:
            op=journal.prepare(project='atlas',kind='production_release',
                public_number=1200,publication_number=1,target='cloudif-p1200-d3-web')
            journal.transition(op,expected_phase='prepared',next_phase='mutating')
        with PublicationRecoveryJournal(self.db) as reopened:
            self.assertEqual(reopened.unresolved()[0]['operation_id'],op)
            self.assertEqual(self.db.stat().st_nlink,1)
            self.assertEqual(stat.S_IMODE(self.db.stat().st_mode),0o600)

    def test_foreign_inode_owner_is_rejected_before_permission_change(self):
        original=os.fstat
        def pretend_foreign(fd):
            st=original(fd)
            class Metadata:
                st_mode=st.st_mode
                st_nlink=st.st_nlink
                st_uid=st.st_uid+123456
            return Metadata()
        with mock.patch('cloudif_publication_recovery_journal.os.fstat',side_effect=pretend_foreign):
            with self.assertRaisesRegex(PermissionError,'journal_file_untrusted_owner'):
                PublicationRecoveryJournal(self.db)
        # No mode escalation and no journal schema creation after refusal.
        self.assertTrue(self.db.exists())
        self.assertEqual(self.db.stat().st_size,0)

if __name__=='__main__':unittest.main()
