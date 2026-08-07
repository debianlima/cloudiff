from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/project-observability-current/cloudif-project-observability.py'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-project-observability.service'


def load_module(root:Path):
    runtime=root/'runtime.db';config=root/'config.db';build=root/'build.db'
    c=sqlite3.connect(runtime);c.execute('create table runtime_reconciliation(project_slug text,environment text,status text,desired_json text,observed_json text,reasons_json text,pending_action text,checked_at integer)');c.execute("insert into runtime_reconciliation values(?,?,?,?,?,?,?,?)",('demo','production','missing-variable',json.dumps({'missingVariables':[{'service':'api','name':'DATABASE_URL','secret':True}]}),'{}',json.dumps(['missing:api:DATABASE_URL']),'configure',100));c.execute("insert into runtime_reconciliation values(?,?,?,?,?,?,?,?)",('demo','preview','pending-restart',json.dumps({'missingVariables':[]}),'{}',json.dumps(['runtime-environment-changed']),'restart',101));c.commit();c.close()
    c=sqlite3.connect(config);c.executescript('create table environment_history(event_id text,project_slug text);create table environment_plans(plan_digest text,project_slug text);create table environment_entries(project_slug text,name text);create table environment_secret_events(project_slug text,event_type text);create table environment_secret_materials(project_slug text,environment text,service text,name text,status text,expires_at integer,secret_reference text);');c.executemany('insert into environment_history values(?,?)',[('e1','demo'),('e2','demo')]);c.execute("insert into environment_plans values('p1','demo')");c.execute("insert into environment_entries values('demo','LOG_LEVEL')");c.executemany('insert into environment_secret_events values(?,?)',[('demo','rotated'),('demo','rotated'),('demo','read-approved')]);c.execute("insert into environment_secret_materials values(?,?,?,?,?,?,?)",('demo','production','api','JWT_SECRET','active',1,'cloudiff-secret://demo/production/api/JWT_SECRET/v1'));c.commit();c.close()
    c=sqlite3.connect(build);c.executescript('create table multiservice_jobs(job_id text,project_slug text,status text,toolchain_digest text);create table toolchain_builds(build_id text,project_slug text,status text,toolchain_digest text);');c.executemany('insert into multiservice_jobs values(?,?,?,?)',[('b1','demo','succeeded','t1'),('b2','demo','failed','t2')]);c.executemany('insert into toolchain_builds values(?,?,?,?)',[('t1','demo','ready','x'),('t2','demo','quarantined','y')]);c.commit();c.close()
    os.environ['CLOUDIF_RUNTIME_RECONCILER_DB']=str(runtime);os.environ['CLOUDIF_PROJECT_CONFIG_DB']=str(config);os.environ['CLOUDIF_BUILD_DB']=str(build);os.environ['CLOUDIF_PROJECT_OBSERVABILITY_TOKEN']='token'
    spec=importlib.util.spec_from_file_location('observability_test_'+root.name.replace('-','_'),SOURCE);m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


class ProjectObservabilityServiceTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.module=load_module(self.root)
    def tearDown(self):self.temp.cleanup()

    def test_snapshot_combines_drift_environment_secret_and_build_without_secret_material(self):
        data=self.module.snapshot('demo');self.assertEqual(data['runtime']['states']['missing-variable'],1);self.assertEqual(data['runtime']['states']['pending-restart'],1);self.assertEqual(data['runtime']['missingVariables'],1);self.assertEqual(data['environment']['historyEvents'],2);self.assertEqual(data['environment']['secretEvents']['rotated'],2);self.assertEqual(data['environment']['expiredSecrets'],1);self.assertEqual(data['build']['buildJobs'],{'succeeded':1,'failed':1});self.assertEqual(data['build']['toolchainBuilds'],{'ready':1,'quarantined':1});self.assertFalse(data['effectsExecuted']);self.assertFalse(data['secretValuesIncluded']);self.assertFalse(data['secretReferencesIncluded'])
        rendered=json.dumps(data);self.assertNotIn('cloudiff-secret://',rendered);self.assertNotIn('JWT_SECRET/v1',rendered)

    def test_production_missing_variable_and_expired_secret_are_critical_alerts(self):
        alerts=self.module.snapshot('demo')['alerts'];by_code={item['code']:item for item in alerts};self.assertEqual(by_code['runtime-missing-variable']['severity'],'critical');self.assertEqual(by_code['secret-expired']['severity'],'critical');self.assertEqual(by_code['toolchain-quarantined']['severity'],'high')

    def test_prometheus_metrics_are_bounded_and_do_not_include_project_secret_names(self):
        metrics=self.module.metrics_text('demo');self.assertIn('cloudiff_configuration_drift_total 2',metrics);self.assertIn('cloudiff_missing_variables_total 1',metrics);self.assertIn('cloudiff_environment_changes_total 2',metrics);self.assertIn('cloudiff_secret_events_total{event="rotated"} 2',metrics);self.assertIn('cloudiff_build_jobs_total{status="failed"} 1',metrics);self.assertNotIn('DATABASE_URL',metrics);self.assertNotIn('JWT_SECRET',metrics);self.assertNotIn('cloudiff-secret://',metrics)

    def test_multiservice_jobs_are_not_double_counted_as_toolchain_builds(self):
        build=self.module.build_summary('demo');self.assertEqual(sum(build['buildJobs'].values()),2);self.assertEqual(sum(build['toolchainBuilds'].values()),2)

    def test_read_only_database_connections_are_explicit(self):
        source=SOURCE.read_text();self.assertIn("sqlite3.connect(f'file:{path}?mode=ro'",source);self.assertNotIn('insert into',source.lower());self.assertNotIn('update ',source.lower());self.assertNotIn('delete from',source.lower())

    def test_service_sandbox_allows_wal_files_but_code_is_read_only(self):
        unit=UNIT.read_text();self.assertIn('ProtectSystem=strict',unit);self.assertIn('ReadWritePaths=/var/lib/cloudif/runtime-reconciler /var/lib/cloudif/project-config /var/lib/cloudif/build-broker',unit);self.assertIn('IPAddressAllow=127.0.0.0/8',unit);self.assertIn('IPAddressDeny=any',unit)


if __name__=='__main__':unittest.main()
