from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTROLLER=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
STORE=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_secret_store.py'


class ProjectSecretControllerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller=CONTROLLER.read_text();cls.store=STORE.read_text()

    def test_secret_store_is_initialized_with_controller(self):
        self.assertIn('import cloudif_project_secret_store as project_secret_store',self.controller)
        self.assertIn('project_secret_store.init_db()',self.controller)
        self.assertIn("SECRET_RESOLVER_TOKEN=os.environ.get('CLOUDIF_SECRET_RESOLVER_TOKEN','')",self.controller)

    def test_public_metadata_routes_never_resolve_values(self):
        self.assertIn('/environment/secrets(?:/(history))?',self.controller)
        self.assertIn('project_secret_store.list_secrets',self.controller)
        self.assertIn('project_secret_store.history',self.controller)
        get_start=self.controller.index("secret_match = re.fullmatch(r'/v1/projects/",self.controller.index('def do_GET'))
        get_end=self.controller.index('environment_match = re.fullmatch',get_start)
        block=self.controller[get_start:get_end]
        self.assertNotIn('resolve_internal',block)
        self.assertNotIn('secretValue',block)
        self.assertNotIn('ciphertext',block)

    def test_internal_resolution_requires_second_token(self):
        start=self.controller.index("secret_match = re.fullmatch(r'/v1/projects/",self.controller.index('def do_POST'))
        end=self.controller.index('environment_match = re.fullmatch',start)
        block=self.controller[start:end]
        self.assertIn("operation=='resolve-internal'",block)
        self.assertIn("X-CloudIF-Secret-Resolver-Token",block)
        self.assertIn('hmac.compare_digest(provided,SECRET_RESOLVER_TOKEN)',block)
        self.assertIn('secret_resolver_forbidden',block)
        self.assertLess(block.index('hmac.compare_digest'),block.index('project_secret_store.resolve_internal'))

    def test_stage_removes_plaintext_from_request_mapping(self):
        start=self.controller.index("if operation=='stage':")
        end=self.controller.index("if operation=='rotate/plan':",start)
        block=self.controller[start:end]
        self.assertIn("payload.pop('secretValue'",block)
        self.assertIn('finally:value=None',block)
        self.assertNotIn("return self.send_json(201,{'secretValue'",block)

    def test_store_never_serializes_plaintext_in_common_responses(self):
        for marker in (
            "'secretValueIncluded':False",
            "'ciphertextIncluded':False",
            "'secretValuesIncluded':False",
            "'ciphertextsIncluded':False",
        ):
            self.assertIn(marker,self.store)
        common=self.store[:self.store.index('def resolve_internal(')]
        self.assertNotIn("'resolvedSecrets'",common)
        self.assertNotIn("plaintext.decode",common)

    def test_only_internal_resolver_returns_decrypted_material(self):
        start=self.store.index('def resolve_internal(')
        block=self.store[start:]
        self.assertIn("'resolvedSecrets':resolved",block)
        self.assertIn("'secretValuesIncluded':True",block)
        self.assertIn("'auditRequired':True",block)
        self.assertIn("status='active'",block)
        self.assertIn('secret_reference_scope_mismatch',block)

    def test_secret_plan_lookup_is_publicly_sanitized(self):
        self.assertIn('/environment/secrets/plans/',self.controller)
        self.assertIn('project_secret_store.get_plan',self.controller)
        start=self.store.index('def get_plan(');end=self.store.index('def _entry_matches_reference',start);block=self.store[start:end]
        self.assertIn("'secretValueIncluded':False",block)
        self.assertIn("'ciphertextIncluded':False",block)
        self.assertIn("startswith('_cloudiff')",block)
        self.assertNotIn('resolve_internal',block)


    def test_controller_supports_promotion_and_active_ttl(self):
        self.assertIn('promote/plan|promote/apply',self.controller)
        self.assertIn('project_secret_store.promotion_plan',self.controller)
        self.assertIn('project_secret_store.apply_promotion',self.controller)
        self.assertIn("body.get('activeTtlSeconds'",self.controller)
        self.assertIn("if not body.get('approved')",self.controller)


    def test_controller_and_store_compile(self):
        ast.parse(self.controller)
        ast.parse(self.store)


if __name__=='__main__':unittest.main()
