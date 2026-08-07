from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
BROKER=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'
LIFECYCLE=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif_toolchain_lifecycle.py'
EXECUTOR=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py'
HTTP_EXECUTOR=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py'


def load_gateway():
    spec=importlib.util.spec_from_file_location('toolchain_mcp_gateway_contract',GATEWAY)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class ToolchainMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway=load_gateway();cls.source=GATEWAY.read_text()

    def test_complete_toolchain_toolset_is_published(self):
        required={
          'project.toolchain.get','project.toolchain.validate','project.toolchain.plan','project.toolchain.build.plan',
          'approval.request-toolchain-build','project.toolchain.build.execute','project.toolchain.build.status',
          'project.toolchain.logs.read','project.toolchain.image.list','project.toolchain.image.get',
          'project.toolchain.image.activate.plan','approval.request-toolchain-activation','project.toolchain.image.activate',
        }
        names={item['name'] for item in self.gateway.TOOLS}
        self.assertTrue(required<=names,required-names)
        for name in required:
            schema=next(item['inputSchema'] for item in self.gateway.TOOLS if item['name']==name)
            self.assertFalse(schema.get('additionalProperties',True),name)

    def test_scopes_are_explicit_and_write_tools_are_destructive(self):
        expected={
          'project.toolchain.get':'project:toolchain-read',
          'project.toolchain.validate':'project:toolchain-plan',
          'project.toolchain.plan':'project:toolchain-plan',
          'project.toolchain.build.plan':'project:toolchain-plan',
          'approval.request-toolchain-build':'approval:request-toolchain-build',
          'project.toolchain.build.execute':'project:toolchain-build-execute',
          'project.toolchain.build.status':'project:toolchain-read',
          'project.toolchain.logs.read':'project:toolchain-read',
          'project.toolchain.image.list':'project:toolchain-read',
          'project.toolchain.image.get':'project:toolchain-read',
          'project.toolchain.image.activate.plan':'project:toolchain-activate-plan',
          'approval.request-toolchain-activation':'approval:request-toolchain-activation',
          'project.toolchain.image.activate':'project:toolchain-activate-execute',
        }
        for tool,scope in expected.items():self.assertEqual(self.gateway.SCOPE_BY_TOOL[tool],scope)
        self.assertIn('project.toolchain.build.execute',self.gateway.DESTRUCTIVE_TOOLS)
        self.assertIn('project.toolchain.image.activate',self.gateway.DESTRUCTIVE_TOOLS)
        self.assertIn('project.toolchain.plan',self.gateway.READ_ONLY_TOOLS)
        self.assertIn('project.toolchain.image.activate.plan',self.gateway.READ_ONLY_TOOLS)

    def test_build_and_activation_use_distinct_approval_actions(self):
        self.assertIn("'project.toolchain.build'",self.source)
        self.assertIn("'project.toolchain.activation'",self.source)
        start=self.source.index('def approval_create_toolchain(')
        end=self.source.index('def toolchain_activation_plan',start)
        block=self.source[start:end]
        self.assertIn("'toolchain_plan_digest'",block)
        self.assertIn("'activation_plan_digest'",block)
        self.assertIn("'content_stored':False",block)
        self.assertIn("'secret_values_in_metadata':False",block)
        self.assertNotIn('provisionScriptContent',block)
        self.assertNotIn('secret_reference',block)
        self.assertNotIn('secretValue',block)

    def test_build_execute_uses_exact_binding_and_reserve_effect_finalize(self):
        start=self.source.index("elif name=='project.toolchain.build.execute':")
        end=self.source.index("elif name=='approval.request-toolchain-activation':",start)
        block=self.source[start:end]
        for marker in (
          'transaction_ids(\'project.toolchain.build\'',
          "approval_transition(approval_id,'reserve'",
          "build_broker_call('POST','/v1/toolchain/build'",
          "approval_transition(approval_id,'finalize'",
          "metadata.get('toolchain_plan_digest')",
          "metadata.get('config_revision')",
          "metadata.get('config_digest')",
          "metadata.get('requested_toolchain_digest')",
          "metadata.get('archive_sha256')",
          "metadata.get('services')==expected_services",
          "metadata.get('content_stored') is False",
          "metadata.get('secret_values_in_metadata') is False",
        ):self.assertIn(marker,block)
        self.assertLess(block.index("'reserve'"),block.index("build_broker_call('POST','/v1/toolchain/build'"))
        self.assertLess(block.index("build_broker_call('POST','/v1/toolchain/build'"),block.index("'finalize'"))
        self.assertIn("queued['images_activated']=False",block)
        self.assertIn("queued['containers_changed']=False",block)

    def test_activation_execute_uses_exact_binding_and_does_not_touch_containers(self):
        start=self.source.index("elif name=='project.toolchain.image.activate':")
        end=self.source.index("elif name=='runtime.catalog':",start)
        block=self.source[start:end]
        for marker in (
          'transaction_ids(\'project.toolchain.activation\'',
          "metadata.get('activation_plan_digest')",
          "metadata.get('environment')==environment",
          "metadata.get('job_id')==job_id",
          "metadata.get('after')==(plan.get('after') or [])",
          "build_broker_call('POST','/v1/toolchain/activation/apply'",
          "result['containers_changed']=False",
        ):self.assertIn(marker,block)
        self.assertLess(block.index("'reserve'"),block.index("build_broker_call('POST','/v1/toolchain/activation/apply'"))
        self.assertLess(block.index("build_broker_call('POST','/v1/toolchain/activation/apply'"),block.index("'finalize'"))

    def test_broker_and_executor_publish_dedicated_routes(self):
        broker=BROKER.read_text();lifecycle=LIFECYCLE.read_text();executor=EXECUTOR.read_text();http=HTTP_EXECUTOR.read_text()
        for marker in (
          "/v1/toolchain/plan","/v1/toolchain/validate","/v1/toolchain/build",
          "/v1/toolchain/activation/plan","/v1/toolchain/activation/apply",
          "/v1/toolchain/jobs/","/toolchain/images",
        ):self.assertIn(marker,broker)
        self.assertIn('def activation_apply(',lifecycle)
        self.assertIn("'containers_changed': False",lifecycle)
        self.assertIn("'pending_rebuild': True",lifecycle)
        self.assertIn('def validate_toolchain_archive(',executor)
        self.assertIn('def build_toolchain_bundle(',executor)
        self.assertIn("'/v1/toolchain/validate'",http)
        self.assertIn("'/v1/toolchain/build'",http)

    def test_role_scopes_are_coherent_without_implicit_secret_value_scope(self):
        registry=REGISTRY.read_text();onboarding=ONBOARDING.read_text()
        scopes={
          'project:toolchain-read','project:toolchain-plan','approval:request-toolchain-build',
          'project:toolchain-build-execute','project:toolchain-activate-plan',
          'approval:request-toolchain-activation','project:toolchain-activate-execute',
        }
        for scope in scopes:
            self.assertIn(scope,registry);self.assertIn(scope,onboarding)
        viewer=registry[registry.index("'viewer':"):registry.index("'developer':")]
        self.assertIn('PROJECT_TOOLCHAIN_READ_SCOPES',viewer)
        self.assertNotIn('PROJECT_TOOLCHAIN_WRITE_SCOPES',viewer)
        developer=registry[registry.index("'developer':"):registry.index("'maintainer':")]
        self.assertIn('PROJECT_TOOLCHAIN_WRITE_SCOPES',developer)
        toolchain_block=registry[registry.index('PROJECT_TOOLCHAIN_READ_SCOPES'):registry.index('PROJECT_ADMIN_SCOPES')]
        self.assertNotIn('environment-secret',toolchain_block)
        self.assertNotIn('project:environment-secret-read-execute',onboarding)


if __name__=='__main__':unittest.main()
