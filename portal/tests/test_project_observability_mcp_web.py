from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_observability_web.py'
ENVWEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
MCP_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service'
PORTAL_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-admin-portal.service'


def load_web(root:Path):
    control=root/'control.db';c=sqlite3.connect(control);c.executescript("create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text);create table project_acl(project_id text,subject_type text,subject text,role text);insert into projects values('p1','demo','Demo','alice','tenant','active');insert into project_acl values('p1','user','viewer','viewer');");c.commit();c.close()
    envspec=importlib.util.spec_from_file_location('cloudif_project_environment_web',ENVWEB);env=importlib.util.module_from_spec(envspec);assert envspec.loader;envspec.loader.exec_module(env);env.CONTROL_DB=control;sys.modules['cloudif_project_environment_web']=env
    spec=importlib.util.spec_from_file_location('observability_web_test',WEB);m=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(m);return m


def load_gateway():
    spec=importlib.util.spec_from_file_location('observability_mcp_test',GATEWAY);m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


class ProjectObservabilityMCPWebTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.web=load_web(self.root)
    def tearDown(self):sys.modules.pop('cloudif_project_environment_web',None);self.temp.cleanup()

    def test_web_reader_can_observe_but_unrelated_user_is_denied(self):
        self.web._call=lambda path,query=None:(200,{'ok':True,'projectSlug':'demo','alerts':[],'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False})
        code,data=self.web.handle_get('demo','snapshot','viewer',[]);self.assertEqual(code,200);self.assertFalse(data['effectsExecuted'])
        code,data=self.web.handle_get('demo','alerts','unrelated',[]);self.assertEqual(code,403);self.assertEqual(data['error']['code'],'forbidden')

    def test_portal_observability_is_new_get_only_route(self):
        source=COEXIST.read_text();self.assertIn('cloudif_project_observability_web',source);self.assertIn("observability(?:/(alerts))?",source)
        get_start=source.index('def do_GET') if 'def do_GET' in source else 0;post_start=source.index('def do_POST') if 'def do_POST' in source else len(source)
        self.assertIn('observability_match',source[get_start:post_start]);self.assertNotIn('/observability',source[post_start:])

    def test_mcp_tools_are_read_only_and_schema_closed(self):
        m=load_gateway();expected={'project.observability.get','project.observability.alerts'};names={x['name'] for x in m.TOOLS};self.assertTrue(expected<=names)
        for name in expected:
            self.assertIn(name,m.READ_ONLY_TOOLS);self.assertNotIn(name,m.DESTRUCTIVE_TOOLS);self.assertEqual(m.SCOPE_BY_TOOL[name],'project:observability-read');tool=next(x for x in m.TOOLS if x['name']==name);self.assertFalse(tool['inputSchema'].get('additionalProperties',True))

    def test_mcp_handler_rejects_observability_contract_leak(self):
        source=GATEWAY.read_text();start=source.index("elif name in {'project.observability.get','project.observability.alerts'}:");end=source.index("elif name in {'project.configuration.status'",start);block=source[start:end]
        self.assertIn("data.get('effectsExecuted') is not False",block);self.assertIn("data.get('secretValuesIncluded') is not False",block);self.assertIn("data.get('secretReferencesIncluded') is not False",block);self.assertNotIn("method='POST'",block)

    def test_every_agent_role_gets_observability_read_only(self):
        registry=REGISTRY.read_text();role_start=registry.index('ROLE_SCOPES=')
        for role,next_role in (('viewer','developer'),('developer','maintainer'),('maintainer','release-manager'),('release-manager','project-admin')):
            a=registry.index("'"+role+"':",role_start);b=registry.index("'"+next_role+"':",a);self.assertIn('PROJECT_OBSERVABILITY_SCOPES',registry[a:b])
        a=registry.index("'project-admin':",role_start);b=registry.find('\n}',a);self.assertIn('PROJECT_OBSERVABILITY_SCOPES',registry[a:b])
        self.assertIn('project:observability-read',ONBOARDING.read_text())

    def test_portal_and_mcp_receive_only_observability_service_token(self):
        for unit in (MCP_UNIT,PORTAL_UNIT):self.assertIn('EnvironmentFile=-/etc/cloudif/project-observability.env',unit.read_text())


if __name__=='__main__':unittest.main()
