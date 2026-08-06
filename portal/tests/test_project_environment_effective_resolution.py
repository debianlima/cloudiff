from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from portal.tests.test_project_environment_controller import load_module


class ProjectEnvironmentEffectiveResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_module(Path(self.temp.name))

    def tearDown(self):self.temp.cleanup()

    def apply(self,changes,revision=0,environment='preview'):
        plan=self.module.plan_change('demo',environment,changes,revision,'alice',900)
        return self.module.apply_plan('demo',plan['planDigest'],revision,'alice')

    def test_effective_internal_separates_public_and_secret_build_runtime_values(self):
        self.apply([
          {'name':'BUILD_LABEL','service':'api','value':'release-a','definition':{'buildTime':True,'runtime':False,'restartRequired':False}},
          {'name':'LOG_LEVEL','service':'api','value':'info','definition':{'buildTime':False,'runtime':True,'restartRequired':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-preview','definition':{'secret':True,'required':True,'runtime':True}},
          {'name':'GLOBAL_REQUIRED','value':'configured','definition':{'required':True,'runtime':True}},
        ])
        result=self.module.effective_internal('demo','preview','api')
        self.assertTrue(result['ok']);self.assertTrue(result['valid'])
        self.assertEqual(result['publicBuildEnvironment']['api']['BUILD_LABEL'],'release-a')
        self.assertEqual(result['publicRuntimeEnvironment']['api']['LOG_LEVEL'],'info')
        self.assertEqual(result['publicRuntimeEnvironment']['api']['GLOBAL_REQUIRED'],'configured')
        self.assertEqual(result['secretRuntimeReferences']['api']['DATABASE_URL'],'vault://project/demo/database-preview')
        self.assertNotIn('DATABASE_URL',result['publicRuntimeEnvironment']['api'])
        self.assertFalse(result['secretValuesIncluded'])
        serialized=json.dumps(result)
        self.assertNotIn('password',serialized.lower())
        self.assertEqual(len(result['buildEnvironmentDigest']),64)
        self.assertEqual(len(result['runtimeEnvironmentDigest']),64)
        self.assertEqual(len(result['environmentDigest']),64)

    def test_sanitized_summary_contains_names_and_digests_but_no_values_or_references(self):
        self.apply([
          {'name':'PUBLIC_API_URL','service':'web','value':'https://api.example.test','definition':{'runtime':True,'exposeToClient':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-preview','definition':{'secret':True,'required':True,'runtime':True}},
          {'name':'GLOBAL_REQUIRED','value':'configured','definition':{'required':True,'runtime':True}},
        ])
        summary=self.module.effective_summary('demo','preview')
        self.assertTrue(summary['ok']);self.assertTrue(summary['valid'])
        self.assertIn('PUBLIC_API_URL',summary['publicRuntimeNames']['web'])
        self.assertIn('DATABASE_URL',summary['secretRuntimeNames']['api'])
        self.assertFalse(summary['secretValuesIncluded']);self.assertFalse(summary['secretReferencesIncluded'])
        serialized=json.dumps(summary)
        self.assertNotIn('https://api.example.test',serialized)
        self.assertNotIn('vault://',serialized)

    def test_service_binding_overrides_project_binding(self):
        self.apply([
          {'name':'LOG_LEVEL','value':'warning','definition':{'runtime':True}},
          {'name':'LOG_LEVEL','service':'api','value':'debug','definition':{'runtime':True}},
          {'name':'GLOBAL_REQUIRED','value':'configured','definition':{'required':True,'runtime':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-preview','definition':{'secret':True,'required':True,'runtime':True}},
        ])
        api=self.module.effective_internal('demo','preview','api')
        web=self.module.effective_internal('demo','preview','web')
        self.assertEqual(api['publicRuntimeEnvironment']['api']['LOG_LEVEL'],'debug')
        self.assertEqual(web['publicRuntimeEnvironment']['web']['LOG_LEVEL'],'warning')

    def test_missing_required_variables_block_effective_configuration(self):
        result=self.module.effective_internal('demo','production','api')
        self.assertFalse(result['valid'])
        missing={(item['service'],item['name']) for item in result['missingRequired']}
        self.assertIn(('api','DATABASE_URL'),missing)
        self.assertIn(('api','GLOBAL_REQUIRED'),missing)

    def test_public_value_and_secret_reference_changes_modify_runtime_digest(self):
        self.apply([
          {'name':'GLOBAL_REQUIRED','value':'one','definition':{'required':True,'runtime':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/db-one','definition':{'secret':True,'required':True,'runtime':True}},
        ])
        first=self.module.effective_internal('demo','preview','api')
        self.apply([
          {'name':'GLOBAL_REQUIRED','value':'two','definition':{'required':True,'runtime':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/db-two','definition':{'secret':True,'required':True,'runtime':True}},
        ],1)
        second=self.module.effective_internal('demo','preview','api')
        self.assertNotEqual(first['runtimeEnvironmentDigest'],second['runtimeEnvironmentDigest'])
        self.assertNotEqual(first['environmentDigest'],second['environmentDigest'])

    def test_unknown_service_is_rejected(self):
        with self.assertRaisesRegex(LookupError,'service_not_found'):
            self.module.effective_internal('demo','preview','unknown')


if __name__=='__main__':unittest.main()
