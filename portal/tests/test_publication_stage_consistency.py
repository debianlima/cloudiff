from pathlib import Path
import importlib.util
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
CANONICAL_UI=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_ui_publications.py'
APP_UI=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py'
CANONICAL_BACKEND=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'
APP_BACKEND=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
RELEASE_JS=ROOT/'portal/design/publication-release.js'


def load(path,name,db):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.DB=str(db)
    return module


class PublicationStageConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'portal.db'
        con=sqlite3.connect(self.db)
        con.executescript('''
        create table production_releases(
          id integer primary key,project_slug text,public_number integer,publication_number integer,candidate_number integer,
          deploy_number integer,stage_code text,hostname text,stable_hostname text,artifact_image_id text,status text,is_active integer,
          environment_revision integer,environment_digest text,created_by text,created_at text,published_at text);
        create table publication_candidates(
          project_slug text,candidate_number integer,commit_sha text,runtime_diff_json text);
        create table project_publications(
          id integer primary key,project_slug text,public_number integer,deploy_number integer,version text,commit_sha text,
          stable_hostname text,version_hostname text,status text,is_active integer,created_by text,created_at text,published_at text,
          message text,detail_json text);
        ''')
        # Legacy D1 is the production that existed before the W/H/P flow.
        con.execute("insert into project_publications values(1,'tuleap-laboratorio-de-hardware',1011,1,'d1','legacycommit','1011.cloudiff.duckdns.org','1011-d1.cloudiff.duckdns.org','published',0,'u','t','t','legacy','{}')")
        # D7 is the compatibility row written by the successful P2 release and must not appear twice.
        con.execute("insert into project_publications values(7,'tuleap-laboratorio-de-hardware',1011,7,'P2','0280dbf46d54','1011.cloudiff.duckdns.org','1011-p2-publication.cloudiff.duckdns.org','published',1,'u','t','t','H7 to P2','{\"publicationNumber\":2}')")
        con.execute("insert into publication_candidates values('tuleap-laboratorio-de-hardware',7,'0280dbf46d54eb3bcceb1582e0b2d6fb92cabc96','{}')")
        con.execute("insert into production_releases values(2,'tuleap-laboratorio-de-hardware',1011,2,7,7,'P2','1011-p2-publication.cloudiff.duckdns.org','1011.cloudiff.duckdns.org','sha256:x','published',1,0,'','u','t','t')")
        con.commit();con.close()

    def tearDown(self): self.tmp.cleanup()

    def test_publication_rows_prefer_real_p_and_keep_unmapped_d_as_legacy(self):
        for idx,path in enumerate((CANONICAL_UI,APP_UI)):
            module=load(path,'pub_ui_'+str(idx),self.db)
            rows=module._rows('tuleap-laboratorio-de-hardware')
            self.assertEqual([(r['kind'],r['number']) for r in rows],[('P',2),('D',1)])
            self.assertEqual(rows[0]['version'],'P2')
            self.assertEqual(rows[0]['commit_sha'][:12],'0280dbf46d54')
            self.assertTrue(rows[1]['legacy'])

    def test_legacy_d_is_never_relabeled_as_p(self):
        for path in (CANONICAL_BACKEND,APP_BACKEND):
            source=path.read_text()
            self.assertIn("'stage_code':'D'+str(int(legacy['deploy_number']))",source)
            self.assertIn("'legacy':True",source)
            self.assertNotIn("'stage_code':'P'+str(int(legacy['deploy_number']))",source)

    def test_homologation_environment_prefers_latest_accepted_candidate(self):
        source=BASE.read_text()
        self.assertIn("items.find(x=>['homologated','published'].includes(x.status))",source)
        self.assertNotIn("items.find(x=>x.status==='homologated')",source)
        self.assertNotIn("const item=(release.candidates||[])[0]||null",source)

    def test_environment_overview_prefers_release_flow_status_over_legacy_overview(self):
        source=BASE.read_text()
        self.assertIn("canonicalStatus=ctx.exists?String(ctx.status||''):''",source)
        self.assertIn("status=envStatusLabels[canonicalStatus]||canonicalStatus||envStatusLabels[item.status]",source)
        self.assertIn("/online|publicado|homologado/i",source)

    def test_manager_labels_legacy_production_honestly(self):
        source=RELEASE_JS.read_text()
        self.assertIn("release.legacy ? release.stage_code + ' · legado'",source)
        self.assertIn("active && active.legacy ? 'Produção legada ativa'",source)

    def test_production_embed_uses_versioned_stage_url_but_external_open_uses_stable_url(self):
        base=BASE.read_text()
        for backend in (CANONICAL_BACKEND,APP_BACKEND):
            source=backend.read_text()
            self.assertIn("'url':'https://'+str(legacy['version_hostname'])+'/'",source)
        self.assertIn("embedUrl:publicationSafeSiteUrl(active.url||active.stableUrl||fallback.url||'')",base)
        self.assertIn("url:publicationSafeSiteUrl(active.stableUrl||active.url||fallback.url||'')",base)
        self.assertIn("const embedUrl=ctx.embedUrl||ctx.url",base)
        self.assertIn("iframe src=\"'+envEsc(embedUrl)+'\"",base)
        self.assertIn("href=\"'+envEsc(ctx.url)+'\"",base)

    def test_homologation_terminal_prefers_accepted_candidate_before_waiting_candidate(self):
        for backend in (CANONICAL_BACKEND,APP_BACKEND):
            source=backend.read_text()
            self.assertIn("status in ('awaiting_homologation','homologated','published')",source)
            self.assertIn("case when status in ('homologated','published') then 0 else 1 end",source)
            self.assertIn("candidate_number desc limit 1",source)

    def test_switcher_exposes_canonical_p_and_separate_legacy_history(self):
        for path in (CANONICAL_UI,APP_UI):
            source=path.read_text()
            for marker in ('production_releases',"'kind':'P'", "'kind':'D'",'Histórico legado',"f'P{number}'", "f'D{number}'"):
                self.assertIn(marker,source)


if __name__=='__main__': unittest.main()
