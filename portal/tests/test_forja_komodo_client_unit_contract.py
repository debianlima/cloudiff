from pathlib import Path
import unittest


class ForjaKomodoClientUnitContractTest(unittest.TestCase):
    def test_forja_service_uses_dedicated_komodo_client_environment(self):
        source=Path('components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/komodo-client.conf').read_text(encoding='utf-8')
        self.assertIn('EnvironmentFile=-/etc/cloudif/forja-komodo-client.env',source)
        self.assertNotIn('TOKEN=',source)


if __name__=='__main__':
    unittest.main()
