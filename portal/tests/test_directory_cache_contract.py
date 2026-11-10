import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_directory_cache.py'

spec=importlib.util.spec_from_file_location('cloudif_directory_cache_test',MODULE)
cache=importlib.util.module_from_spec(spec); spec.loader.exec_module(cache)

class DirectoryCacheContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=os.environ.get('CLOUDIF_DIRECTORY_CACHE_DB')
        os.environ['CLOUDIF_DIRECTORY_CACHE_DB']=str(Path(self.tmp.name)/'directory-cache.db')
    def tearDown(self):
        if self.old is None: os.environ.pop('CLOUDIF_DIRECTORY_CACHE_DB',None)
        else: os.environ['CLOUDIF_DIRECTORY_CACHE_DB']=self.old
        self.tmp.cleanup()

    def _seed(self):
        users=[
          {'username':'iff20222920038','uuid':'u-pedro','name':'Pedro Henrique Miranda de Oliveira','email':'pedro@example.invalid','is_active':True,'is_superuser':False,'groups_obj':[]},
          {'username':'iff3546365','uuid':'u-admin','name':'Administrador Teste','email':'admin@example.invalid','is_active':True,'is_superuser':False,'groups_obj':[{'name':'CloudIF-Tenants-Admin'},{'name':'CloudIF-Professor'}]},
        ]
        groups=[{'pk':'g-admin','name':'CloudIF-Tenants-Admin'},{'pk':'g-prof','name':'CloudIF-Professor'}]
        return cache._replace_snapshot(users,groups,123)

    def test_snapshot_is_separate_derived_cache(self):
        st=self._seed()
        self.assertTrue(st['ready']); self.assertEqual(st['users'],2); self.assertEqual(st['groups'],2)
        self.assertTrue(Path(os.environ['CLOUDIF_DIRECTORY_CACHE_DB']).is_file())
        source=MODULE.read_text().lower()
        for sql in ('from project_acl','insert into project_acl','update project_acl','delete from project_acl','from tenant_acl','insert into tenant_acl'):
            self.assertNotIn(sql,source)

    def test_empty_query_lists_users_with_pagination(self):
        self._seed()
        first=cache.search('',kind='user',page=1,page_size=1)
        second=cache.search('',kind='user',page=2,page_size=1)
        self.assertEqual(first['total'],2); self.assertEqual(first['pages'],2)
        self.assertEqual(len(first['items']),1); self.assertEqual(len(second['items']),1)
        self.assertNotEqual(first['items'][0]['principal'],second['items'][0]['principal'])

    def test_name_and_username_search_are_submillisecond_style_local_queries(self):
        self._seed()
        by_name=cache.search('Pedro Henrique',kind='all')
        by_login=cache.search('iff20222920038',kind='user')
        self.assertEqual(by_name['items'][0]['principal'],'iff20222920038')
        self.assertEqual(by_login['items'][0]['full_name'],'Pedro Henrique Miranda de Oliveira')

    def test_only_admin_group_marks_user_as_admin(self):
        self._seed()
        admin=cache.search('iff3546365',kind='user')['items'][0]
        pedro=cache.search('iff20222920038',kind='user')['items'][0]
        self.assertTrue(admin['is_admin']); self.assertFalse(pedro['is_admin'])
        self.assertIn('CloudIF-Professor',admin['groups'])

    def test_group_catalog_is_selectable_without_marking_group_as_admin_user(self):
        self._seed()
        item=cache.search('CloudIF-Tenants-Admin',kind='group')['items'][0]
        self.assertEqual(item['type'],'group'); self.assertFalse(item['is_admin'])

if __name__=='__main__': unittest.main()
