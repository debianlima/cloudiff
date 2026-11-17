import importlib.util
import pathlib
import unittest

P = pathlib.Path(__file__).parents[1] / 'tools' / 'cloudif_paperclip_w1_plan.py'
spec = importlib.util.spec_from_file_location('paperclip_w1_plan', P)
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)

COMMIT='dfcaaf831438cf0402d54a5ede388c3dc66bf222'
APP='sha256:'+'a'*64
NGINX='nginx:1.27.5-alpine@sha256:'+'b'*64

class PlanTests(unittest.TestCase):
    def get(self):
        return plan.compose_plan(source_commit=COMMIT, native_image_id=APP, nginx_image=NGINX)

    def test_exact_paperclip_project_identity(self):
        d=self.get(); self.assertEqual(d['services']['app']['labels']['org.cloudiff.project'], 'paperclip')
        self.assertEqual(d['services']['web']['labels']['org.cloudiff.stage'], 'preview')
        self.assertEqual(d['services']['web']['labels']['org.cloudiff.source-commit'], COMMIT)

    def test_no_public_ports_and_no_private_service_bind(self):
        d=self.get()
        for svc in d['services'].values():
            self.assertNotIn('ports', svc)
            self.assertNotIn('network_mode', svc)
        self.assertEqual(d['services']['app']['networks'], ['preview-private'])
        self.assertTrue(d['networks']['preview-private']['internal'])
        self.assertEqual(d['services']['web']['networks'], ['preview-private','cloudif-publications'])

    def test_private_data_separate_from_production(self):
        d=self.get(); app=d['services']['app']
        self.assertEqual(app['volumes'][0]['source'], plan.DATA_VOLUME)
        self.assertNotIn('bind', str(app['volumes']))
        self.assertEqual(app['environment']['PAPERCLIP_DEPLOYMENT_MODE'], 'authenticated')
        self.assertEqual(app['environment']['PAPERCLIP_DEPLOYMENT_EXPOSURE'], 'private')
        self.assertNotIn('DATABASE_URL', app['environment'])

    def test_pinned_image_ids(self):
        d=self.get(); self.assertEqual(d['services']['app']['image'], APP)
        self.assertEqual(d['services']['web']['image'], NGINX)
        self.assertEqual(d['services']['app']['pull_policy'], 'never')
        self.assertEqual(d['services']['web']['pull_policy'], 'never')

    def test_invalid_native_image_rejected(self):
        for image in ['cloudif/paperclip:latest','sha256:short','']:
            with self.subTest(image=image),self.assertRaises(ValueError):
                plan.compose_plan(source_commit=COMMIT,native_image_id=image,nginx_image=NGINX)

    def test_invalid_proxy_image_rejected(self):
        for image in ['nginx:latest','nginx:1.27.5-alpine','nginx:latest@sha256:'+'b'*64]:
            with self.subTest(image=image),self.assertRaises(ValueError):
                plan.compose_plan(source_commit=COMMIT,native_image_id=APP,nginx_image=image)

    def test_exact_git_commit_required(self):
        for sha in ['dfcaaf831438','invalidx'*5,'main','']:
            with self.subTest(commit=sha),self.assertRaises(ValueError):
                plan.compose_plan(source_commit=sha,native_image_id=APP,nginx_image=NGINX)

    def test_gateway_alias_and_port(self):
        d=self.get(); self.assertEqual(d['services']['web']['container_name'], 'cloudif-p1025-preview-web')
        self.assertEqual(d['services']['app']['container_name'], 'cloudif-p1025-preview-app')
        self.assertEqual(d['services']['app']['environment']['PORT'], '3100')
        self.assertNotIn('3100:',str(d))

    def test_nginx_routes_to_internal_app_only(self):
        content=plan.nginx_proxy_config()
        self.assertIn('proxy_pass http://app:3100;',content)
        self.assertNotIn('10.62.91.2',content)
        self.assertNotIn('127.0.0.1:3100',content)
        self.assertIn('server_name 1025-w1-preview.cloudiff.duckdns.org;',content)

    def test_proxy_config_mount_owner_only(self):
        d=self.get();m=d['services']['web']['volumes'][0]
        self.assertEqual(m['source'], '/srv/cloudif/paperclip-w1-1025/proxy.conf')
        self.assertTrue(m['read_only'])
        self.assertFalse(m['bind']['create_host_path'])

    def test_no_secret_values(self):
        d=self.get()
        out=str(d).lower()
        for secret in ('password','token','api_key','authorization','cloudif-paperclip/private','paperclip-private'):
            self.assertNotIn(secret,out)

    def test_no_deploy_actions(self):
        content=P.read_text()
        for verb in ('docker run','docker build','docker compose up','sudo ','chmod 777','deploy_stack('):
            self.assertNotIn(verb,content)

if __name__=='__main__': unittest.main()
