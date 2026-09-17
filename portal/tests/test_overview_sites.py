import tempfile
import unittest
from unittest import mock
from pathlib import Path
from portal.modules.overview.views import _network_graph, _site_card, sites_body


class OverviewSiteCardTest(unittest.TestCase):
    def test_published_site_keeps_new_tab_and_individual_manage_link(self):
        markup = _site_card({
            "project_slug": "library-test", "name": "Library", "stable_hostname": "library.example",
            "published": True,
        })
        self.assertIn('target="_blank"', markup)
        self.assertIn('tab=publicacao&project=library-test', markup)
        self.assertIn('Publicado', markup)

    def test_unpublished_site_has_manage_action_without_public_link(self):
        markup = _site_card({
            "project_slug": "draft-site", "name": "Draft", "stable_hostname": None,
            "published": False,
        })
        self.assertIn('Ainda não publicado', markup)
        self.assertIn('tab=publicacao&project=draft-site', markup)
        self.assertNotIn('target="_blank"', markup)




    def test_registry_tenants_include_own_and_count_other_academic_databases(self):
        from portal.modules.overview import service
        from types import SimpleNamespace
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            handle.write("tenant,created_at\n")
            handle.write("akadmin,now\n")
            handle.write("iff1742962,now\n")
            handle.write("iff1860746,now\n")
            registry = handle.name
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_handle:
            database = db_handle.name
        import sqlite3
        con = sqlite3.connect(database)
        con.executescript("""
            CREATE TABLE projects (slug TEXT, name TEXT, owner TEXT, status TEXT, tenant TEXT);
            CREATE TABLE project_acl (slug TEXT, subject_type TEXT, subject TEXT);
            CREATE TABLE project_publications (project_slug TEXT, stable_hostname TEXT, version_hostname TEXT, status TEXT, published_at TEXT, is_active INTEGER, id INTEGER);
            CREATE TABLE project_publication_aliases (project_slug TEXT, alias TEXT);
            CREATE TABLE project_tenants (project TEXT, tenant TEXT, is_primary INTEGER);
            CREATE TABLE tenant_acl (tenant TEXT, subject_type TEXT, subject TEXT);
        """)
        con.commit(); con.close()
        identity = SimpleNamespace(username="iff1742962", groups=("CloudIF-Tenants-Admin",))
        with mock.patch.object(service, "_DB", database), mock.patch.object(service, "_TENANTS_REGISTRY", registry):
            resources = service.academic_resources(identity)
        self.assertEqual([item["tenant"] for item in resources["databases"]], ["iff1742962"])
        self.assertEqual(resources["other_databases"], 1)

    def test_other_sites_card_opens_filtered_publication_scope(self):
        from portal.modules.overview.views import overview_body
        data = {
            "username": "admin", "metrics": {"nodes": [], "fmt": lambda _v: "0 B", "fmt_rate": lambda _v: "0 B/s", "online_count": 0, "node_count": 0},
            "resources": {"sites": [], "databases": [], "can_view_others": True, "other_sites": 2, "other_databases": 1},
        }
        markup = overview_body(data)
        self.assertIn('/cloudiff/portal/?tab=publicacao&amp;scope=others#other-user-sites', markup)

    def test_sites_page_uses_canonical_empty_state(self):
        markup = sites_body({"resources": {"sites": []}})
        self.assertIn("Meus sites", markup)
        self.assertIn("Você ainda não publicou um site", markup)
        self.assertIn("Ver meus projetos", markup)

    def test_network_graph_explains_direction_and_uses_comparative_bars(self):
        markup = _network_graph({
            "network_rx_bps": 2000,
            "network_tx_bps": 1000,
            "network_rx_label": "2.0 KB/s",
            "network_tx_label": "1.0 KB/s",
        })
        self.assertIn("Tráfego de rede", markup)
        self.assertIn("Taxa atual recebida e enviada pelo servidor", markup)
        self.assertIn("Recebimento", markup)
        self.assertIn("Envio", markup)
        self.assertIn('width:100%', markup)
        self.assertIn('width:50%', markup)



    def test_academic_tracking_is_global_only_and_uses_canonical_visibility(self):
        from portal.modules.overview import service
        from portal.core.auth import Identity
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_handle:
            database=db_handle.name
        con=sqlite3.connect(database)
        con.executescript("""
            CREATE TABLE projects(slug TEXT,name TEXT,tenant TEXT,owner TEXT,description TEXT,repo_url TEXT,komodo_status TEXT,status TEXT,updated_at TEXT,repo_name TEXT,stack_name TEXT);
            CREATE TABLE project_acl(slug TEXT,subject_type TEXT,subject TEXT);
            CREATE TABLE tenant_acl(tenant TEXT,subject_type TEXT,subject TEXT);
            INSERT INTO projects VALUES('alpha','Alpha','','alice','','','','active','2026-09-17T10:00:00Z','','');
            INSERT INTO projects VALUES('beta','Beta','','bob','','','','active','2026-09-17T11:00:00Z','','');
            INSERT INTO project_acl VALUES('beta','user','prof');
        """)
        con.commit();con.close()
        professor=Identity('prof','prof@example.invalid',frozenset({'CloudIF-Professor'}))
        student=Identity('alice','alice@example.invalid',frozenset({'CloudIF-Aluno'}))
        def fake_summary(_identity, project):
            self.assertEqual(project['slug'],'beta')
            return {'ok':True,'slug':'beta','name':'Beta','members':5,'active_7d':3,'without_activity_7d':2,'events_14d':18,'tasks_open':4,'stories_open':1,'channels_14d':{'taiga':5,'forgejo':7,'mcp':6,'environment':4},'production':{'instrumented':True,'published':True,'window_days':7,'public_requests':120,'public_unique_visitors':13,'errors':2,'last_seen':'2026-09-17T20:00:00Z','primary_host':'beta.cloudiff.duckdns.org'}}
        with mock.patch.object(service,'_DB',database), mock.patch.object(service,'project_tracking_summary',side_effect=fake_summary) as tracking:
            data=service.academic_tracking(professor)
            self.assertTrue(data['enabled'])
            self.assertEqual(data['project_count'],1)
            self.assertEqual(data['members'],5)
            self.assertEqual(data['active_7d'],3)
            self.assertEqual(data['without_activity_7d'],2)
            self.assertEqual(data['events_14d'],18)
            self.assertEqual(data['production_requests_7d'],120)
            self.assertEqual(data['projects'][0]['slug'],'beta')
            self.assertEqual(tracking.call_count,1)
            student_data=service.academic_tracking(student)
            self.assertFalse(student_data['enabled'])
            self.assertEqual(student_data['projects'],[])
            self.assertEqual(tracking.call_count,1)

    def test_academic_tracking_view_is_supportive_and_transparent_about_coverage(self):
        from portal.modules.overview.views import academic_tracking_body
        data={'academic_tracking':{
            'enabled':True,'project_count':1,'members':5,'active_7d':3,'without_activity_7d':2,'events_14d':18,'production_requests_7d':120,
            'projects':[{'ok':True,'slug':'beta','name':'Beta','members':5,'active_7d':3,'without_activity_7d':2,'events_14d':18,'tasks_open':4,'stories_open':1,'last_activity':'2026-09-17T11:00:00Z','channels_14d':{'taiga':5,'forgejo':7,'mcp':6,'environment':4},'production':{'instrumented':True,'published':True,'window_days':7,'public_requests':120,'public_unique_visitors':13,'errors':2,'last_seen':'2026-09-17T20:00:00Z','primary_host':'beta.cloudiff.duckdns.org'}}]
        }}
        markup=academic_tracking_body(data)
        self.assertIn('Acompanhamento acadêmico',markup)
        self.assertIn('Sinais dos projetos',markup)
        self.assertIn('Ativos · 7d',markup)
        self.assertIn('Sem atividade registrada · 7d',markup)
        self.assertIn('Taiga <b>5</b>',markup)
        self.assertIn('Forgejo <b>7</b>',markup)
        self.assertIn('CloudIFF/MCP <b>6</b>',markup)
        self.assertIn('Produção pública · 7d',markup)
        self.assertIn('120',markup)
        self.assertIn('Visitantes externos · aprox.',markup)
        self.assertIn('Ambiente CloudIFF <b>4</b>',markup)
        self.assertIn('não é nota, ranking',markup)
        self.assertIn('produção pública é mostrada apenas de forma agregada/anônima',markup)
        self.assertIn('tab=taiga&amp;project=beta',markup)

    def test_academic_tracking_css_is_responsive(self):
        css=(Path(__file__).resolve().parents[1] / 'design' / 'components.css').read_text()
        for marker in ('.academic-tracking{','.academic-summary-strip{','.academic-project-metrics{','.academic-channel-grid{','.academic-tracking-note{'):
            self.assertIn(marker,css)
        self.assertIn('@media(max-width:560px)',css)

    def test_publication_submit_preserves_operation_before_disabling_button(self):
        source = (Path(__file__).resolve().parents[1] / "design" / "app.js").read_text()
        self.assertIn("event.submitter", source)
        self.assertIn("operation.name=button.name", source)
        self.assertIn("operation.value=button.value", source)
        self.assertLess(source.index("operation.value=button.value"), source.index("button.disabled=true"))

    def test_server_metrics_prefers_physical_and_mounted_storage_fields(self):
        from portal.modules.overview import service
        import json, sqlite3
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_handle:
            database = db_handle.name
        con = sqlite3.connect(database)
        con.execute("create table node_metrics_cache(node text, ok integer, payload text, updated_at text)")
        payload = {
            "ok": True,
            "memory": {"total": 16 * 1024**3, "used": 4 * 1024**3},
            "disk_root": {"size": 100 * 1024**3, "used": 20 * 1024**3},
            "storage": {
                "physical_total": 3 * 1024**4,
                "mounted_total": 2 * 1024**4,
                "mounted_used": 200 * 1024**3,
                "outside_mounted_filesystems": 1 * 1024**4,
            },
            "docker": {"count": 4},
        }
        con.execute("insert into node_metrics_cache values(?,?,?,datetime('now'))", ("backup", 1, json.dumps(payload)))
        con.commit(); con.close()
        with mock.patch.object(service, "_DB", database):
            metrics = service.server_metrics()
        node = metrics["nodes"][0]
        self.assertEqual(node["storage_physical_total"], 3 * 1024**4)
        self.assertEqual(node["disk_total"], 100 * 1024**3)
        self.assertEqual(node["disk_used"], 20 * 1024**3)
        self.assertEqual(node["storage_outside_root"], 3 * 1024**4 - 100 * 1024**3)
        self.assertEqual(node["container_count"], 4)

    def test_overview_renders_capacity_and_memory_graphs(self):
        from portal.modules.overview.views import overview_body
        from portal.modules.overview.service import _fmt_bytes, _fmt_rate, _fmt_storage
        data = {
            "username": "admin",
            "metrics": {
                "nodes": [{
                    "node": "backup", "online": True, "stale": False,
                    "mem_used": 4 * 1024**3, "mem_total": 16 * 1024**3, "mem_pct": 25,
                    "disk_used": 20 * 1024**3, "disk_total": 100 * 1024**3, "disk_pct": 20,
                    "storage_physical_total": 3 * 1024**4, "storage_outside_root": 3 * 1024**4 - 100 * 1024**3,
                    "storage_disk_count": 2,
                    "network_rx_bps": 0, "network_tx_bps": 0,
                }],
                "fmt": _fmt_bytes, "fmt_storage": _fmt_storage, "fmt_rate": _fmt_rate, "online_count": 1, "node_count": 1,
            },
            "resources": {"sites": [], "databases": [], "can_view_others": False, "other_sites": 0, "other_databases": 0},
        }
        markup = overview_body(data)
        self.assertIn("Capacidade física por servidor", markup)
        self.assertIn("Uso de memória por servidor", markup)
        self.assertIn("Capacidade física instalada", markup)
        self.assertIn("Sistema (/)", markup)
        self.assertIn("além do filesystem raiz", markup)
        self.assertIn("2 disco(s) físico(s)", markup)
        self.assertIn("3.3 TB", markup)

    def test_modular_public_summary_uses_canonical_cpp_metrics(self):
        import importlib
        import sys
        from portal.modules.overview import service
        component_lib = Path(__file__).resolve().parents[2] / "components" / "control-plane" / "srv" / "cloudif" / "lib"
        sys.path.insert(0, str(component_lib))
        try:
            pages = importlib.import_module("cloudif_ui_pages")
            metrics = {
                "nodes": [{
                    "node": "backup", "online": True, "updated_at": "2026-09-09T03:30:52+00:00",
                    "mem_used": 1 * 1024**3, "mem_total": 16 * 1024**3, "mem_pct": 6,
                    "disk_used": 17 * 1000**3, "disk_total": 979 * 1000**3, "disk_pct": 2,
                    "storage_physical_total": 3 * 1000**4, "storage_disk_count": 2,
                    "container_count": 4,
                }],
                "agg_mem": "1.0 GB / 16.0 GB",
                "agg_storage_physical": "3.0 TB",
                "agg_storage_root": "17.0 GB / 979.0 GB",
                "fmt": service._fmt_bytes,
                "fmt_storage": service._fmt_storage,
            }
            with mock.patch.object(service, "server_metrics", return_value=metrics):
                markup = pages.render_server_metric_section()
        finally:
            sys.path.pop(0)
        self.assertIn("Capacidade física por servidor", markup)
        self.assertIn("Uso de memória por servidor", markup)
        self.assertIn("Capacidade física instalada:", markup)
        self.assertIn("Sistema (/)", markup)
        self.assertIn("3.0 TB", markup)
        self.assertIn("Containers:</strong> 4", markup)
        self.assertIn("cloudif-node-metrics-cpp", markup)
        self.assertNotIn('<span>Disco</span>', markup)


if __name__ == "__main__":
    unittest.main()
