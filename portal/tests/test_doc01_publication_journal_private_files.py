"""Independent review: publication-journal files must not inherit permissive umask."""
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif_publication_recovery_journal.py'
spec=importlib.util.spec_from_file_location('doc01_recovery_review', MODULE)
journal=importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


class JournalPrivateFiles(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name)
        self.root.chmod(0o755)  # Demonstrate safety even in a traversable parent.

    def test_new_db_and_wal_are_private_with_permissive_process_umask(self):
        script="""import os,sys,stat
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import cloudif_publication_recovery_journal as j
os.umask(0o022)
path=Path(sys.argv[2])
with j.PublicationRecoveryJournal(path) as x:
    x.prepare(project='safe',kind='production_release',public_number=10,
              publication_number=1,target='cloudif-p10-d3-web')
    wal=Path(str(path)+'-wal')
    assert wal.exists()
    assert stat.S_IMODE(path.stat().st_mode)==0o600,oct(path.stat().st_mode)
    assert stat.S_IMODE(wal.stat().st_mode)==0o600,oct(wal.stat().st_mode)
"""
        result=subprocess.run([sys.executable,'-c',script,str(MODULE.parent),
                               str(self.root/'journal.sqlite')],
                              capture_output=True,text=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stat.S_IMODE((self.root/'journal.sqlite').stat().st_mode),0o600)

    def test_existing_world_readable_db_is_tightened(self):
        path=self.root/'legacy.sqlite'
        path.write_bytes(b'')
        path.chmod(0o644)
        with journal.PublicationRecoveryJournal(path) as j:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertFalse(j.unresolved())

    def test_preexisting_world_readable_wal_shm_are_tightened(self):
        path=self.root/'journal.sqlite'
        with journal.PublicationRecoveryJournal(path) as first:
            first.prepare(project='safe',kind='production_release',
                          public_number=10,publication_number=1,
                          target='cloudif-p10-d3-web')
            files=[Path(str(path)+suffix) for suffix in ('-wal','-shm')]
            self.assertTrue(all(f.exists() for f in files))
            for f in files:
                f.chmod(0o644)
                self.assertEqual(stat.S_IMODE(f.stat().st_mode),0o644)
            with journal.PublicationRecoveryJournal(path) as second:
                self.assertEqual(len(second.unresolved()),1)
                self.assertTrue(all(
                    stat.S_IMODE(f.stat().st_mode)==0o600 for f in files))

    def test_symlink_to_other_file_is_rejected_without_modifying_target(self):
        target=self.root/'target.txt'
        target.write_text('untouched')
        original_mode=stat.S_IMODE(target.stat().st_mode)
        link=self.root/'journal.sqlite'
        link.symlink_to(target)
        with self.assertRaises(OSError):
            journal.PublicationRecoveryJournal(link)
        self.assertEqual(target.read_text(),'untouched')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),original_mode)

    def test_rejects_group_or_world_writable_state_directory(self):
        for mode in (0o775,0o777):
            with self.subTest(mode=oct(mode)):
                self.root.chmod(mode)
                try:
                    with self.assertRaisesRegex(PermissionError,'journal_parent_writable_by_others'):
                        journal.PublicationRecoveryJournal(self.root/'insecure.sqlite')
                    self.assertFalse((self.root/'insecure.sqlite').exists())
                finally:
                    self.root.chmod(0o755)

    def test_rejects_symlinked_immediate_state_directory(self):
        trusted=self.root/'trusted';trusted.mkdir(mode=0o700)
        alias=self.root/'alias';alias.symlink_to(trusted,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'journal_parent_not_directory'):
            journal.PublicationRecoveryJournal(alias/'journal.sqlite')
        self.assertFalse((trusted/'journal.sqlite').exists())

    def test_nonregular_path_is_not_accepted(self):
        folder=self.root/'journal.sqlite'
        folder.mkdir()
        with self.assertRaises((ValueError,OSError)):
            journal.PublicationRecoveryJournal(folder)


if __name__=='__main__':
    unittest.main()
