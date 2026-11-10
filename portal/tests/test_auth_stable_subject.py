import os
import unittest
from pathlib import Path

os.environ.setdefault("CLOUDIF_PORTAL_TESTING", "1")

from portal.core.auth import Identity
from portal.core.security import csrf_token

ROOT=Path(__file__).resolve().parents[2]
PORTAL=ROOT/"components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py"

class StableSubjectIdentityTests(unittest.TestCase):
    def test_legacy_constructor_and_principal_remain_compatible(self):
        identity=Identity("Alice","a@example.invalid",frozenset({"CloudIF-Aluno"}))
        self.assertEqual(identity.principal,"alice")

    def test_subject_and_issuer_form_stable_principal(self):
        identity=Identity("renamed-user","a@example.invalid",frozenset(),subject="uid-123",issuer="https://authiff.duckdns.org/")
        self.assertEqual(identity.principal,"https://authiff.duckdns.org|uid-123")

    def test_csrf_is_stable_across_username_rename_for_same_subject(self):
        a=Identity("old-name","a@example.invalid",frozenset(),subject="uid-123",issuer="https://authiff.duckdns.org")
        b=Identity("new-name","a@example.invalid",frozenset(),subject="uid-123",issuer="https://authiff.duckdns.org")
        self.assertEqual(csrf_token(a),csrf_token(b))

    def test_different_subjects_do_not_share_csrf_identity(self):
        a=Identity("same","a@example.invalid",frozenset(),subject="uid-a",issuer="https://authiff.duckdns.org")
        b=Identity("same","a@example.invalid",frozenset(),subject="uid-b",issuer="https://authiff.duckdns.org")
        self.assertNotEqual(csrf_token(a),csrf_token(b))

    def test_production_portal_captures_authentik_uid_and_uses_it_for_csrf(self):
        src=PORTAL.read_text()
        self.assertIn('X-authentik-uid',src)
        self.assertIn('CLOUDIF_AUTHENTIK_ISSUER',src)
        self.assertIn('subject=str(user.get("subject") or "").strip()',src)
        self.assertIn('return ((issuer+"|") if issuer else "")+subject',src)

if __name__ == "__main__":
    unittest.main()
