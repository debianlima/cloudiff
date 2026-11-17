#!/usr/bin/env python3
import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).with_name('check-w1-edge-servername-readonly.py')
spec=importlib.util.spec_from_file_location('edge_host',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProbeTests(unittest.TestCase):
 def test_exact_server_name_matches(self):
  s='server {\n server_name 1002-w1-preview.cloudiff.duckdns.org;\n proxy_pass http://PRIVATE:8080;\n}'
  v=m.summarize(s)
  self.assertTrue(v['host_rules']['silvipro']['textual_config_present'])
  self.assertFalse(v['all_known_w1_server_names_present'])
  self.assertNotIn('PRIVATE',json.dumps(v))
 def test_body_without_w1_host_reports_missing(self):
  self.assertFalse(m.summarize('server_name cloudiff.duckdns.org;')['host_rules']['silvipro']['textual_config_present'])
 def test_unrelated_suffix_does_not_match(self):
  self.assertFalse(m.summarize('server_name 1002-w1-preview.cloudiff.duckdns.org.evil.invalid;')['host_rules']['silvipro']['textual_config_present'])
 def test_comments_are_not_config(self):
  self.assertFalse(m.summarize('# server_name 1002-w1-preview.cloudiff.duckdns.org;')['host_rules']['silvipro']['textual_config_present'])
 def test_all_hosts_present(self):
  s='\n'.join('server_name '+host+';' for host in m.HOSTS.values())
  self.assertTrue(m.summarize(s)['all_known_w1_server_names_present'])
 def test_wrong_host_no_config_read(self):
  with patch.object(m.socket,'gethostname',return_value='forja'),patch.object(m,'CONF') as conf:
   self.assertEqual(m.run()['status'],'BLOCKED_WRONG_HOST');conf.read_text.assert_not_called()
 def test_fails_when_unreadable(self):
  with patch.object(m.socket,'gethostname',return_value='mauricio'),patch.object(m,'CONF') as conf:
   conf.stat.side_effect=OSError
   self.assertEqual(m.run()['status'],'BLOCKED_CONFIG_UNREADABLE_OR_TOO_LARGE')
 def test_never_claims_tls_success(self):
  self.assertFalse(m.summarize('')['tls_verified'])
 def test_no_secrets_in_output(self):
  self.assertNotIn('a_password',json.dumps(m.summarize('proxy_pass http://user:a_password@host;')))
if __name__=='__main__':unittest.main()
