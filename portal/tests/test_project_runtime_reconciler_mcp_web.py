from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RECONCILER=ROOT/'components/control-plane/current-apps/project-runtime-reconciler-current/cloudif-project-runtime-reconciler.py'
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_runtime_reconcile_web.py'
ENVWEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
MCP_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service'
PORTAL_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-admin-portal.service'


def load_web(root:Path):
    control=root/'control.db';c=sqlite3.connect(control);c.executescript("create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text);create table project_acl(project_id text,subject_type text,subject text,role text);insert into projects values('p1','demo','Demo','alice','tenant','active');insert into project_acl values('p1','user','viewer','viewer');insert into project_acl values('p1','user','dev','developer');");c.commit();c.close()
    envspec=importlib.util.spec_from_file_location('cloudif_project_environment_web',ENVWEB);env=importlib.util.module_from_spec(envspec);assert envspec.loader;envspec.loader.exec_module(env);env.CONTROL_DB=control;sys.modules['cloudif_project_environment_web']=env
    spec=importlib.util.spec_from_file_location('runtime_reconcile_web_test',WEB);m=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(m);return m


def load_gateway():
    spec=importlib.util.spec_from_file_location('runtime_reconcile_mcp_test',GATEWAY);m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


class ProjectRuntimeReconcilerMCPWebTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.web=load_web(self.root)
    def tearDown(self):sys.modules.pop('cloudif_project_environment_web',None);self.temp.cleanup()

    def test_web_viewer_reads_but_cannot_plan(self):
        self.web._call=lambda method,path,payload=None,timeout=45:(200,{'ok':True,'states':[{'status':'pending-restart','effectsExecuted':False}],'count':1})
        code,data=self.web.handle_get('demo','status',{},'viewer',[]);self.assertEqual(code,200);self.assertEqual(data['states'][0]['status'],'pending-restart');self.assertFalse(data['effectsExecuted'])
        code,data=self.web.handle_post('demo','plan',{'environment':'preview'},'viewer',[]);self.assertEqual(code,403)

    def test_web_developer_plan_remains_side_effect_free(self):
        captured={}
        def call(method,path,payload=None,timeout=45):captured.update({'method':method,'path':path,'payload':payload});return 200,{'ok':True,'planDigest':'a'*64,'status':'pending-restart','effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}
        self.web._call=call;code,data=self.web.handle_post('demo','plan',{'environment':'preview'},'dev',[]);self.assertEqual(code,200);self.assertEqual(captured['method'],'POST');self.assertIn('/reconcile-plan',captured['path']);self.assertFalse(data['effectsExecuted'])

    def test_portal_routes_are_isolated_and_plan_keeps_csrf(self):
        source=COEXIST.read_text();self.assertIn('cloudif_project_runtime_reconcile_web',source);self.assertIn('runtime-state|runtime-drift',source);self.assertIn('runtime-reconcile/(plan)',source)
        start=source.index("runtime_match = re.fullmatch(r'/cloudiff?/portal/api/projects/",source.index('def do_POST'));end=source.index('secret_match = re.fullmatch',start);block=source[start:end]
        self.assertIn('_prod_csrf_equal',block);self.assertLess(block.index('_prod_csrf_equal'),block.index('handle_runtime_post'))

    def test_mcp_tools_and_scopes_are_explicit(self):
        m=load_gateway();expected={'project.configuration.status':'project:runtime-status-read','project.configuration.drift':'project:runtime-status-read','project.configuration.reconcile.plan':'project:runtime-reconcile-plan'}
        names={x['name'] for x in m.TOOLS};self.assertTrue(set(expected)<=names)
        for tool,scope in expected.items():self.assertEqual(m.SCOPE_BY_TOOL[tool],scope);self.assertIn(tool,m.READ_ONLY_TOOLS)
        self.assertNotIn('project.configuration.reconcile.execute',names)

    def test_mcp_plan_calls_only_reconciler_plan_endpoint(self):
        source=GATEWAY.read_text();start=source.index("elif name in {'project.configuration.status','project.configuration.drift','project.configuration.reconcile.plan'}:");end=source.index('elif name in SECRET_READ_PLAN_TOOLS',start);block=source[start:end]
        self.assertIn("runtime_reconciler_call('POST'",block);self.assertIn('/reconcile-plan',block);self.assertNotIn('deployment.multiservice.execute',block);self.assertNotIn('build.multiservice.execute',block);self.assertIn("data.get('effectsExecuted') is not False",block)

    def test_reconciliation_workflow_points_to_existing_approved_tools(self):
        spec=importlib.util.spec_from_file_location('runtime_plan_workflow_test',RECONCILER);m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m)
        rebuild=[x['tool'] for x in m.recommended_workflow('pending-rebuild','rebuild','build_old')]
        self.assertEqual(rebuild,['build.multiservice.plan','approval.request-multiservice-build','build.multiservice.execute','deployment.multiservice.plan','approval.request-multiservice-deployment','deployment.multiservice.execute'])
        restart=[x['tool'] for x in m.recommended_workflow('pending-restart','restart','build_123')];self.assertEqual(restart,['deployment.multiservice.plan','approval.request-multiservice-deployment','deployment.multiservice.execute'])
        self.assertEqual(m.recommended_workflow('synchronized','none','build_123'),[])

    def test_agent_role_scopes_do_not_allow_viewer_to_plan(self):
        registry=REGISTRY.read_text();viewer=registry[registry.index("'viewer':"):registry.index("'developer':")];developer=registry[registry.index("'developer':"):registry.index("'maintainer':")]
        self.assertIn('PROJECT_RUNTIME_READ_SCOPES',viewer);self.assertNotIn('PROJECT_RUNTIME_PLAN_SCOPES',viewer);self.assertIn('PROJECT_RUNTIME_PLAN_SCOPES',developer)
        onboarding=ONBOARDING.read_text();self.assertIn('project:runtime-status-read',onboarding);self.assertIn('project:runtime-reconcile-plan',onboarding)

    def test_mcp_and_portal_receive_reconciler_token_only_as_optional_env_file(self):
        for unit in (MCP_UNIT,PORTAL_UNIT):self.assertIn('EnvironmentFile=-/etc/cloudif/runtime-reconciler.env',unit.read_text())


if __name__=='__main__':unittest.main()
