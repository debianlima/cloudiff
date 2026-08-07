from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ARTIFACT=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py'
BROKER=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'
CONTROLLER=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
ENVIRONMENT=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py'


def load_artifact():
    spec=importlib.util.spec_from_file_location('effective_environment_artifact_test',ARTIFACT)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class EffectiveEnvironmentBuildContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.artifact=load_artifact();cls.source=ARTIFACT.read_text()

    def request(self):
        return {
          'services':[{'name':'api'}],
          'effectiveEnvironment':{
            'projectSlug':'demo','environment':'preview','revision':2,
            'publicBuildEnvironment':{'api':{'PUBLIC_VERSION':'42','FEATURE_FLAG':True}},
            'publicRuntimeEnvironment':{'api':{'LOG_LEVEL':'info'}},
            'secretBuildReferences':{'api':{}},
            'secretRuntimeReferences':{'api':{'DATABASE_URL':'vault://project/demo/database-preview'}},
            'missingRequired':[],
            'buildEnvironmentDigest':'1'*64,'runtimeEnvironmentDigest':'2'*64,'environmentDigest':'3'*64,
            'secretValuesIncluded':False,
          },
        }

    def test_service_contract_returns_public_values_and_only_opaque_secret_references(self):
        result=self.artifact.service_effective_environment(self.request(),'api')
        self.assertEqual(result['publicBuildEnvironment']['PUBLIC_VERSION'],'42')
        self.assertEqual(result['publicBuildEnvironment']['FEATURE_FLAG'],'true')
        self.assertEqual(result['publicRuntimeEnvironment']['LOG_LEVEL'],'info')
        self.assertEqual(result['secretRuntimeReferences']['DATABASE_URL'],'vault://project/demo/database-preview')
        self.assertFalse(result['secretValuesIncluded'])

    def test_build_secret_references_fail_closed(self):
        request=self.request();request['effectiveEnvironment']['secretBuildReferences']['api']={'NPM_TOKEN':'vault://project/demo/npm-token'}
        with self.assertRaises(self.artifact.ArtifactError) as captured:
            self.artifact.service_effective_environment(request,'api')
        self.assertEqual(captured.exception.code,'build_secret_injection_unavailable')
        self.assertIn('Segredos de build',captured.exception.message)

    def test_invalid_secret_reference_and_complex_public_value_are_rejected(self):
        request=self.request();request['effectiveEnvironment']['secretRuntimeReferences']['api']['DATABASE_URL']='not-a-reference'
        with self.assertRaises(self.artifact.ArtifactError) as captured:
            self.artifact.service_effective_environment(request,'api')
        self.assertEqual(captured.exception.code,'invalid_secret_reference')
        self.assertIn('Referência de segredo',captured.exception.message)
        request=self.request();request['effectiveEnvironment']['publicBuildEnvironment']['api']['OBJECT']={'unsafe':True}
        with self.assertRaises(self.artifact.ArtifactError) as captured:
            self.artifact.service_effective_environment(request,'api')
        self.assertEqual(captured.exception.code,'invalid_public_environment_value')
        self.assertIn('escalares',captured.exception.message)

    def test_application_dockerfile_uses_only_public_build_args(self):
        start=self.source.index('def build_service_artifact(')
        end=self.source.index('\ndef ',start+5)
        block=self.source[start:end]
        self.assertIn("dockerfile.insert(1,'ARG '+name)",block)
        self.assertIn("build_arguments.extend(['--build-arg',name+'='+value])",block)
        self.assertIn("['docker', 'build', *build_arguments,",block)
        self.assertIn('org.cloudiff.environment-digest=',block)
        self.assertIn("'publicBuildNames':sorted(environment_contract['publicBuildEnvironment'])",block)
        self.assertIn("'publicRuntimeNames':sorted(environment_contract['publicRuntimeEnvironment'])",block)
        self.assertIn("'secretRuntimeNames':sorted(environment_contract['secretRuntimeReferences'])",block)
        self.assertIn("'secretReferencesIncluded':False",block)
        self.assertNotIn('secretRuntimeReferences.items()',block)
        self.assertNotIn('secretBuildReferences.items()',block)

    def test_broker_plan_uses_digests_and_sanitized_summary_only(self):
        source=BROKER.read_text()
        self.assertIn('project_effective_environment(slug,environment)',source)
        self.assertIn('project_effective_environment_internal(slug,environment)',source)
        self.assertIn("'environment_digests':{'build':environment_summary.get('buildEnvironmentDigest')",source)
        self.assertIn("'effective_environment':environment_summary",source)
        self.assertIn("if include_internal:response['_internal_effective_environment']=project_effective_environment_internal(slug,environment)",source)
        self.assertIn("'effectiveEnvironment':internal_effective_environment",source)
        self.assertIn('build-secret-injection-unavailable',source)
        self.assertIn('missing-variable',source)

    def test_controller_has_separate_sanitized_and_internal_routes(self):
        controller=CONTROLLER.read_text();environment=ENVIRONMENT.read_text()
        self.assertIn('history|missing|effective|effective-internal',controller)
        self.assertIn('project_environment.effective_summary',controller)
        self.assertIn('project_environment.effective_internal',controller)
        self.assertIn("'secretReferencesIncluded': False",environment)
        self.assertIn("'secretValuesIncluded': False",environment)


if __name__=='__main__':unittest.main()
