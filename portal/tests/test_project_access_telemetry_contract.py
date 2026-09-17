from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
COLLECTOR=ROOT/'components/control-plane/current-apps/project-access-collector-current/cloudif-project-access-collector.py'
PATCH=ROOT/'components/control-plane/srv/cloudif/bin/cloudif-apply-router-academic-access-v1.sh'
RENDERER=ROOT/'components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-project-access-collector.service'


def load_collector():
    spec=importlib.util.spec_from_file_location('project_access_collector_test',COLLECTOR)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class ProjectAccessTelemetryContractTests(unittest.TestCase):
    def setUp(self):
        self.module=load_collector()
        self.tmp=tempfile.TemporaryDirectory()
        db=Path(self.tmp.name)/'portal.db'
        c=sqlite3.connect(db)
        c.execute('create table projects(slug text,name text,tenant text,status text)')
        c.execute('insert into projects values(?,?,?,?)',('alpha','Alpha','iff1-alpha','published'))
        c.commit();c.close();self.module.DB=db

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_view_is_attributed_without_sensitive_request_data(self):
        rec={'ts':'2026-09-17T20:00:00-03:00','msec':'1789671600.100','tenant':'iff1-alpha','user':'student1','method':'GET','uri':'/project/default','status':200}
        event=self.module._event_from_record(rec)
        self.assertEqual(event['project_slug'],'alpha')
        self.assertEqual(event['actor_id'],'student1')
        self.assertEqual(event['delegated_user_id'],'student1')
        self.assertEqual(event['source'],'project-access')
        self.assertEqual(event['action'],'environment.view')
        self.assertEqual(event['attrs']['path'],'/project/default')
        raw=json.dumps(event).lower()
        for bad in ('cookie','authorization','referer','remote_addr','query'):
            self.assertNotIn(bad,raw)

    def test_api_get_is_ignored_but_write_is_audited(self):
        base={'ts':'2026-09-17T20:00:00-03:00','msec':'1789671600.100','tenant':'iff1-alpha','user':'student1','uri':'/api/projects','status':200}
        self.assertIsNone(self.module._event_from_record({**base,'method':'GET'}))
        event=self.module._event_from_record({**base,'method':'POST'})
        self.assertEqual(event['action'],'environment.write')
        self.assertEqual(event['attrs']['resource'],'project-api')

    def test_view_event_id_deduplicates_within_five_minute_bucket(self):
        base={'ts':'2026-09-17T20:00:00-03:00','tenant':'iff1-alpha','user':'student1','method':'GET','uri':'/project/default','status':200}
        a=self.module._event_from_record({**base,'msec':'1789671600.100'})
        b=self.module._event_from_record({**base,'msec':'1789671699.900'})
        self.assertEqual(a['event_id'],b['event_id'])
        c=self.module._event_from_record({**base,'msec':'1789672000.100'})
        self.assertNotEqual(a['event_id'],c['event_id'])

    def test_unknown_or_ambiguous_tenant_is_not_attributed(self):
        rec={'ts':'2026-09-17T20:00:00-03:00','msec':'1','tenant':'unknown','user':'student1','method':'GET','uri':'/project/default','status':200}
        self.assertIsNone(self.module._event_from_record(rec))

    def test_router_log_is_privacy_safe_and_scope_limited(self):
        src=PATCH.read_text()
        log_line=next(line for line in src.splitlines() if line.startswith("log_format cloudif_project_access"))
        self.assertIn('$uri',log_line)
        for bad in ('$request_uri','$http_referer','$http_cookie','$remote_addr','$http_authorization'):
            self.assertNotIn(bad,log_line)
        self.assertIn("inject('location ^~ /project/ {'",src)
        self.assertIn("inject('location ^~ /api/ {'",src)
        self.assertIn('if=$cloudif_project_write_log',src)
        self.assertNotIn("inject('location ^~ /rest/v1/ {'",src)

    def test_renderer_reapplies_access_logging_after_authz(self):
        src=RENDERER.read_text()
        self.assertIn('cloudif-apply-router-academic-access-v1.sh',src)
        self.assertGreater(src.index('academic project access telemetry post-render'),src.index('tenant control v134 post-render normalization END'))

    def test_service_is_unprivileged_and_hardened(self):
        src=UNIT.read_text()
        self.assertIn('User=cloudif-control',src)
        self.assertIn('ProtectSystem=strict',src)
        self.assertIn('NoNewPrivileges=true',src)
        self.assertIn('ReadOnlyPaths=/srv/cloudif/router/logs /var/lib/cloudif/portal',src)
        self.assertIn('EnvironmentFile=/etc/cloudif/academic-audit.env',src)
        self.assertIn('CLOUDIF_PROJECT_ACCESS_PORT=18211',src)
        self.assertIn("'18211'",COLLECTOR.read_text())


if __name__=='__main__':
    unittest.main()
