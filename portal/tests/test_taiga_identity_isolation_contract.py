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
        self.assertIn('cloudif-local/taiga-back-oidc:6.10.2-c623b753-r4-identity',compose)
        self.assertIn('cloudif-local/taiga-front-oidc:6.10.3-c623b753-r3-session',compose)
        self.assertIn('/cloudif-enter/',conf)
        self.assertIn('localStorage.removeItem("token")',conf)
        self.assertIn('sessionStorage.removeItem("token")',conf)
        self.assertIn('sessionid=; Path=/; Max-Age=0',conf)
        self.assertIn('/oidc/authenticate/?next=/project/$1',conf)

    def test_broker_marks_placeholder_users_as_pending_identity(self):
        src=BROKER.read_text()
        self.assertIn('pending_identity=[]',src)
        self.assertIn("status='waiting_identity' if (unresolved or pending_identity) else 'ready'",src)
        self.assertIn("'pending_identity':sorted(set(pending_identity))",src)
        self.assertIn("version':'0.4.0'",src)

    def test_derivative_images_are_reproducible(self):
        back=BACK_DOCKER.read_text(); front=FRONT_DOCKER.read_text()
        self.assertIn('FROM cloudif-local/taiga-back-oidc:6.10.2-c623b753',back)
        self.assertIn('COPY oidc.py',back)
        self.assertIn('FROM cloudif-local/taiga-front-oidc:6.10.3-c623b753-r2',front)
        self.assertIn('/plugins/cloudif-session-isolation.js',front)

if __name__=='__main__': unittest.main()
