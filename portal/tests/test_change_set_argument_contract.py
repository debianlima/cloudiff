from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'


def load_module():
    spec=importlib.util.spec_from_file_location('mcp_change_set_argument_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class ChangeSetArgumentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=load_module()
        cls.required={'slug','workspace_id','change_set_digest'}
        cls.example={'slug':'demo','workspace_id':'ws_'+'1'*24,'change_set_digest':'a'*64}

    def normalize(self,raw):
        return self.module.canonical_tool_arguments(raw,self.required,self.required,self.example,'mcp#forgejo-change-set',aliases={'project_slug':'slug'})

    def test_direct_arguments_are_preserved(self):
        args,meta=self.normalize(dict(self.example))
        self.assertEqual(args,self.example)
        self.assertEqual(meta,{'wrappersRemoved':[],'aliasesApplied':{}})

    def test_common_wrappers_are_unwrapped(self):
        for raw,expected in (
            ({'arguments':dict(self.example)},['arguments']),
            ({'payload':{'arguments':dict(self.example)}},['payload','arguments']),
            ({'request':dict(self.example),'metadata':{}},['request']),
        ):
            args,meta=self.normalize(raw)
            self.assertEqual(args,self.example)
            self.assertEqual(meta['wrappersRemoved'],expected)

    def test_project_slug_alias_is_normalized(self):
        raw={**self.example,'project_slug':self.example['slug']};raw.pop('slug')
        args,meta=self.normalize(raw)
        self.assertEqual(args['slug'],'demo')
        self.assertEqual(meta['aliasesApplied'],{'project_slug':'slug'})

    def test_missing_field_error_is_actionable(self):
        raw={'workspace_id':self.example['workspace_id'],'change_set_digest':self.example['change_set_digest']}
        with self.assertRaises(self.module.ToolInputError) as captured:
            self.normalize(raw)
        payload=captured.exception.payload
        self.assertEqual(payload['code'],'missing_field')
        self.assertEqual(payload['field'],'slug')
        self.assertEqual(payload['path'],'$.slug')
        self.assertEqual(payload['receivedFields'],['change_set_digest','workspace_id'])
        self.assertEqual(payload['example'],self.example)

    def test_unknown_field_error_lists_allowed_fields(self):
        with self.assertRaises(self.module.ToolInputError) as captured:
            self.normalize({**self.example,'extra':True})
        payload=captured.exception.payload
        self.assertEqual(payload['code'],'unknown_field')
        self.assertEqual(payload['field'],'extra')
        self.assertEqual(set(payload['allowedFields']),self.required)

    def test_public_schema_and_json_rpc_error_expose_complete_contract(self):
        tool=next(item for item in self.module.TOOLS if item['name']=='forgejo.proposal.change-set.plan')
        schema=tool['inputSchema']
        self.assertEqual(set(schema['required']),self.required)
        self.assertEqual(set(schema['properties']),self.required)
        self.assertFalse(schema['additionalProperties'])
        self.assertTrue(schema['examples'])
        source=SOURCE.read_text();start=source.index('except ToolInputError as e:');end=source.index('except ToolStateError as e:',start);handler=source[start:end]
        self.assertIn('enrich_tool_error(',handler)
        self.assertIn("'data':_data",handler)
        self.assertIn("'code':-32602",handler)
        self.assertIn('args,input_wrappers=_unwrap_tool_arguments(raw_args)',source);self.assertIn('auth_args=args',source)


if __name__=='__main__':unittest.main()
