from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
SCHEMA=ROOT/'components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json'


def load_module(root: Path):
    state=root/'config.db';control=root/'control.db'
    connection=sqlite3.connect(control)
    connection.execute('create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text)')
    connection.execute("insert into projects values('p1','demo','Demo','alice','tenant-demo','active')")
    connection.commit();connection.close()
    os.environ['CLOUDIF_PROJECT_CONFIG_DB']=str(state)
    os.environ['CLOUDIF_PROJECT_SNAPSHOT_DB']=str(control)
    os.environ['CLOUDIF_PROJECT_MANIFEST_SCHEMA']=str(SCHEMA)
    name='project_config_environment_toolchain_test_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);module.init_db();return module


class ProjectManifestEnvironmentToolchainV1Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_module(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_declarative_project_and_service_environment_is_normalized_compatibly(self):
        result=self.module.validate_manifest({
            'version':1,
            'project':{'type':'multi-service','primaryService':'web'},
            'environment':{
                'APP_NAME':{'value':'demo','required':True,'secret':False},
                'LOG_LEVEL':{'default':'info','allowedValues':['debug','info','warning'],'restartRequired':True},
                'JWT_SECRET':{'required':True,'secret':True,'description':'JWT signing material'},
            },
            'services':{
                'web':{'runtime':'static','publish':'dist','environment':{
                    'PUBLIC_API_URL':{'required':True,'secret':False,'exposeToClient':True},
                }},
                'api':{'runtime':'node','version':'24','start':['node','server.js'],'port':3000,'environment':{
                    'JWT_SECRET':{'required':True,'secret':True},
                    'APP_ENV':{'default':'production','secret':False},
                }},
            },
        })
        self.assertTrue(result.valid,result.errors)
        environment=result.normalized['environment']
        self.assertEqual(environment['variables'],{'APP_NAME':'demo','LOG_LEVEL':'info'})
        self.assertIn('JWT_SECRET',environment['required'])
        self.assertTrue(environment['definitions']['JWT_SECRET']['secret'])
        self.assertNotIn('value',environment['definitions']['JWT_SECRET'])
        self.assertEqual(result.normalized['services']['api']['environment']['variables']['APP_ENV'],'production')
        self.assertIn('JWT_SECRET',result.normalized['services']['api']['environment']['required'])
        self.assertTrue(result.normalized['services']['web']['environment']['definitions']['PUBLIC_API_URL']['exposeToClient'])

    def test_environment_overlays_are_separate_and_service_scoped(self):
        result=self.module.validate_manifest({
            'version':1,'services':{'api':{'runtime':'node','version':'24','start':['node','server.js'],'port':3000}},
            'environments':{
                'preview':{'environment':{'LOG_LEVEL':{'value':'debug'}}},
                'production':{
                    'environment':{'LOG_LEVEL':{'value':'warning'}},
                    'services':{'api':{'environment':{'DATABASE_URL':{'required':True,'secret':True}}}},
                },
            },
        })
        self.assertTrue(result.valid,result.errors)
        self.assertEqual(result.normalized['environments']['preview']['environment']['variables']['LOG_LEVEL'],'debug')
        prod_api=result.normalized['environments']['production']['services']['api']['environment']
        self.assertIn('DATABASE_URL',prod_api['required'])
        self.assertNotIn('DATABASE_URL',prod_api['variables'])

    def test_secret_value_and_client_exposure_are_rejected(self):
        secret_value=self.module.validate_manifest({'version':1,'runtime':'static','environment':{
            'JWT_SECRET':{'secret':True,'value':'never-store-this'},
        }})
        self.assertFalse(secret_value.valid)
        self.assertIn('secret_value_not_allowed',{item['code'] for item in secret_value.errors})
        exposed=self.module.validate_manifest({'version':1,'runtime':'static','environment':{
            'PUBLIC_SECRET':{'secret':True,'required':True,'exposeToClient':True},
        }})
        self.assertFalse(exposed.valid)
        self.assertTrue({'secret_client_exposure_forbidden','schema_validation_failed','invalid_field_value'} & {item['code'] for item in exposed.errors})

    def test_toolchain_packages_tools_and_provision_are_canonical_and_digest_bound(self):
        manifest={
            'version':1,'runtime':'node',
            'toolchain':{
                'base':{'runtime':'node','version':'24'},
                'architecture':'amd64',
                'systemPackages':['git',{'name':'imagemagick','version':'6.9','source':'catalog'}],
                'tools':[{'name':'pnpm','version':'10','installMethod':'corepack'}],
                'provision':{'script':'scripts/cloudiff-provision.sh','timeoutSeconds':600,'network':'restricted'},
            },
        }
        first=self.module.validate_manifest(manifest)
        self.assertTrue(first.valid,first.errors)
        toolchain=first.normalized['toolchain']
        self.assertEqual(toolchain['systemPackages'][0]['name'],'git')
        self.assertEqual(toolchain['tools'][0]['name'],'pnpm')
        self.assertEqual(toolchain['provision']['network'],{'mode':'restricted','domains':[]})
        changed=self.module.validate_manifest({**manifest,'toolchain':{**manifest['toolchain'],'provision':{**manifest['toolchain']['provision'],'timeoutSeconds':601}}})
        self.assertTrue(changed.valid,changed.errors)
        self.assertNotEqual(first.toolchain_digest,changed.toolchain_digest)
        self.assertNotEqual(first.config_digest,changed.config_digest)

    def test_approved_domains_require_explicit_domain_list(self):
        invalid=self.module.validate_manifest({'version':1,'runtime':'static','toolchain':{
            'provision':{'script':'scripts/cloudiff-provision.sh','network':{'mode':'approved-domains'}},
        }})
        self.assertFalse(invalid.valid)
        self.assertIn('required_field_missing',{item['code'] for item in invalid.errors})
        valid=self.module.validate_manifest({'version':1,'runtime':'static','toolchain':{
            'provision':{'script':'scripts/cloudiff-provision.sh','network':{'mode':'approved-domains','domains':['registry.npmjs.org']}},
        }})
        self.assertTrue(valid.valid,valid.errors)

    def test_old_top_level_names_return_migration_examples(self):
        cases=(
            ({'version':1,'runtime':'static','env':{}},'env','environment'),
            ({'version':1,'runtime':'static','systemPackages':['git']},'systemPackages','toolchain.systemPackages'),
            ({'version':1,'runtime':'static','provision':{'script':'x.sh'}},'provision','toolchain.provision'),
        )
        for manifest,field,suggestion in cases:
            result=self.module.validate_manifest(manifest)
            self.assertFalse(result.valid)
            issue=next(item for item in result.errors if item['field']==field)
            self.assertEqual(issue['code'],'unknown_field')
            self.assertIn(suggestion,issue['message'])
            self.assertIn('example',issue)

    def test_simple_legacy_manifest_stays_valid(self):
        result=self.module.validate_manifest({'version':1,'runtime':'static','environment':{'variables':{'PUBLIC_NAME':'demo'},'required':{}}})
        self.assertTrue(result.valid,result.errors)
        self.assertEqual(result.normalized['environment']['variables']['PUBLIC_NAME'],'demo')
        self.assertIn('PUBLIC_NAME',result.normalized['environment']['definitions'])


if __name__=='__main__':unittest.main()
