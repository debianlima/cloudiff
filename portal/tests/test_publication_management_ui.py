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



    def test_information_keeps_only_nonduplicated_project_facts(self):
        markup=ui.publication_panel('demo','Django')
        for duplicate in ('Configuração do PHP','Runtime do Node.js','Preview do site','Terminal do ambiente','Serviço web'):
            self.assertNotIn(duplicate,markup)
        self.assertIn('<span>Versões</span>',markup)
        self.assertIn('Banco vinculado',markup);self.assertIn('demo-db',markup)
        self.assertIn('publication-database-link',markup)
        self.assertIn('https://demo-db.cloudiff.duckdns.org/project/default',markup)
        self.assertIn('Abrir Studio do banco',markup)
        self.assertIn('https://demo-db.cloudiff.duckdns.org/project/default',markup)
        self.assertIn('target="_blank"',markup)
        self.assertIn('Segurança',markup);self.assertIn('HTTPS ativo',markup)
        self.assertIn('Repositório Forge',markup);self.assertIn('https://forge.example/cloudif/demo',markup)

    def test_publication_summary_stays_in_dedicated_module(self):
        root=Path(__file__).resolve().parents[2]
        publication_module=root/'portal/core/publication_summary.py'
        fragments_module=root/'portal/core/html_fragments.py'
        ownership_module=root/'portal/core/resource_ownership.py'
        legacy=(root/'portal/core/legacy_shell.py').read_text()
        manifest=(root/'manifesto.yaml').read_text()
        self.assertTrue(publication_module.is_file())
        self.assertTrue(fragments_module.is_file())
        self.assertTrue(ownership_module.is_file())
        self.assertIn(
            'from portal.core.publication_summary import clean_general_publication_body, individual_publication_body',
            legacy,
        )
        self.assertIn('from portal.core.html_fragments import article_spans as _card_spans',legacy)
        self.assertIn('from portal.core.resource_ownership import load_resource_ownership',legacy)
        self.assertNotIn('publication-summary-card',legacy)
        self.assertEqual(
            legacy.count('from portal.core.publication_summary import clean_general_publication_body, individual_publication_body'),
            1,
        )
        for path in (
            'portal/core/publication_summary.py',
            'portal/core/html_fragments.py',
            'portal/core/resource_ownership.py',
        ):
            self.assertIn(f'caminho: {path}',manifest)

    def test_general_publication_page_is_summary_before_management(self):
        from portal.core.legacy_shell import clean_general_publication_body
        body=(
            '<section><div class="page-hero">Meus Projetos Publicação</div>'
            '<article class="publication-project card"><div class="publication-head"><h2>Demo</h2><code>demo</code></div>'
            '<div class="publication-grid">Preview Produção</div><div class="publication-flow">Detecção Plano Build Rollback</div>'
            '<div class="cm-resource publication-manager-resource">'
            '<div class="publication-information">Framework Banco vinculado Segurança Repositório Forge</div>'
            '<div class="publication-alias"><form action="/cloudiff/portal/action/publication"><input name="slug" value="demo"><button>Salvar endereço</button></form></div>'
            '<div class="publication-active-card"><div><span>Site publicado</span><a href="https://demo.cloudiff.duckdns.org/">demo.cloudiff.duckdns.org</a></div><span class="pill ok">d4 ativa</span></div>'
            '<div class="publication-versions"><button>Ativar esta versão</button></div>'
            '</div></article></section>'
        )
        out=clean_general_publication_body(body)
        self.assertIn('publication-summary-card',out)
        self.assertIn('Demo',out)
        self.assertIn('demo.cloudiff.duckdns.org',out)
        self.assertIn('d4 ativa',out)
        self.assertIn('Gerenciar publicação',out)
        self.assertIn('tab=publicacao&amp;project=demo',out)
        self.assertNotIn('/action/publication',out)
        self.assertNotIn('Salvar endereço',out)
        self.assertNotIn('Ativar esta versão',out)
        self.assertNotIn('Framework Banco vinculado Segurança Repositório Forge',out)
        self.assertNotIn('Preview Produção',out)
        self.assertNotIn('Detecção Plano Build Rollback',out)



    def test_publication_landing_and_manager_have_distinct_page_context(self):
        from unittest.mock import patch
        from portal.core.auth import Identity
        from portal.core.legacy_shell import transform
        identity=Identity('alice','alice@example.invalid',frozenset({'CloudIF-Tenants-Admin'}))
        markup=(
            '<html><head><title>Publicação</title></head><body><main id="conteudo-principal">'
            '<section class="publication-shell"><article class="publication-project card">'
            '<div class="publication-head"><h2>Demo</h2><code>demo</code></div>'
            '<div class="cm-resource"><form><input name="slug" value="demo"></form></div>'
            '</article></section></main></body></html>'
        )
        with patch('portal.core.legacy_shell._resource_ownership',return_value=({'demo':'alice'},{})):
            landing=transform(markup,identity,'publicacao')
            manager=transform(markup,identity,'publicacao',selected_project='demo')
        self.assertIn('<h1 class="page-title">Publicações</h1>',landing)
        self.assertIn('Escolha uma publicação para consultar o resumo ou abrir o gerenciamento.',landing)
        self.assertIn('<h1 class="page-title">Publicação</h1>',manager)
        self.assertIn('Versões publicadas, endereço ativo e ativação do site.',manager)

    def test_publication_landing_logic_is_kept_in_dedicated_modules(self):
        root=Path(__file__).resolve().parents[2]
        legacy=(root/'portal/core/legacy_shell.py').read_text()
        summary=(root/'portal/core/publication_summary.py').read_text()
        ownership=(root/'portal/core/resource_ownership.py').read_text()
        fragments=(root/'portal/core/html_fragments.py').read_text()
        self.assertIn('from portal.core.publication_summary import clean_general_publication_body, individual_publication_body',legacy)
        self.assertNotIn('def clean_general_publication_body(',legacy)
        self.assertNotIn('def individual_publication_body(',legacy)
        self.assertIn('def clean_general_publication_body(',summary)
        self.assertIn('def individual_publication_body(',summary)
        self.assertIn('def load_resource_ownership(',ownership)
        self.assertIn('def article_spans(',fragments)
        self.assertIn('def balanced_element_by_class(',fragments)

    def test_publication_css_module_is_exposed_by_v2_asset_allowlist(self):
        root=Path(__file__).resolve().parents[2]
        coexist=(root/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        shell=(root/'portal/ui/shell.py').read_text()
        self.assertIn('"publications.css"',coexist)
        self.assertIn('/cloudiff/portal/assets/publications.css',shell)
        self.assertIn('if active_tab == "publicacao"',shell)
        self.assertIn('caminho: portal/design/publications.css',(root/'manifesto.yaml').read_text())

    def test_unlinked_database_remains_plain_text(self):
        context={'framework':'Django','database':'Nenhum banco vinculado','security':'Aguardando publicação','repo_url':''}
        markup=ui._project_information(context)
        self.assertIn('Nenhum banco vinculado',markup)
        self.assertNotIn('.cloudiff.duckdns.org/project/default',markup)


if __name__=='__main__':unittest.main()
