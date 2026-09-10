from pathlib import Path
import importlib.util
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
APP=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
LIB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
GIT=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py').read_text()

class LinkedComposePublicationTests(unittest.TestCase):
    def test_linked_compose_is_project_scoped_and_never_falls_back_to_generic_runtime(self):
        for source in (APP,LIB):
            self.assertIn("LINKED_COMPOSE_PROJECTS={'tuleap-laboratorio-de-hardware'}",source)
            self.assertIn('def _is_linked_compose_project(slug):',source)
            self.assertIn("if _is_linked_compose_project(slug):",source)
            self.assertIn("runtimeKind':'linked-compose'",source)
            self.assertIn('Homologação imutável de stack Compose',source)

    def test_linked_compose_preview_uses_canonical_komodo_binding_and_forgejo_status(self):
        for source in (APP,LIB):
            self.assertIn('def _linked_compose_binding(con,slug):',source)
            self.assertIn('komodo_repo_id,komodo_stack_id,komodo_stack_name',source)
            self.assertIn('v133_komodo_project_status',source)
            self.assertIn('v133_komodo_deploy_linked_current',source)
            self.assertIn("'sourceMode':'forgejo-linked-stack'",source)
            self.assertIn("'bridge':f'cloudif-p{num}-w1-preview-web'",source)

    def test_safe_linked_deploy_does_not_force_clone_or_reclone(self):
        self.assertIn('def v133_komodo_deploy_linked_current(',GIT)
        block=GIT[GIT.index('def v133_komodo_deploy_linked_current('):GIT.index('\ndef v133_komodo_stack_action',GIT.index('def v133_komodo_deploy_linked_current('))]
        self.assertIn('"force_reclone": False',block)
        self.assertIn('"force_clone": False',block)
        self.assertIn('"wait_for_completion": True',block)
        self.assertNotIn('"force_reclone": True',block)
        self.assertNotIn('"force_clone": True',block)


    def test_safe_linked_deploy_payload_is_executable_contract(self):
        path=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py'
        spec=importlib.util.spec_from_file_location('gk_linked_contract',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        calls=[]
        module._v133_komodo_agent=lambda:('http://komodo.invalid','token')
        def fake(method,url,payload=None,token='',timeout=0):
            calls.append((method,url,payload,token,timeout));return {'ok':True,'status':200,'data':{'ok':True,'deploy_status':'completed'}}
        module._v133_http_json=fake
        result=module.v133_komodo_deploy_linked_current('tuleap-laboratorio-de-hardware','1'*24,'2'*24,timeout=181)
        self.assertTrue(result['ok']);self.assertEqual(len(calls),1)
        method,url,payload,token,timeout=calls[0]
        self.assertEqual(method,'POST');self.assertTrue(url.endswith('/komodo/project/deploy-full'))
        self.assertIs(payload['force_reclone'],False);self.assertIs(payload['force_clone'],False)
        self.assertIs(payload['wait_for_completion'],True);self.assertEqual(payload['repo_id'],'1'*24);self.assertEqual(payload['stack_id'],'2'*24)

if __name__=='__main__':unittest.main()
