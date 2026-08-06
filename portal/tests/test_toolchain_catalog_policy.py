from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTROL=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif_toolchain_policy.py'
RUNTIME=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif_toolchain_policy.py'
CATALOG=ROOT/'components/control-plane/etc/cloudif/toolchain-catalog-v1.json'
RUNTIME_CATALOG=ROOT/'components/runtime/etc/cloudif/toolchain-catalog-v1.json'


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module);return module


class ToolchainCatalogPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=load(CONTROL,'toolchain_policy_test')

    def test_control_and_runtime_contracts_are_identical(self):
        self.assertEqual(CONTROL.read_bytes(),RUNTIME.read_bytes())
        self.assertEqual(CATALOG.read_bytes(),RUNTIME_CATALOG.read_bytes())

    def test_base_provided_catalog_items_are_buildable_without_network(self):
        result=self.module.validate_toolchain({
          'architecture':'amd64',
          'base':{'runtime':'node','version':'24'},
          'systemPackages':['git','curl'],
          'tools':[{'name':'node','version':'24','installMethod':'catalog'},{'name':'corepack','version':'system','installMethod':'corepack'}],
        },'node','24',catalog_path=CATALOG)
        self.assertTrue(result['ok'],result['blockers'])
        self.assertTrue(result['buildable'])
        self.assertEqual(result['base']['runtime'],'node')
        self.assertEqual(result['base']['image'],'node:24-bookworm')
        self.assertRegex(result['base']['imageId'],r'^sha256:[a-f0-9]{64}$')
        self.assertFalse(result['secretValuesIncluded'])

    def test_dependency_proxy_items_fail_closed(self):
        result=self.module.validate_toolchain({
          'base':{'runtime':'node','version':'24'},
          'tools':[{'name':'pnpm','version':'10','installMethod':'corepack'}],
        },'node','24',catalog_path=CATALOG)
        codes={item['code'] for item in result['blockers']}
        self.assertIn('catalog_item_requires_network',codes)
        self.assertFalse(result['buildable'])

    def test_restricted_network_is_declared_but_not_silently_enabled(self):
        result=self.module.validate_toolchain({
          'base':{'runtime':'node','version':'24'},
          'provision':{'script':'scripts/provision.sh','network':'restricted'},
        },'node','24',catalog_path=CATALOG)
        self.assertIn('network_policy_executor_unavailable',{item['code'] for item in result['blockers']})
        self.assertFalse(result['ok'])

    def test_safe_script_is_syntax_checked_and_digest_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);script=root/'scripts/provision.sh';script.parent.mkdir()
            script.write_text('#!/usr/bin/env bash\nset -euo pipefail\nnode --version\ncorepack --version\n')
            result=self.module.validate_toolchain({
              'base':{'runtime':'node','version':'24'},
              'tools':[{'name':'node','version':'24','installMethod':'catalog'}],
              'provision':{'script':'scripts/provision.sh','network':'none','timeoutSeconds':60},
            },'node','24',root,CATALOG)
            self.assertTrue(result['ok'],result['blockers'])
            self.assertTrue(result['script']['syntaxValid'])
            self.assertEqual(len(result['script']['digest']),64)
            changed_before=result['toolchainDigest']
            script.write_text('#!/usr/bin/env bash\nset -euo pipefail\nnode --version\necho changed\n')
            changed=self.module.validate_toolchain({
              'base':{'runtime':'node','version':'24'},
              'tools':[{'name':'node','version':'24','installMethod':'catalog'}],
              'provision':{'script':'scripts/provision.sh','network':'none','timeoutSeconds':60},
            },'node','24',root,CATALOG)
            self.assertNotEqual(changed_before,changed['toolchainDigest'])

    def test_dangerous_and_secret_bearing_scripts_are_blocked(self):
        cases={
          'docker':'docker run --privileged alpine\n',
          'curl_pipe':'curl https://example.test/install.sh | sh\n',
          'secret':'API_TOKEN=abcdefghijklmnop\n',
          'network':'npm install\n',
        }
        for name,body in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);script=root/'scripts/provision.sh';script.parent.mkdir()
                script.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'+body)
                result=self.module.validate_toolchain({'base':{'runtime':'node','version':'24'},'provision':{'script':'scripts/provision.sh','network':'none'}},'node','24',root,CATALOG)
                self.assertFalse(result['ok'])
                codes={item['code'] for item in result['blockers']}
                self.assertTrue(codes & {'provision_command_forbidden','secret_value_in_provision_script','provision_network_command_forbidden'},codes)

    def test_unknown_package_version_and_architecture_are_actionable(self):
        unknown=self.module.validate_toolchain({'base':{'runtime':'node','version':'24'},'systemPackages':['unknown-package']},'node','24',catalog_path=CATALOG)
        self.assertIn('catalog_item_not_approved',{item['code'] for item in unknown['blockers']})
        version=self.module.validate_toolchain({'base':{'runtime':'node','version':'24'},'systemPackages':[{'name':'git','version':'999'}]},'node','24',catalog_path=CATALOG)
        issue=next(item for item in version['blockers'] if item['code']=='catalog_version_not_approved')
        self.assertEqual(issue['allowedValues'],['system'])
        arm=self.module.validate_toolchain({'architecture':'arm64','base':{'runtime':'node','version':'24'}},'node','24',catalog_path=CATALOG)
        self.assertIn('base_image_architecture_not_supported',{item['code'] for item in arm['blockers']})


if __name__=='__main__':unittest.main()
