import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'
sys.path.insert(0,str(LIB))


class ProjectSlugWriteAclTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.con=sqlite3.connect(':memory:')
        self.con.row_factory=sqlite3.Row
        self.con.executescript('''
        create table projects(slug text primary key,owner text,created_by text);
        create table project_acl(id integer primary key autoincrement,slug text,subject_type text,subject text);
        insert into projects values('demo','alice','alice');
        insert into projects values('legado',null,'carol');
        insert into project_acl(slug,subject_type,subject) values('demo','user','bob');
        insert into project_acl(slug,subject_type,subject) values('demo','group','CloudIF-Grupo-X');
        ''')
        import cloudif_publication_permissions as permissions
        self.p=permissions

    def user(self,username,groups=(),admin=False):
        return {'username':username,'groups':list(groups),'admin':admin}

    def test_admin_and_professor_allowed(self):
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('root',['CloudIF-Tenants-Admin'])))
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('prof',['CloudIF-Professor'])))
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('root',admin=True)))

    def test_owner_and_creator_allowed(self):
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('alice')))
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('ALICE')))
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'legado',self.user('carol')))

    def test_acl_user_and_group_allowed(self):
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('bob')))
        self.assertTrue(self.p.project_slug_write_allowed(self.con,'demo',self.user('dave',['cloudif-grupo-x'])))

    def test_outsider_and_anonymous_denied(self):
        self.assertFalse(self.p.project_slug_write_allowed(self.con,'demo',self.user('mallory')))
        self.assertFalse(self.p.project_slug_write_allowed(self.con,'demo',self.user('')))
        self.assertFalse(self.p.project_slug_write_allowed(self.con,'demo',None))

    def test_unknown_slug_denied(self):
        self.assertFalse(self.p.project_slug_write_allowed(self.con,'inexistente',self.user('alice')))


if __name__=='__main__':
    unittest.main()
