import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Remote443RelayContractTests(unittest.TestCase):
    def text(self,p):return (ROOT/p).read_text()
    def test_public_surface_is_single_443_relay(self):
        unit=self.text('components/proxy/etc/systemd/system/cloudif-443-relay.service')
        self.assertIn('-p 0.0.0.0:443',unit);self.assertIn('--ssh 127.0.0.1:10022',unit);self.assertIn('--tls 127.0.0.1:10443',unit)
    def test_student_gateway_is_forward_only_and_project_scoped(self):
        cfg=self.text('components/proxy/etc/ssh/cloudif-remote-sshd_config')
        self.assertIn('AllowTcpForwarding local',cfg);self.assertIn('AuthorizedKeysCommand /usr/local/libexec/cloudif-remote-authorized-key.py',cfg);self.assertIn('Match User cifconn-hosp',cfg);self.assertIn('AllowTcpForwarding remote',cfg);self.assertIn('PermitListen 127.0.0.1:*',cfg)
    def test_hospedagem_connector_uses_outbound_443(self):
        unit=self.text('components/control-plane/etc/systemd/system/cloudif-remote-connector-master.service')
        self.assertIn('-p 443',unit);self.assertIn('cifconn-hosp@cloudiff.duckdns.org',unit)
        sync=self.text('components/control-plane/usr/local/libexec/cloudif-remote-connector-sync.py');self.assertIn("t.get('connector')!='hospedagem'",sync);self.assertIn("-O',op,'-R'",sync)
    def test_no_frp_panel_runtime_contract_remains(self):
        for p in ('components/proxy/etc/systemd/system/cloudif-frp-panel-master.service','components/control-plane/etc/systemd/system/cloudif-frp-panel-client.service','components/runtime/etc/systemd/system/cloudif-frp-panel-client.service'):
            self.assertFalse((ROOT/p).exists(),p)
    def test_docs_fix_wan_to_80_and_443(self):
        d=self.text('docs/manual-tecnico/13-ACESSO-EXTERNO.md')
        self.assertIn('WAN pública permite somente TCP/80 e TCP/443',d)
        self.assertIn('porta 22',d.lower())
        self.assertIn('nunca',d.lower())
if __name__=='__main__':unittest.main()
