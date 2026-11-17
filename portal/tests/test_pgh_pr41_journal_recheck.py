"""Offline PR41 boundary regression: no production or network access."""
import importlib.util
import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

SRC=pathlib.Path(__file__).resolve().parents[2]/'components/runtime/current-apps/komodo-agent-current/cloudif_publication_recovery_journal.py'
spec=importlib.util.spec_from_file_location('journal_pr41',SRC)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class JournalRecheckTests(unittest.TestCase):
    def test_regular_private_journal_initializes(self):
        with tempfile.TemporaryDirectory() as d:
            with mod.PublicationRecoveryJournal(pathlib.Path(d)/'journal.db') as journal:
                self.assertIsNotNone(journal.con.execute('select 1').fetchone())

    def test_inode_swap_before_sqlite_open_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            db=pathlib.Path(d)/'journal.db'
            replacement=pathlib.Path(d)/'replacement.db'
            replacement.touch(mode=0o600)
            connect=sqlite3.connect
            def swap_then_connect(path,**kw):
                if pathlib.Path(path)==db:
                    os.replace(replacement,db)
                return connect(path,**kw)
            with mock.patch.object(mod.sqlite3,'connect',side_effect=swap_then_connect):
                with self.assertRaisesRegex(PermissionError,'journal_db_changed_after_validation'):
                    mod.PublicationRecoveryJournal(db)
            with connect(db) as c:
                row=c.execute("select name from sqlite_master where name='stage_publication_operation_journal'").fetchone()
            self.assertIsNone(row,'no journal schema may be written into substituted inode')

    def test_ancestor_symlink_rejected_before_sqlite_open(self):
        with tempfile.TemporaryDirectory() as d:
            base=pathlib.Path(d)
            real=base/'real';real.mkdir(mode=0o700)
            state=real/'state';state.mkdir(mode=0o700)
            alias=base/'alias';alias.symlink_to(real,target_is_directory=True)
            with mock.patch.object(mod.sqlite3,'connect',side_effect=AssertionError('must_not_open')):
                with self.assertRaisesRegex(PermissionError,'journal_ancestor_symlink_forbidden'):
                    mod.PublicationRecoveryJournal(alias/'state'/'journal.db')
            self.assertFalse((state/'journal.db').exists())

    def test_symlink_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'target.db';target.touch(mode=0o600)
            link=pathlib.Path(d)/'journal.db';link.symlink_to(target)
            with self.assertRaises(OSError):mod.PublicationRecoveryJournal(link)

if __name__=='__main__':unittest.main()
