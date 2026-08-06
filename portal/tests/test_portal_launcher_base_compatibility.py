from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
LAUNCHER=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py'
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'


class PortalLauncherBaseCompatibilityTests(unittest.TestCase):
    def test_message_migrations_are_optional_for_updated_base(self):
        source=LAUNCHER.read_text()
        self.assertIn('for old, new in _MESSAGE_REPLACEMENTS:',source)
        self.assertIn('if old in source:',source)
        self.assertIn('source = source.replace(old, new)',source)
        block=source[source.index('for old, new in _MESSAGE_REPLACEMENTS:'):source.index("source = _replace_all(source, _ADMIN_LOOKUP_BOX",source.index('for old, new in _MESSAGE_REPLACEMENTS:'))]
        self.assertNotIn('_replace_all(source, old, new, old)',block)

    def test_authorization_policy_contract_remains_required(self):
        launcher=LAUNCHER.read_text();base=BASE.read_text()
        self.assertIn('if _POLICY_OLD in source:',launcher)
        self.assertIn('elif _POLICY_NEW not in source:',launcher)
        self.assertEqual(base.count("return bool(groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))"),1)
        self.assertNotIn("return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins'}))",base)
        self.assertIn('def _admin_project_delete_allowed(user,slug):',base)

    def test_updated_base_no_longer_contains_legacy_global_only_messages(self):
        base=BASE.read_text()
        self.assertNotIn('Área restrita à administração global.',base)
        self.assertNotIn('Acesso restrito à administração global.',base)
        self.assertIn('Somente o proprietário, CloudIF-Professor ou CloudIF-Tenants-Admin pode excluir este projeto.',base)


if __name__=='__main__':unittest.main()
