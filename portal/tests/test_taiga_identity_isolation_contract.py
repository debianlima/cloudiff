from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
BROKER=ROOT/'components/faro/current-apps/taiga-reconciler-current/cloudif-taiga-reconciler.py'
OIDC=ROOT/'components/faro/taiga-custom/back-oidc/oidc.py'
OIDC_SETTINGS=ROOT/'components/faro/taiga-custom/back-oidc/oidc_settings.py'
BACK_DOCKER=ROOT/'components/faro/taiga-custom/back-oidc/Dockerfile'
SESSION=ROOT/'components/faro/taiga-custom/front-session/cloudif-session-isolation.js'
FRONT_DOCKER=ROOT/'components/faro/taiga-custom/front-session/Dockerfile'

class TaigaIdentityIsolationContractTests(unittest.TestCase):
    def test_broker_preprovisions_missing_email_with_reserved_placeholder(self):
        src=BROKER.read_text(); ast.parse(src)
        self.assertIn("username+'@pending.cloudif.invalid'",src)
        self.assertIn("verified_email=not placeholder",src)
        self.assertIn("current_email.endswith('@pending.cloudif.invalid')",src)
        block=src.split('def user_for(spec):',1)[1].split('with transaction.atomic():',1)[0]
        self.assertNotIn("unresolved.append(username); return None",block)

    def test_oidc_prefers_stable_subject_and_username_before_email(self):
        src=OIDC.read_text(); ast.parse(src)
        self.assertIn('AUTHDATA_SUB_KEY = "oidc_sub"',src)
        self.assertIn('claims.get("preferred_username") or claims.get("nickname")',src)
        sub=src.index('self._authdata_user(self.AUTHDATA_SUB_KEY, sub)')
        username=src.index('username__iexact=username')
        email=src.index('email__iexact=email')
        authdata=src.index('self._authdata_user(self.AUTHDATA_KEY, username)')
        self.assertLess(sub,authdata)
        self.assertLess(authdata,username)
        self.assertLess(username,email)
        self.assertIn('current.endswith(self.PLACEHOLDER_SUFFIX)',src)
        self.assertIn('@pending.cloudif.invalid',src)


    def test_broker_never_resolves_a_different_username_by_email(self):
        src=BROKER.read_text(); ast.parse(src)
        user_block=src.split('def user_for(spec):',1)[1].split('with transaction.atomic():',1)[0]
        self.assertNotIn("User.objects.filter(email__iexact=email).first()",user_block)
        self.assertIn("email_collision=bool(source_email",user_block)
        self.assertIn("username+'@pending.cloudif.invalid'",user_block)
        start=src.index("DJANGO_GRANT_ACCESS = r'''")
        end=src.index("\ndef grant_access",start)
        grant=src[start:end]
        self.assertNotIn("if not u and email:u=User.objects.filter(email__iexact=email).first()",grant)
        self.assertIn("effective_email",grant)

    def test_oidc_does_not_alias_present_username_by_email(self):
        src=OIDC.read_text(); ast.parse(src)
        block=src.split('def filter_users_by_claims',1)[1].split('def _ensure_authdata',1)[0]
        username_none=block.index("if username:\n            return self.UserModel.objects.none()")
        email_lookup=block.index('email__iexact=email')
        self.assertLess(username_none,email_lookup)
        create=src.split('def create_user',1)[1].split('def update_user',1)[0]
        self.assertNotIn('if not user and email:',create)
        self.assertIn('collision=bool(email',create)
        self.assertIn('username+self.PLACEHOLDER_SUFFIX',create)

    def test_oidc_forces_fresh_idp_login_on_shared_workstations(self):
        src=OIDC_SETTINGS.read_text()
        self.assertIn('OIDC_AUTH_REQUEST_EXTRA_PARAMS',src)
        self.assertIn('"prompt": os.getenv("OIDC_AUTH_PROMPT", "login")',src)

    def test_auth_keys_are_session_scoped_not_persistent(self):
        src=SESSION.read_text()
        for key in ('token','refresh','userInfo'):
            self.assertIn(key,src)
        self.assertIn('window.sessionStorage',src)
        self.assertIn('originalRemove.call(local, key)',src)
        self.assertIn('originalSet.call(session, key, value)',src)
        self.assertNotIn('localStorage.clear()',src)

    def test_runtime_uses_derivative_images_and_clean_entry_route(self):
        compose=(ROOT/'components/faro/current-apps/taiga-current/compose.yaml').read_text()
        conf=(ROOT/'components/faro/current-apps/taiga-current/taiga.conf').read_text()
        self.assertIn('cloudif-local/taiga-back-oidc:6.10.2-c623b753-r7-identity',compose)
        self.assertIn('cloudif-local/taiga-front-oidc:6.10.3-c623b753-r4-session',compose)
        self.assertIn('/cloudif-enter/',conf)
        self.assertIn('location ~ "^/cloudif-enter/([a-z0-9][a-z0-9-]{0,62})$" {',conf)
        self.assertNotIn('location ~ ^/cloudif-enter/([a-z0-9][a-z0-9-]{0,62})$ {',conf)
        self.assertIn('localStorage.removeItem("token")',conf)
        self.assertIn('sessionStorage.removeItem("token")',conf)
        self.assertIn('sessionid=; Path=/; Max-Age=0',conf)
        self.assertIn('/oidc/authenticate/?next=/project/$1',conf)


    def test_oidc_username_shadow_collision_fails_closed(self):
        src=OIDC.read_text(); ast.parse(src)
        block=src.split('def filter_users_by_claims',1)[1].split('def _bind_authdata',1)[0]
        self.assertIn('bound_user = self._authdata_user(self.AUTHDATA_KEY, username)',block)
        self.assertIn('named_user = self.UserModel.objects.filter(username__iexact=username).first()',block)
        self.assertIn('bound_user.pk != named_user.pk',block)
        self.assertIn('raise PermissionDenied("OIDC username shadow collision")',block)
        self.assertLess(block.index('bound_user.pk != named_user.pk'),block.index('if bound_user:'))

    def test_oidc_binding_conflicts_fail_closed(self):
        src=OIDC.read_text(); ast.parse(src)
        self.assertIn('from django.core.exceptions import PermissionDenied',src)
        self.assertIn('def _bind_authdata',src)
        self.assertIn('query.exclude(user=user).exists()',src)
        self.assertIn('raise PermissionDenied("OIDC identity binding conflict")',src)
        self.assertIn('row.user_id != user.pk',src)

    def test_new_authenticated_tab_invalidates_previous_tab(self):
        src=SESSION.read_text()
        self.assertIn('cloudif-auth-generation',src)
        self.assertIn('BroadcastChannel',src)
        self.assertIn('window.addEventListener("storage"',src)
        self.assertIn('announceAuthenticatedSession()',src)
        self.assertIn('/login?reason=session-replaced',src)

    def test_authenticated_api_responses_are_not_shared_cached(self):
        conf=(ROOT/'components/faro/current-apps/taiga-current/taiga.conf').read_text()
        block=conf.split('location /api/ {',1)[1].split('}',1)[0]
        self.assertIn('Cache-Control "private, no-store, no-cache, must-revalidate"',block)
        self.assertIn('Pragma "no-cache"',block)
        self.assertIn('Expires "0"',block)
        self.assertIn('Vary "Authorization, Cookie"',block)

    def test_shared_workstation_bootstrap_assets_are_not_stale_cached(self):
        conf=(ROOT/'components/faro/current-apps/taiga-current/taiga.conf').read_text()
        self.assertIn('location = / {',conf)
        self.assertIn('location = /index.html {',conf)
        self.assertIn('location = /plugins/cloudif-session-isolation.js {',conf)
        self.assertGreaterEqual(conf.count('no-store, no-cache, must-revalidate'),4)
        self.assertIn('location / {\n    proxy_pass http://taiga-front/;',conf)
        generic=conf.split('location / {\n    proxy_pass http://taiga-front/;',1)[1].split('}',1)[0]
        self.assertIn('Cache-Control "no-cache, must-revalidate"',generic)

    def test_all_entry_routes_reset_session_and_private_media_is_no_store(self):
        conf=(ROOT/'components/faro/current-apps/taiga-current/taiga.conf').read_text()
        edge=(ROOT/'components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http_top.conf').read_text()
        for text in (conf,edge):
            self.assertIn('location = /entrar-cloudiff',text)
            self.assertIn('sessionStorage.removeItem("cloudif-auth-generation")',text)
            self.assertIn('/oidc/authenticate/?next=/',text)
        self.assertIn('private, no-store, no-cache, must-revalidate',conf)
        self.assertIn('add_header Vary "Authorization, Cookie" always',conf)
        self.assertIn('~^/media/ "private, no-store, no-cache, must-revalidate"',edge)

    def test_broker_marks_placeholder_users_as_pending_identity(self):
        src=BROKER.read_text()
        self.assertIn('pending_identity=[]',src)
        self.assertIn("status='waiting_identity' if (unresolved or pending_identity) else 'ready'",src)
        self.assertIn("'pending_identity':sorted(set(pending_identity))",src)
        self.assertIn("version':'0.4.1'",src)

    def test_derivative_images_are_reproducible(self):
        back=BACK_DOCKER.read_text(); front=FRONT_DOCKER.read_text()
        self.assertIn('FROM cloudif-local/taiga-back-oidc:6.10.2-c623b753',back)
        self.assertIn('COPY oidc.py',back)
        self.assertIn('chmod 0644 /opt/venv/lib/python3.11/site-packages/taiga_contrib_oidc_auth/oidc.py',back)
        self.assertIn('FROM cloudif-local/taiga-front-oidc:6.10.3-c623b753-r2',front)
        self.assertIn('/plugins/cloudif-session-isolation.js',front)
        self.assertIn('chmod 0644 /usr/share/nginx/html/plugins/cloudif-session-isolation.js',front)

if __name__=='__main__': unittest.main()
