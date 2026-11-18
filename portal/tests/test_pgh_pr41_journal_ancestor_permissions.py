"""Offline ancestor-path trust regression, no network, Docker, or production."""
import importlib.util
import os
import pathlib
import stat
import tempfile
import unittest
from unittest import mock

SOURCE = (pathlib.Path(__file__).resolve().parents[2] /
    'components/runtime/current-apps/komodo-agent-current/cloudif_publication_recovery_journal.py')
spec = importlib.util.spec_from_file_location('journal_ancestor_permissions', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class AncestorPermissionsTests(unittest.TestCase):
    def test_world_writable_ancestor_rejected_before_sqlite(self):
        with tempfile.TemporaryDirectory() as temp:
            unsafe = pathlib.Path(temp) / 'unsafe'
            unsafe.mkdir()
            private = unsafe / 'private'; private.mkdir(mode=0o700)
            unsafe.chmod(0o777)
            try:
                with mock.patch.object(mod.sqlite3,'connect',side_effect=AssertionError('SQL opened')):
                    with self.assertRaisesRegex(PermissionError, 'journal_ancestor_writable_by_others'):
                        mod.PublicationRecoveryJournal(private / 'journal.sqlite')
                self.assertFalse((private / 'journal.sqlite').exists())
            finally:
                unsafe.chmod(0o700)

    def test_group_writable_ancestor_rejected_before_sqlite(self):
        with tempfile.TemporaryDirectory() as temp:
            unsafe = pathlib.Path(temp) / 'unsafe'
            unsafe.mkdir()
            private = unsafe / 'private'; private.mkdir(mode=0o700)
            unsafe.chmod(0o770)
            try:
                with mock.patch.object(mod.sqlite3,'connect',side_effect=AssertionError('SQL opened')):
                    with self.assertRaisesRegex(PermissionError, 'journal_ancestor_writable_by_others'):
                        mod.PublicationRecoveryJournal(private / 'journal.sqlite')
                self.assertFalse((private / 'journal.sqlite').exists())
            finally:
                unsafe.chmod(0o700)

    def test_non_root_sticky_writable_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            unsafe = pathlib.Path(temp) / 'unsafe'
            unsafe.mkdir()
            private = unsafe / 'private'; private.mkdir(mode=0o700)
            unsafe.chmod(0o1777)
            try:
                with mock.patch.object(mod.sqlite3,'connect',side_effect=AssertionError('SQL opened')):
                    with self.assertRaisesRegex(PermissionError, 'journal_ancestor_writable_by_others'):
                        mod.PublicationRecoveryJournal(private / 'journal.sqlite')
            finally:
                unsafe.chmod(0o700)

    def test_private_chain_under_root_owned_sticky_tmp_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            with mod.PublicationRecoveryJournal(base / 'journal.sqlite') as obj:
                self.assertEqual(obj.con.execute('select 1').fetchone()[0], 1)
            self.assertTrue((base / 'journal.sqlite').exists())
            self.assertEqual(stat.S_IMODE((base / 'journal.sqlite').stat().st_mode),0o600)

    def test_private_nested_ancestor_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            ancestor = pathlib.Path(temp) / 'a'; ancestor.mkdir(mode=0o700)
            parent = ancestor / 'b'; parent.mkdir(mode=0o700)
            with mod.PublicationRecoveryJournal(parent / 'journal.sqlite') as obj:
                self.assertIsNotNone(obj.con.execute('select 1').fetchone())

if __name__ == '__main__': unittest.main()
