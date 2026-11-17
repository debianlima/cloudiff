import importlib.util
import pathlib
import tempfile
import os
import shutil
import subprocess
import unittest

P = pathlib.Path(__file__).parents[1] / 'tools' / 'cloudif_paperclip_w1_plan.py'
spec = importlib.util.spec_from_file_location('paperclip_w1_plan', P)
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)

COMMIT='dfcaaf831438cf0402d54a5ede388c3dc66bf222'
APP='sha256:'+'a'*64
NGINX='nginx:1.27.5-alpine@sha256:'+'b'*64

class PlanTests(unittest.TestCase):
    def get(self, mode="cutover"):
        return plan.compose_plan(source_commit=COMMIT, native_image_id=APP, nginx_image=NGINX,
                                 mode=mode)

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
        d=self.get(); self.assertEqual(d['services']['web']['container_name'], 'cloudif-p1025-w1-preview-web')
        self.assertEqual(d['services']['app']['container_name'], 'cloudif-p1025-w1-preview-app')
        self.assertEqual(d['services']['app']['environment']['PORT'], '3100')
        self.assertNotIn('3100:',str(d))

    def test_default_plan_canary_is_not_public(self):
        d=plan.compose_plan(source_commit=COMMIT,native_image_id=APP,nginx_image=NGINX)
        self.assertEqual(d["name"],"cloudif-p1025-w1-canary")
        self.assertEqual(d["services"]["web"]["container_name"],plan.CANARY_WEB_NAME)
        self.assertEqual(d["services"]["app"]["container_name"],plan.CANARY_APP_NAME)
        self.assertEqual(d["services"]["web"]["networks"],["preview-private"])
        self.assertEqual(d["services"]["app"]["networks"],["preview-private"])
        self.assertNotIn("cloudif-publications",d["networks"])
        self.assertTrue(d["networks"]["preview-private"]["internal"])
        self.assertEqual(d["services"]["web"]["labels"]["org.cloudiff.source-preview-bridge"],"false")
        self.assertEqual(d["services"]["web"]["labels"]["org.cloudiff.stage"],"canary")
        self.assertEqual(d["services"]["app"]["volumes"][0]["source"],plan.CANARY_DATA_VOLUME)
        self.assertNotIn(plan.DATA_VOLUME,d["volumes"])
        self.assertEqual(d["services"]["app"]["environment"]["PAPERCLIP_INSTANCE_ID"],
                         "preview-w1-1025-canary")
        self.assertNotIn(plan.WEB_NAME,str(d))
        self.assertNotIn(plan.APP_NAME,str(d))

    def test_cutover_matches_forja_generic_nginx_gateway_name(self):
        d=self.get(mode="cutover")
        self.assertEqual(d["services"]["web"]["container_name"],
                         "cloudif-p1025-w1-preview-web")
        self.assertEqual(d["services"]["web"]["networks"],
                         ["preview-private","cloudif-publications"])
        self.assertEqual(d["services"]["web"]["labels"]["org.cloudiff.source-preview-bridge"],"true")
        self.assertEqual(d["volumes"][plan.DATA_VOLUME]["name"],plan.DATA_VOLUME)
        self.assertNotEqual(plan.CANARY_DATA_VOLUME,plan.DATA_VOLUME)

    def test_invalid_mode_rejected_before_any_manifest_is_written(self):
        for invalid in ("production","preview","",None):
            with self.subTest(mode=invalid),self.assertRaises(ValueError):
                self.get(mode=invalid)

    def test_nginx_routes_to_internal_app_only(self):
        content=plan.nginx_proxy_config()
        self.assertIn('resolver 127.0.0.11 valid=10s ipv6=off;',content)
        self.assertIn('proxy_pass http://$cloudiff_preview_upstream:3100;',content)
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

    def test_nginx_websocket_upgrade_and_trusted_scheme(self):
        config=plan.nginx_proxy_config()
        self.assertIn('map $http_upgrade $cloudiff_w1_connection', config)
        self.assertIn('proxy_set_header Connection $cloudiff_w1_connection;', config)
        self.assertIn('proxy_set_header X-Forwarded-Proto https;', config)
        self.assertIn('return 421;', config)
        self.assertIn('set $cloudiff_preview_upstream app;', config)
        self.assertNotIn('$http_x_forwarded_proto', config)

    def test_proxy_health_requires_root_and_api(self):
        d=self.get()
        health=d['services']['web']['healthcheck']['test'][-1]
        self.assertIn('127.0.0.1/ &&', health)
        self.assertIn('127.0.0.1/api/health', health)

    def test_proxy_health_sends_configured_host_header(self):
        # Without the Host header nginx rejects its own loopback checks (HTTP 421).
        health = self.get()['services']['web']['healthcheck']['test'][-1]
        self.assertEqual(health.count(f"--header='Host: {plan.HOST}'"), 2)

    def test_explicit_isolated_paperclip_config(self):
        app=self.get()['services']['app']
        self.assertEqual(
            app['environment']['PAPERCLIP_CONFIG'],
            '/paperclip/instances/preview-w1-1025/config.json'
        )

    def test_local_candidate_files_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            previous=os.getcwd()
            try:
                os.chdir(temp)
                config=self.get()
                target=plan.write_candidate('candidate',config,plan.nginx_proxy_config())
                self.assertEqual(len(target),2)
                root=pathlib.Path(temp)/'candidate'
                self.assertEqual(root.stat().st_mode & 0o777,0o700)
                self.assertEqual((root/'proxy.conf').stat().st_mode & 0o777,0o600)
                self.assertIn('"cloudif-p1025-w1-preview-app"', (root/'compose.json').read_text())
                with self.assertRaisesRegex(ValueError,'already_exists'):
                    plan.write_candidate('candidate',config,plan.nginx_proxy_config())
            finally:
                os.chdir(previous)

    def test_local_candidate_rejects_absolute_path_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            previous=os.getcwd()
            try:
                os.chdir(temp)
                pathlib.Path('link').symlink_to(temp, target_is_directory=True)
                pathlib.Path('deeper').mkdir()
                pathlib.Path('deeper/link').symlink_to(temp, target_is_directory=True)
                for bad in ('/etc/komodo/stacks/evil', '../outside','link/candidate','deeper/link/candidate'):
                    with self.subTest(bad=bad),self.assertRaises(ValueError):
                        plan.write_candidate(bad,self.get(),plan.nginx_proxy_config())
            finally:
                os.chdir(previous)

    def test_nginx_configuration_with_installed_binary(self):
        if not shutil.which("nginx"):
            self.skipTest("nginx not installed; unit tests still assert proxy contract")
        with tempfile.TemporaryDirectory() as prefix:
            base=pathlib.Path(prefix)
            dirs=['client_body','proxy','fastcgi','uwsgi','scgi']
            http="\n".join(
                ["access_log off;"]
                + [f"{part}_temp_path {base / part};" for part in dirs]
            )
            nginx=plan.nginx_proxy_config().replace("listen 80;", "listen 18080;")
            conf=base/"nginx.conf"
            conf.write_text(
                f"error_log stderr notice;\npid {base / 'nginx.pid'};\n"
                "events { worker_connections 64; }\n"
                f"http {{\n{http}\n{nginx}\n}}\n",
                encoding="utf-8",
            )
            p=subprocess.run(
                ["nginx","-t","-e","stderr","-p",prefix+"/","-c",str(conf)],
                capture_output=True,text=True,check=False,timeout=10,
            )
            self.assertEqual(p.returncode,0,p.stderr[-500:])

    def test_no_deploy_actions(self):
        content=P.read_text()
        for verb in ('docker run','docker build','docker compose up','sudo ','chmod 777','deploy_stack('):
            self.assertNotIn(verb,content)

if __name__=='__main__': unittest.main()
