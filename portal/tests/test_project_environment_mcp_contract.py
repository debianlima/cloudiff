from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
CONTROLLER=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
ENVIRONMENT=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'


def load_gateway():
    spec=importlib.util.spec_from_file_location('environment_mcp_gateway_test',GATEWAY)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class ProjectEnvironmentMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.gateway=load_gateway();cls.source=GATEWAY.read_text()

    def test_requested_tools_are_published(self):
        expected={
          'project.environment.list','project.environment.get','project.environment.validate',
          'project.environment.change.plan','approval.request-environment-change','project.environment.change.execute',
          'project.environment.promote.plan','approval.request-environment-promotion','project.environment.promote.execute',
          'project.environment.history',
        }
        names={item['name'] for item in self.gateway.TOOLS}
        self.assertTrue(expected<=names,expected-names)
        for name in expected:
            tool=next(item for item in self.gateway.TOOLS if item['name']==name)
            self.assertFalse(tool['inputSchema'].get('additionalProperties',True))

    def test_scopes_are_explicit_and_execution_is_destructive(self):
        expected={
          'project.environment.list':'project:environment-read',
          'project.environment.get':'project:environment-read',
          'project.environment.validate':'project:environment-plan',
          'project.environment.change.plan':'project:environment-plan',
          'approval.request-environment-change':'approval:request-environment-change',
          'project.environment.change.execute':'project:environment-execute',
          'project.environment.promote.plan':'project:environment-plan',
          'approval.request-environment-promotion':'approval:request-environment-promotion',
          'project.environment.promote.execute':'project:environment-promote',
          'project.environment.history':'project:environment-read',
        }
        for tool,scope in expected.items():self.assertEqual(self.gateway.SCOPE_BY_TOOL[tool],scope)
        self.assertIn('project.environment.change.execute',self.gateway.DESTRUCTIVE_TOOLS)
        self.assertIn('project.environment.promote.execute',self.gateway.DESTRUCTIVE_TOOLS)
        self.assertIn('project.environment.change.plan',self.gateway.READ_ONLY_TOOLS)

    def test_execute_uses_reserve_effect_finalize_and_exact_approval_binding(self):
        start=self.source.index("elif name in {'project.environment.change.execute','project.environment.promote.execute'}:")
        end=self.source.index("elif name=='runtime.catalog':",start)
        block=self.source[start:end]
        for marker in (
          'transaction_ids(',"approval_transition(approval_id,'reserve'",
          "project_environment_call('POST'","approval_transition(approval_id,'finalize'",
          "approval.get('project_slug')==slug","approval.get('requested_by')==client_id",
          "metadata.get('environment_plan_digest')","metadata.get('expected_revision')",
          "metadata.get('secret_values_in_metadata') is False",
        ):self.assertIn(marker,block)
        self.assertLess(block.index("'reserve'"),block.index("project_environment_call('POST'"))
        self.assertLess(block.index("project_environment_call('POST'"),block.index("'finalize'"))

    def test_approval_metadata_contains_no_operations_or_secret_references(self):
        start=self.source.index('def environment_approval_create(')
        end=self.source.index('def workspace_broker_post',start)
        block=self.source[start:end]
        self.assertIn("'content_stored':False",block)
        self.assertIn("'secret_values_in_metadata':False",block)
        self.assertNotIn("'operations'",block)
        self.assertNotIn('secret_reference',block)

    def test_controller_routes_share_canonical_module(self):
        source=CONTROLLER.read_text()
        for marker in (
          'project_environment.list_environment','project_environment.history','project_environment.missing_variables',
          'project_environment.validate_changes','project_environment.plan_change','project_environment.plan_promotion',
          'project_environment.apply_plan','project_environment.get_plan',
        ):self.assertIn(marker,source)
        self.assertIn("if not body.get('approved')",source)
        self.assertIn("'approval_required'",source)

    def test_secret_values_are_not_returned_by_environment_module(self):
        source=ENVIRONMENT.read_text()
        self.assertIn("'value':value",source)
        self.assertIn("if kind=='public' and include_value",source)
        self.assertIn("if snapshot.get('kind')=='secret':snapshot['value']=None",source)
        self.assertIn("'secretValuesIncluded':False",source)
        self.assertNotIn("'secretValue'",source)

    def test_role_scopes_and_onboarding_are_coherent(self):
        registry=REGISTRY.read_text();onboarding=ONBOARDING.read_text()
        for scope in (
          'project:environment-read','project:environment-plan','approval:request-environment-change',
          'project:environment-execute','approval:request-environment-promotion','project:environment-promote',
        ):
            self.assertIn(scope,registry);self.assertIn(scope,onboarding)
        viewer=registry[registry.index("'viewer':"):registry.index("'developer':")]
        self.assertIn('PROJECT_ENVIRONMENT_READ_SCOPES',viewer)
        self.assertNotIn('PROJECT_ENVIRONMENT_WRITE_SCOPES',viewer)
        developer=registry[registry.index("'developer':"):registry.index("'maintainer':")]
        self.assertIn('PROJECT_ENVIRONMENT_WRITE_SCOPES',developer)


if __name__=='__main__':unittest.main()
