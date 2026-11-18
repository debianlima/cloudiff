#!/usr/bin/env python3
"""Offline SQLite contract and revision monotonicity tests with fictitious data."""
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path

# Research fixtures only: never import these modules from a production worker.
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "tools" / "acl_r3_research"))
from portal_acl_revision import install_disposable_schema,read_canonical_snapshot
from acl_revision_gate import apply_revision,GateError

class PortalRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cloudiff-r3-db-')
        self.path=str(Path(self.temp.name)/'portal.db')
        self.con=sqlite3.connect(self.path)
        self.con.executescript('''
         CREATE TABLE projects(slug TEXT PRIMARY KEY,owner TEXT);
         CREATE TABLE project_acl(id INTEGER PRIMARY KEY,slug TEXT,subject_type TEXT,subject TEXT,
             UNIQUE(slug,subject_type,subject));
        ''')
        install_disposable_schema(self.con)
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def snap(self):return read_canonical_snapshot(self.path,'demo')
    def new(self):
        self.con.execute('INSERT INTO projects(slug,owner) VALUES(?,?)',('demo','synthetic-owner'))
        self.con.commit()
    def test_insert_and_acl_additions_monotonic(self):
        self.new();self.assertEqual(self.snap()['acl_revision'],1)
        self.con.execute('INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','alice-synthetic'))
        self.con.commit();self.assertEqual(self.snap()['acl_revision'],2)
        self.con.execute('INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','group','class-synthetic'))
        self.con.commit();self.assertEqual(self.snap()['acl_revision'],3)
        self.assertEqual(len(self.snap()['acl']),2)
    def test_idempotent_insert_not_bump(self):
        self.new();self.con.execute('INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','member'))
        self.con.commit();a=self.snap()['acl_revision']
        self.con.execute('INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','member'))
        self.con.commit();self.assertEqual(self.snap()['acl_revision'],a)
    def test_delete_member_bumps_revision(self):
        self.new();self.con.execute('INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','member'))
        self.con.commit();before=self.snap()['acl_revision']
        self.con.execute('DELETE FROM project_acl WHERE slug=?',('demo',));self.con.commit()
        self.assertEqual(self.snap()['acl_revision'],before+1);self.assertEqual(self.snap()['acl'],[])
    def test_owner_change_bumps_revision(self):
        self.new();before=self.snap()['acl_revision']
        self.con.execute('UPDATE projects SET owner=? WHERE slug=?',('another-owner','demo'));self.con.commit()
        self.assertEqual(self.snap()['acl_revision'],before+1)
        self.con.execute('UPDATE projects SET owner=? WHERE slug=?',('another-owner','demo'));self.con.commit()
        self.assertEqual(self.snap()['acl_revision'],before+1)
    def test_rollback_does_not_bump_revision(self):
        self.new();before=self.snap()['acl_revision']
        self.con.execute('BEGIN')
        self.con.execute('INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','temporary-member'))
        self.con.rollback();self.assertEqual(self.snap()['acl_revision'],before)
    def test_restart_schema_idempotent(self):
        self.new();before=self.snap()['acl_revision']
        install_disposable_schema(self.con)
        self.con.commit();self.assertEqual(self.snap()['acl_revision'],before)
    def test_legacy_seed_without_acl_mutation(self):
        self.con.execute('INSERT INTO projects(slug,owner) VALUES(?,?)',('legacy','old-owner'))
        self.con.commit()
        before=self.con.execute('SELECT count(*) FROM project_acl').fetchone()[0]
        install_disposable_schema(self.con)
        self.assertEqual(self.con.execute('SELECT count(*) FROM project_acl').fetchone()[0],before)
        self.assertGreaterEqual(self.con.execute('SELECT revision FROM project_acl_revisions WHERE slug=?',('legacy',)).fetchone()[0],1)
    def test_snapshot_and_guard_rejects_prior_revision(self):
        self.new();snap1=self.snap()
        self.con.execute('INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',('demo','user','member'))
        self.con.commit();snap2=self.snap()
        root=Path(self.temp.name)/'state'
        def attach(snap):return dict(snap,stack_ids=['stack'],repo_id='repo',server_id='')
        calls=[]
        def apply(request,previous):calls.append(request['acl_revision']);return {'ok':True,'targets':[]}
        apply_revision(root,attach(snap2),'portal',apply)
        with self.assertRaisesRegex(GateError,'stale_acl_revision'):
            apply_revision(root,attach(snap1),'portal',apply)
        self.assertEqual(calls,[snap2['acl_revision']])
    def test_incomplete_snapshot_missing_revision_fails_closed(self):
        self.new();snap=self.snap();snap.pop('acl_revision')
        with self.assertRaises(GateError):
            apply_revision(Path(self.temp.name)/'state',dict(snap,stack_ids=['stack'],repo_id='repo'),'portal',lambda a,b:{'ok':True,'targets':[]})

if __name__=='__main__':unittest.main()
