import importlib.util
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'
MODULE=LIB/'cloudif_project_environments_overview.py'
if str(LIB) not in sys.path:sys.path.insert(0,str(LIB))


def load_module():
    spec=importlib.util.spec_from_file_location('cloudif_project_environments_overview_test',MODULE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class ProjectEnvironmentsOverviewTests(unittest.TestCase):
    def test_aggregates_preview_homologation_and_production_without_secret_values(self):
        module=load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);portal=tmp/'portal.db';preview=tmp/'preview.db'
            con=sqlite3.connect(portal)
            con.executescript('''
              create table project_publications(id integer primary key,project_slug text,public_number integer,deploy_number integer,commit_sha text,stable_hostname text,version_hostname text,status text,is_active integer,published_at text);
              create table project_publication_aliases(alias text,project_slug text);
            ''')
            con.execute("insert into project_publications values(1,'demo',1001,4,'abcdef1234567890','1001.cloudiff.duckdns.org','1001-d4.cloudiff.duckdns.org','published',1,'2026-08-07T10:00:00Z')")
            con.execute("insert into project_publication_aliases values('demo-site','demo')");con.commit();con.close()
            con=sqlite3.connect(preview)
            con.execute('create table previews(id text,project_slug text,build_id text,commit_ref text,plan_digest text,status text,created_at integer,expires_at integer,removed_at integer,url text,result_json text)')
            con.execute("insert into previews values('pv_aaaaaaaaaaaaaaaaaaaaaaaa','demo','build_1','fedcba9876543210','digest','active',10,4102444800,0,'http://internal-preview','{}')");con.commit();con.close()
            module.PORTAL_DB=portal;module.PREVIEW_DB=preview
            module.authorization=lambda slug,user,groups:{'canRead':True,'canWrite':True}
            module.environment_get=lambda slug,op,query,user,groups:(200,{'ok':True,'environmentRevision':7,'configurationRevision':3,'environmentDigest':'d'*64,'valid':True,'missingRequired':[]})
            module.runtime_get=lambda slug,op,query,user,groups:(200,{'ok':True,'states':[{'status':'running','deploymentId':'dep_'+'a'*24,'buildJobId':'build_hom' if query['environment']=='homologation' else 'build_prod','configRevision':7,'environmentDigest':'d'*64,'updatedAt':123}]})
            data=module.overview('demo','owner',[])
        self.assertTrue(data['ok']);self.assertTrue(data['canWrite'])
        self.assertFalse(data['secretValuesIncluded']);self.assertFalse(data['secretReferencesIncluded'])
        by={item['name']:item for item in data['environments']}
        self.assertEqual(set(by),{'preview','homologation','production'})
        self.assertEqual(by['preview']['url'],'/cloudiff/portal/preview/pv_aaaaaaaaaaaaaaaaaaaaaaaa/')
        self.assertEqual(by['preview']['artifact'],'fedcba9876543210')
        self.assertEqual(by['homologation']['status'],'running');self.assertEqual(by['homologation']['artifact'],'build_hom');self.assertEqual(by['homologation']['url'],'')
        self.assertEqual(by['production']['status'],'published');self.assertEqual(by['production']['deployNumber'],4);self.assertEqual(by['production']['url'],'https://demo-site.cloudiff.duckdns.org/')
        self.assertEqual(by['production']['configuration']['revision'],7)
        for item in data['environments']:
            self.assertNotIn('values',item);self.assertNotIn('value',item);self.assertNotIn('secret',item)

    def test_read_access_is_required(self):
        module=load_module();module.authorization=lambda slug,user,groups:{'canRead':False,'canWrite':False}
        code,data=module.handle_get('demo','viewer',[])
        self.assertEqual(code,403);self.assertFalse(data['ok']);self.assertFalse(data['secretValuesIncluded'])


if __name__=='__main__':unittest.main()
