from pathlib import Path
import ast, unittest

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'components/faro/current-apps/taiga-reconciler-current/cloudif-taiga-reconciler.py'
UNIT=ROOT/'components/faro/etc/systemd/system/cloudif-taiga-reconciler.service'
ENV=ROOT/'config/faro/taiga-reconciler.env.example'

class FaroTaigaReconcilerContractTests(unittest.TestCase):
    def test_broker_is_local_authority_without_external_taiga_secret(self):
        src=APP.read_text(); ast.parse(src)
        self.assertIn("TAIGA_RECONCILER_TOKEN",src)
        self.assertIn("TAIGA_BACK_CONTAINER",src)
        self.assertIn("docker','exec','-i',CONTAINER",src)
        self.assertNotIn('OIDC_RP_CLIENT_SECRET',src)
        self.assertNotIn('POSTGRES_PASSWORD',src)
        self.assertIn("'secrets_exposed':False",src)
    def test_summary_supports_subject_isolation(self):
        src=APP.read_text()
        self.assertIn("/summary",src)
        self.assertIn("include_members",src)
        self.assertIn("user__pk",src)
        self.assertIn("HistoryEntry",src)
    def test_service_uses_root_only_env_and_hardened_unit(self):
        unit=UNIT.read_text(); env=ENV.read_text()
        self.assertIn('EnvironmentFile=/etc/cloudif/taiga-reconciler.env',unit)
        for marker in ('NoNewPrivileges=true','ProtectSystem=strict','ProtectHome=true','PrivateTmp=true'):
            self.assertIn(marker,unit)
        self.assertIn('TAIGA_RECONCILER_TOKEN=<required-local-secret>',env)
        self.assertNotIn('TAIGA_SECRET_KEY',env)
        self.assertNotIn('OIDC_RP_CLIENT_SECRET',env)

if __name__=='__main__':unittest.main()
