from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'


def load_gateway():
    spec=importlib.util.spec_from_file_location('mcp_actionable_errors_test',GATEWAY);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class MCPActionableErrorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.module=load_gateway()

    def error(self,tool,args):
        try:self.module.validate_tool_arguments(tool,args)
        except self.module.ToolInputError as exc:return self.module.enrich_tool_error(tool,args,exc.payload,exc.payload.get('message'))
        self.fail('arguments unexpectedly valid')

    def assert_usage(self,payload,tool):
        self.assertEqual(payload['tool'],tool);self.assertIn('receivedFields',payload);usage=payload['usage'];self.assertTrue(usage['known']);self.assertEqual(usage['tool'],tool)
        self.assertIn('requiredParameters',usage);self.assertIn('optionalParameters',usage);self.assertIn('parameters',usage);self.assertIn('minimumExample',usage);self.assertIn('completeExample',usage)

    def test_missing_field_returns_usage_required_optional_types_and_examples(self):
        tool='forgejo.propose-edit.plan';payload=self.error(tool,{'slug':'demo'})
        self.assertEqual(payload['code'],'missing_field');self.assertTrue(payload['field']);self.assert_usage(payload,tool)
        usage=payload['usage'];self.assertIn('slug',usage['requiredParameters']);self.assertEqual(usage['parameters']['slug']['type'],'string');self.assertTrue(usage['minimumExample'])

    def test_wrong_type_returns_expected_parameter_contract(self):
        tool='runtime.plan';payload=self.error(tool,{'framework':123})
        self.assertEqual(payload['code'],'invalid_field_type');self.assertEqual(payload['field'],'framework');self.assert_usage(payload,tool)
        self.assertEqual(payload['usage']['parameters']['framework']['type'],'string');self.assertIn('allowedValues',payload['usage']['parameters']['framework'])

    def test_invalid_enum_and_pattern_are_actionable(self):
        enum_payload=self.error('runtime.plan',{'framework':'not-a-framework'});self.assertEqual(enum_payload['code'],'invalid_field_value');self.assert_usage(enum_payload,'runtime.plan')
        pattern_payload=self.error('project.get',{'slug':''});self.assertIn(pattern_payload['code'],{'field_limit_violation','invalid_field_format'});self.assert_usage(pattern_payload,'project.get')

    def test_unknown_field_lists_contract_without_echoing_values(self):
        payload=self.error('project.get',{'slug':'demo','password':'super-secret-value'})
        self.assertEqual(payload['code'],'unknown_field');self.assertEqual(payload['field'],'password');self.assertEqual(payload['receivedFields'],['password','slug']);self.assert_usage(payload,'project.get')
        serialized=str(payload);self.assertNotIn('super-secret-value',serialized)

    def test_environment_incomplete_change_points_to_nested_field_and_usage(self):
        payload=self.error('project.environment.validate',{'slug':'demo','environment':'preview','changes':[{}]})
        self.assertEqual(payload['code'],'missing_field');self.assertEqual(payload['field'],'changes.0.name');self.assert_usage(payload,'project.environment.validate')
        changes=payload['usage']['parameters']['changes'];self.assertEqual(changes['type'],'array');self.assertEqual(changes['items']['type'],'object');self.assertIn('name',changes['items']['properties'])

    def test_toolchain_revision_zero_is_bootstrap_sentinel_only_for_side_effect_free_tools(self):
        by_name={item['name']:item for item in self.module.TOOLS}
        for name in ('project.toolchain.validate','project.toolchain.plan','project.toolchain.build.plan'):
            self.assertEqual(by_name[name]['inputSchema']['properties']['expected_revision']['minimum'],0)
            self.module.validate_tool_arguments(name,{'slug':'demo','expected_revision':0})
        for name in ('approval.request-toolchain-build','project.toolchain.build.execute'):
            self.assertEqual(by_name[name]['inputSchema']['properties']['expected_revision']['minimum'],1)

    def test_unconfigured_toolchain_state_is_semantic_not_generic_argument_error(self):
        with patch.object(self.module,'project_config_call',return_value=(200,{'ok':True,'configured':False,'currentRevision':0})):
            with self.assertRaises(self.module.ToolStateError) as captured:self.module.toolchain_configuration_revision('demo',0)
        payload=captured.exception.payload;self.assertEqual(payload['code'],'toolchain_not_configured');self.assertEqual(payload['currentRevision'],0);self.assertEqual(payload['minimumRevision'],1);self.assertIn('cloudiff.yaml',payload['nextAction'])

    def test_legacy_value_error_is_enriched_from_public_schema(self):
        payload=self.module.enrich_tool_error('forgejo.propose-edit.plan',{'slug':'demo'},message='argumentos inválidos')
        self.assertEqual(payload['code'],'invalid_arguments');self.assertEqual(payload['message'],'argumentos inválidos');self.assert_usage(payload,'forgejo.propose-edit.plan')
        self.assertIn('path',payload['usage']['requiredParameters'])

    def test_gateway_validates_before_tool_dispatch_and_enriches_both_error_paths(self):
        source=GATEWAY.read_text();self.assertIn('validate_tool_arguments(tool,args)',source);self.assertIn('enrich_tool_error(_tool_name,_args,e.payload',source);self.assertIn('enrich_tool_error(_tool_name,_args,{},_message)',source)

    def test_all_published_examples_validate_against_their_tool_schema(self):
        import jsonschema
        for tool in self.module.TOOLS:
            usage=self.module.tool_usage(tool['name'])
            validator=jsonschema.Draft202012Validator(tool.get('inputSchema') or {})
            minimum=list(validator.iter_errors(usage['minimumExample']))
            complete=list(validator.iter_errors(usage['completeExample']))
            self.assertEqual(minimum,[],f"minimum example invalid for {tool['name']}: {minimum}")
            self.assertEqual(complete,[],f"complete example invalid for {tool['name']}: {complete}")


if __name__=='__main__':unittest.main()
