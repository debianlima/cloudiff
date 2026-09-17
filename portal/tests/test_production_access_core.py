from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from portal.core import production_access


class ProductionAccessCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.project_db=root/'portal.db';self.access_db=root/'access.db'
        c=sqlite3.connect(self.project_db)
        c.executescript('''
          create table project_publication_aliases(alias text,project_slug text);
          create table project_publications(id integer primary key,project_slug text,public_number integer,stable_hostname text,status text,is_active integer);
          create table project_public_ids(project_slug text,public_number integer);
        ''')
        c.execute('insert into project_publication_aliases values(?,?)',('alpha','alpha'))
        c.execute('insert into project_publications(project_slug,public_number,stable_hostname,status,is_active) values(?,?,?,?,?)',('alpha',1042,'1042.cloudiff.duckdns.org','published',1))
        c.execute('insert into project_public_ids values(?,?)',('alpha',1042));c.commit();c.close()
        c=sqlite3.connect(self.access_db)
        c.execute('create table snapshots(id integer primary key,received_at text,source_host text,window_days integer,hosts_json text)')
        hosts=[
          {'host':'alpha.cloudiff.duckdns.org','requests':100,'public_requests':70,'internal_requests':30,'public_errors':3,'internal_errors':9,'public_unique_visitors':12,'errors':12,'last_seen':'2026-09-17T20:00:00Z'},
          {'host':'1042.cloudiff.duckdns.org','requests':20,'public_requests':5,'internal_requests':15,'public_errors':1,'internal_errors':2,'public_unique_visitors':4,'errors':3,'last_seen':'2026-09-17T21:00:00Z'},
        ]
        c.execute('insert into snapshots values(?,?,?,?,?)',(1,'2026-09-17T21:01:00Z','mauricio',7,json.dumps(hosts)))
        c.commit();c.close()
        self.old_project=production_access.PROJECT_DB;self.old_access=production_access.ACCESS_DB
        production_access.PROJECT_DB=str(self.project_db);production_access.ACCESS_DB=str(self.access_db)

    def tearDown(self):
        production_access.PROJECT_DB=self.old_project;production_access.ACCESS_DB=self.old_access;self.tmp.cleanup()

    def test_maps_alias_and_stable_host_to_project_aggregate(self):
        data=production_access.project_production_access('alpha')
        self.assertTrue(data['ok']);self.assertTrue(data['published']);self.assertTrue(data['instrumented'])
        self.assertEqual(data['primary_host'],'alpha.cloudiff.duckdns.org')
        self.assertEqual(data['hosts'],['alpha.cloudiff.duckdns.org','1042.cloudiff.duckdns.org'])
        self.assertEqual(data['public_requests'],75)
        self.assertEqual(data['internal_requests'],45)
        self.assertEqual(data['public_unique_visitors'],12)
        self.assertEqual(data['errors'],4)
        self.assertEqual(data['last_seen'],'2026-09-17T21:00:00Z')
        self.assertTrue(data['split_available'])

    def test_legacy_snapshot_does_not_mislabel_all_requests_as_public(self):
        c=sqlite3.connect(self.access_db);c.execute('delete from snapshots')
        c.execute('insert into snapshots values(?,?,?,?,?)',(1,'2026-09-17T21:01:00Z','mauricio',7,json.dumps([{'host':'alpha.cloudiff.duckdns.org','requests':99,'unique_visitors':9,'errors':2,'last_seen':'2026-09-17T20:00:00Z'}])));c.commit();c.close()
        data=production_access.project_production_access('alpha')
        self.assertTrue(data['ok']);self.assertFalse(data['split_available'])
        self.assertIsNone(data['public_requests']);self.assertIsNone(data['public_unique_visitors'])

    def test_unmapped_project_is_not_fabricated(self):
        data=production_access.project_production_access('missing')
        self.assertFalse(data['ok']);self.assertFalse(data['published'])


if __name__=='__main__':unittest.main()
