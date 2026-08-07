from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
BROKER=ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py'
BUILD=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'


def load_gateway():
    spec=importlib.util.spec_from_file_location('build_bound_gateway_contract',GATEWAY)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def runtime_executor_path()->Path:
    candidates=[]
    for path in (ROOT/'components/runtime').rglob('*.py'):
        source=path.read_text(errors='ignore')
        if '_validated_runtime_configuration' in source and '_apply_runtime_configuration' in source:
            candidates.append(path)
    assert len(candidates)==1,candidates
    return candidates[0]


class BuildBoundPreviewDeploymentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway=load_gateway();cls.source=GATEWAY.read_text();cls.broker=BROKER.read_text();cls.runtime_path=runtime_executor_path();cls.runtime=cls.runtime_path.read_text()

    def test_persistent_tools_require_exact_build_job(self):
        names={
          'preview.multiservice.plan','preview.multiservice.create',
          'deployment.multiservice.plan','approval.request-multiservice-deployment','deployment.multiservice.execute',
        }
        tools={item['name']:item for item in self.gateway.TOOLS}
        for name in names:
            self.assertIn(name,tools)
            schema=tools[name]['inputSchema']
            self.assertIn('build_job_id',schema['properties'],name)
            self.assertIn('build_job_id',schema.get('required') or [],name)
            self.assertEqual(schema['properties']['build_job_id']['pattern'],'^build_[a-f0-9]{24}$')
            self.assertFalse(schema.get('additionalProperties',True),name)

    def test_environment_enum_was_not_modified_by_handler_migration(self):
        self.assertEqual(self.gateway.ENVIRONMENT_NAME_SCHEMA['enum'],['development','preview','homologation','production'])
        self.assertNotIn('build_job_id',self.gateway.ENVIRONMENT_NAME_SCHEMA['enum'])
        self.assertNotIn("{'development','preview','homologation','production','build_job_id'}",self.source)

    def _branch(self,tool:str)->str:
        patterns=[
          re.compile(r"(?m)^\s*elif name=='"+re.escape(tool)+r"':"),
          re.compile(r"(?m)^\s*elif name in \{[^\n]*'"+re.escape(tool)+r"'[^\n]*\}:")
        ]
        match=next((pattern.search(self.source) for pattern in patterns if pattern.search(self.source)),None)
        self.assertIsNotNone(match,tool)
        next_match=re.search(r'(?m)^\s*elif name',self.source[match.end():]);end=match.end()+next_match.start() if next_match else len(self.source)
        return self.source[match.start():end]

    def test_handlers_validate_and_forward_build_job(self):
        for tool in ('preview.multiservice.plan','preview.multiservice.create','deployment.multiservice.plan','approval.request-multiservice-deployment','deployment.multiservice.execute'):
            block=self._branch(tool)
            self.assertIn("build_job_id=str(args.get('build_job_id') or '').strip()",block,tool)
            self.assertIn("re.fullmatch(r'build_[a-f0-9]{24}',build_job_id)",block,tool)
            if tool=='preview.multiservice.plan':
                self.assertIn('multiservice_preview_plan(build_job_id',block)
            else:
                self.assertIn("'build_job_id':build_job_id",block,tool)

    def test_deployment_approval_is_bound_to_build_job(self):
        self.assertIn("'build_job_id':plan.get('build_job_id')",self.source)
        execute=self._branch('deployment.multiservice.execute')
        self.assertIn("metadata.get('build_job_id')==build_job_id",execute)
        self.assertIn('approval_binding_mismatch',execute)

    def test_build_broker_internal_runtime_contract_is_not_an_mcp_tool(self):
        self.assertIn('def multiservice_runtime_config(',BUILD.read_text())
        self.assertIn('/runtime-config',BUILD.read_text())
        names={item['name'] for item in self.gateway.TOOLS}
        self.assertNotIn('build.multiservice.runtime-config',names)
        self.assertNotIn('/runtime-config',self.source)

    def test_deployment_plan_is_sanitized_and_secret_refs_block(self):
        for marker in (
          'def _build_runtime_configuration(',
          'def _deployment_runtime_summary(',
          'def multiservice_plan(payload,include_internal=False):',
          "'build-job-required'",
          "'build-environment-mismatch'",
          "'build-config-digest-mismatch'",
          "'secret-resolution-unavailable'",
          "'secretValuesIncluded':False,'secretReferencesIncluded':False",
          "base['_internal_runtime_configuration']=runtime_configuration",
        ):self.assertIn(marker,self.broker)
        start=self.broker.index('def _deployment_runtime_summary(');end=self.broker.index('def _deployment_routes(',start);block=self.broker[start:end]
        return_block=block[block.rindex('return {'):]
        self.assertNotIn('secretRuntimeReferences',return_block)
        self.assertNotIn('publicRuntimeEnvironment',return_block)
        self.assertIn("'secretNames':secret_names",return_block)
        self.assertIn("'variableNames':public_names",return_block)

    def test_runtime_executor_fails_closed_before_docker_and_injects_public_only(self):
        for marker in (
          'def _validated_runtime_configuration(',
          "raise ValueError('secret_resolution_unavailable')",
          'def _apply_runtime_configuration(',
          "service['environment']=merged",
          "'cloudiff.environment.digest'",
          "'cloudiff.runtime-environment.digest'",
          "'cloudiff.build.job'",
          'runtime_configuration=_validated_runtime_configuration',
        ):self.assertIn(marker,self.runtime)
        tree=ast.parse(self.runtime)
        target=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and any(isinstance(child,ast.Assign) and ast.get_source_segment(self.runtime,child) and 'runtime_configuration=_validated_runtime_configuration' in ast.get_source_segment(self.runtime,child).replace(' ','') for child in ast.walk(node)))
        segment=ast.get_source_segment(self.runtime,target) or ''
        self.assertLess(segment.index('runtime_configuration=_validated_runtime_configuration'),segment.lower().index('docker'))
        self.assertNotIn('secretRuntimeReferences.items()',segment)


if __name__=='__main__':unittest.main()
