from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'


def load_gateway():
    spec=importlib.util.spec_from_file_location('secret_mcp_contract_test',GATEWAY);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class ProjectSecretMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.module=load_gateway();cls.source=GATEWAY.read_text()

    def test_full_secret_lifecycle_tools_are_published_without_raw_read(self):
        expected={
          'project.environment.secret.list','project.environment.secret.history','project.environment.secret.stage',
          'project.environment.secret.rotate.plan','approval.request-secret-rotation','project.environment.secret.rotate.execute',
          'project.environment.secret.revoke.plan','approval.request-secret-revocation','project.environment.secret.revoke.execute',
          'project.environment.secret.promote.plan','approval.request-secret-promotion','project.environment.secret.promote.execute',
          'project.environment.secret.read.plan','approval.request-secret-read','project.environment.secret.read.execute',
        }
        names={item['name'] for item in self.module.TOOLS};self.assertTrue(expected<=names,expected-names)
        self.assertFalse(any('resolve-internal' in name or name.endswith('.secret.read') for name in names))
        for name in expected:
            schema=next(item['inputSchema'] for item in self.module.TOOLS if item['name']==name);self.assertFalse(schema.get('additionalProperties',True),name)

    def test_secret_scopes_are_explicit_and_do_not_include_resolver_scope(self):
        expected={
          'project.environment.secret.list':'project:environment-secret-read',
          'project.environment.secret.history':'project:environment-secret-read',
          'project.environment.secret.stage':'project:environment-secret-stage',
          'project.environment.secret.rotate.plan':'project:environment-secret-plan',
          'approval.request-secret-rotation':'approval:request-secret-rotation',
          'project.environment.secret.rotate.execute':'project:environment-secret-execute',
          'project.environment.secret.revoke.plan':'project:environment-secret-plan',
          'approval.request-secret-revocation':'approval:request-secret-revocation',
          'project.environment.secret.revoke.execute':'project:environment-secret-execute',
          'project.environment.secret.promote.plan':'project:environment-secret-plan',
          'approval.request-secret-promotion':'approval:request-secret-promotion',
          'project.environment.secret.promote.execute':'project:environment-secret-execute',
        }
        for tool,scope in expected.items():self.assertEqual(self.module.SCOPE_BY_TOOL[tool],scope)
        self.assertFalse(any('resolver' in scope or 'secret-value' in scope for scope in self.module.SCOPE_BY_TOOL.values()))

    def test_stage_and_execute_are_effectful_but_plans_are_read_only(self):
        self.assertIn('project.environment.secret.stage',self.module.DESTRUCTIVE_TOOLS)
        for name in ('project.environment.secret.rotate.execute','project.environment.secret.revoke.execute','project.environment.secret.promote.execute'):
            self.assertIn(name,self.module.DESTRUCTIVE_TOOLS)
        for name in ('project.environment.secret.list','project.environment.secret.history','project.environment.secret.rotate.plan','project.environment.secret.revoke.plan','project.environment.secret.promote.plan'):
            self.assertIn(name,self.module.READ_ONLY_TOOLS)

    def test_approval_metadata_contains_no_plaintext_or_ciphertext(self):
        start=self.source.index('def secret_approval_create(');end=self.source.index('def secret_plan_metadata',start);block=self.source[start:end]
        self.assertIn("'content_stored':False",block);self.assertIn("'secret_values_in_metadata':False",block);self.assertIn("'ciphertext_in_metadata':False",block)
        self.assertNotIn("'secret_value':",block);self.assertNotIn('secretValue',block);self.assertNotIn('resolvedSecrets',block);self.assertNotIn('ciphertext_b64',block)

    def test_execute_uses_reserve_effect_finalize_and_exact_source_bindings(self):
        start=self.source.index('def secret_mcp_execute(');end=self.source.index('def environment_plan_get',start);block=self.source[start:end]
        for marker in ('transaction_ids(',"approval_transition(approval_id,'reserve'",'project_secret_call(\'POST\'',"approval_transition(approval_id,'finalize'",'secret_stage_binding_mismatch','secret_reference_binding_mismatch','source_secret_reference_binding_mismatch'):
            self.assertIn(marker,block)
        self.assertLess(block.index("'reserve'"),block.index("project_secret_call('POST'"));self.assertLess(block.index("project_secret_call('POST'"),block.index("'finalize'"))

    def test_stage_clears_local_secret_and_public_contract_rejects_leaks(self):
        start=self.source.index('def secret_mcp_read_or_plan(');end=self.source.index('def secret_mcp_request_approval',start);block=self.source[start:end]
        self.assertIn("secret_value=args.get('secret_value')",block);self.assertIn('finally:',block);self.assertIn('secret_value=None',block)
        self.assertIn("data.get('secretValueIncluded') is True",block);self.assertIn("data.get('ciphertextIncluded') is True",block)

    def test_agent_profiles_include_metadata_read_and_controlled_write_only(self):
        registry=REGISTRY.read_text();onboarding=ONBOARDING.read_text()
        for scope in ('project:environment-secret-read','project:environment-secret-stage','project:environment-secret-plan','approval:request-secret-rotation','approval:request-secret-revocation','approval:request-secret-promotion','project:environment-secret-execute'):
            self.assertIn(scope,registry);self.assertIn(scope,onboarding)
        viewer=registry[registry.index("'viewer':"):registry.index("'developer':")]
        self.assertIn('PROJECT_SECRET_READ_SCOPES',viewer);self.assertNotIn('PROJECT_SECRET_WRITE_SCOPES',viewer)
        developer=registry[registry.index("'developer':"):registry.index("'maintainer':")]
        self.assertIn('PROJECT_SECRET_WRITE_SCOPES',developer)
        self.assertNotIn('resolve-internal',registry+onboarding)

    def test_exceptional_read_tools_are_separate_critical_and_raw_only_on_execute(self):
        self.assertEqual(self.module.SCOPE_BY_TOOL['project.environment.secret.read.plan'],'project:environment-secret-read-plan')
        self.assertEqual(self.module.SCOPE_BY_TOOL['approval.request-secret-read'],'approval:request-secret-read')
        self.assertEqual(self.module.SCOPE_BY_TOOL['project.environment.secret.read.execute'],'project:environment-secret-read-execute')
        self.assertIn('project.environment.secret.read.plan',self.module.READ_ONLY_TOOLS)
        self.assertIn('project.environment.secret.read.execute',self.module.DESTRUCTIVE_TOOLS)
        source=self.source
        start=source.index('def secret_mcp_execute(');end=source.index('def environment_plan_get',start);block=source[start:end]
        self.assertIn("'project.environment.secret.read.execute':'read'",block)
        self.assertIn("path='/read/apply'",block)
        self.assertIn("data['cacheControl']='no-store'",block)
        self.assertIn("data['secretValuesIncluded']=True",block)

    def test_raw_read_scopes_are_not_granted_to_viewer_or_developer(self):
        registry=REGISTRY.read_text()
        viewer=registry[registry.index("'viewer':"):registry.index("'developer':")]
        developer=registry[registry.index("'developer':"):registry.index("'maintainer':")]
        maintainer=registry[registry.index("'maintainer':"):registry.index("'release-manager':")]
        self.assertNotIn('PROJECT_SECRET_VALUE_READ_SCOPES',viewer)
        self.assertNotIn('PROJECT_SECRET_VALUE_READ_SCOPES',developer)
        self.assertIn('PROJECT_SECRET_VALUE_READ_SCOPES',maintainer)

    def test_actionable_errors_never_echo_supplied_secret_value(self):
        tool='project.environment.secret.stage';args={'slug':'demo','environment':'preview','name':'DATABASE_URL','secret_value':'very-sensitive-value','extra':True}
        with self.assertRaises(self.module.ToolInputError) as captured:self.module.validate_tool_arguments(tool,args)
        data=self.module.enrich_tool_error(tool,args,captured.exception.payload,captured.exception.payload['message'])
        rendered=json.dumps(data);self.assertNotIn('very-sensitive-value',rendered);self.assertIn('secret_value',data['receivedFields']);self.assertEqual(data['usage']['parameters']['secret_value']['type'],'string')


if __name__=='__main__':unittest.main()
