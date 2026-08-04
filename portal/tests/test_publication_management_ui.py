import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portal.legacy import cloudif_portal_publications as publications
from portal.legacy import cloudif_ui_publications as ui
from portal.core.legacy_shell import individual_publication_body


class PublicationManagementUITest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'portal.db'
        con=sqlite3.connect(self.db)
        con.executescript('''
        create table projects(slug text primary key,owner text,created_by text,status text,repo_url text,tenant_default text,tenant text);
        create table project_acl(slug text,subject_type text,subject text);
        insert into projects values('demo','alice','alice','published','https://forge.example/cloudif/demo','demo-db','');
        ''')
        publications._ensure_schema(con)
        con.execute("insert into project_publications(project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,version_hostname,status,is_active,created_by,created_at,published_at) values('demo',1001,1,'d1','abc','1001.cloudiff.duckdns.org','1001-d1.cloudiff.duckdns.org','published',1,'alice','now','now')")
        con.execute("insert into project_publication_aliases values('lima','demo','alice','now','now')")
        con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at) values('demo','alice','succeeded','completed','Site publicado e ativado.','now')")
        con.commit();con.close()
        self.old_pub=publications.DB;self.old_ui=ui.DB;publications.DB=self.db;ui.DB=self.db
    def tearDown(self):
        publications.DB=self.old_pub;ui.DB=self.old_ui;self.tmp.cleanup()
    def test_saved_alias_is_read_only_until_edit(self):
        markup=ui.publication_panel('demo')
        self.assertIn('lima.cloudiff.duckdns.org',markup)
        self.assertIn('Editar endereço',markup)
        self.assertIn('publication-alias-form" hidden',markup)
        self.assertIn('Site publicado',markup)
    def test_acknowledged_job_disappears(self):
        user={'username':'alice','groups':[],'admin':False}
        job=publications.latest_job('demo');self.assertIsNotNone(job)
        publications.acknowledge_job('demo',job['id'],user)
        self.assertIsNone(publications.latest_job('demo'))
    def test_individual_view_removes_legacy_pipeline(self):
        body='<article class="publication-project card"><div class="publication-head"><h2>Demo</h2></div><div class="publication-grid">Sem build</div><div class="publication-flow">Detecção Plano Build</div><div class="cm-resource"><form><input name="slug" value="demo"></form><p>Funcional</p></div></article>'
        out=individual_publication_body(body,'demo')
        self.assertIn('Funcional',out);self.assertIn('Gerenciar site',out)
        self.assertNotIn('Sem build',out);self.assertNotIn('Detecção Plano Build',out)


    def test_old_unacknowledged_jobs_do_not_resurface(self):
        user={'username':'alice','groups':[],'admin':False}
        current=publications.latest_job('demo')
        publications.acknowledge_job('demo',current['id'],user)
        con=sqlite3.connect(self.db)
        con.execute("insert into publication_jobs(project_slug,actor,status,step,message,created_at) values('demo','alice','failed','failed','Erro antigo','before')")
        old_id=con.execute('select last_insert_rowid()').fetchone()[0]
        con.execute("update publication_jobs set id=? where id=?",(current['id']-1,old_id))
        con.commit();con.close()
        self.assertIsNone(publications.latest_job('demo'))



    def test_information_uses_real_project_links(self):
        markup=ui.publication_panel('demo','Django')
        self.assertIn('Informações do PHP',markup);self.assertIn('Informações do Node.js',markup)
        self.assertIn('Banco vinculado',markup);self.assertIn('demo-db',markup)
        self.assertIn('publication-database-link',markup)
        self.assertIn('https://demo-db.cloudiff.duckdns.org/project/default',markup)
        self.assertIn('Abrir Studio do banco',markup)
        self.assertIn('https://demo-db.cloudiff.duckdns.org/project/default',markup)
        self.assertIn('target="_blank"',markup)
        self.assertIn('Segurança',markup);self.assertIn('HTTPS ativo',markup)
        self.assertIn('Repositório Forge',markup);self.assertIn('https://forge.example/cloudif/demo',markup)

    def test_general_cleaner_matches_individual_structure(self):
        from portal.core.legacy_shell import clean_general_publication_body
        body='<section><div class="page-hero">Meus Projetos Publicação</div><article class="publication-project card"><div class="publication-head"><h2>Demo</h2><code>demo</code></div><div class="publication-grid">Preview Produção</div><div class="publication-flow">Detecção Plano Build Rollback</div><div class="cm-resource"><div class="publication-information">Framework Banco vinculado Segurança Repositório Forge</div></div></article></section>'
        out=clean_general_publication_body(body)
        self.assertIn('publication-manager',out)
        self.assertIn('Framework Banco vinculado Segurança Repositório Forge',out)
        self.assertNotIn('Meus Projetos Publicação',out)
        self.assertNotIn('Preview Produção',out)
        self.assertNotIn('Detecção Plano Build Rollback',out)



    def test_unlinked_database_remains_plain_text(self):
        context={'framework':'Django','database':'Nenhum banco vinculado','security':'Aguardando publicação','repo_url':''}
        markup=ui._project_information(context)
        self.assertIn('Nenhum banco vinculado',markup)
        self.assertNotIn('.cloudiff.duckdns.org/project/default',markup)


if __name__=='__main__':unittest.main()
