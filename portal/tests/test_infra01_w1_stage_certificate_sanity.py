"""Fail-closed stage certificate SAN/expiry cache validation; offline only."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py'
REPLICA=ROOT/'components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py'
spec=importlib.util.spec_from_file_location('cloudif_publisher_tls',MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class CertTests(unittest.TestCase):
 def _openssl(self,san,expiry_exit=0):
  def side_effect(argv,**kwargs):
   if '-ext' in argv:return subprocess.CompletedProcess(argv,0,san,'')
   if '-checkend' in argv:return subprocess.CompletedProcess(argv,expiry_exit,'','')
   raise AssertionError('unexpected subprocess')
  return patch.object(mod.subprocess,'run',side_effect=side_effect)
 def test_exact_san_positive(self):
  with patch.object(mod.Path,'is_file',return_value=True),self._openssl('X509v3 Subject Alternative Name:\n DNS:1002-w1-preview.cloudiff.duckdns.org, DNS:other.org'):
   self.assertTrue(mod.cert_covers('cloudif-stage-1002-w1-preview',['1002-w1-preview.cloudiff.duckdns.org']))
 def test_substring_suffix_san_does_not_match(self):
  with patch.object(mod.Path,'is_file',return_value=True),self._openssl('DNS:1002-w1-preview.cloudiff.duckdns.org.attacker.example'):
   self.assertFalse(mod.cert_covers('cloudif-stage-1002-w1-preview',['1002-w1-preview.cloudiff.duckdns.org']))
 def test_san_expired_fails(self):
  with patch.object(mod.Path,'is_file',return_value=True),self._openssl('DNS:1002-w1-preview.cloudiff.duckdns.org',expiry_exit=1):
   self.assertFalse(mod.cert_covers('cloudif-stage-1002-w1-preview',['1002-w1-preview.cloudiff.duckdns.org']))
 def test_cert_path_traversal_rejected(self):
  with patch.object(mod.Path,'is_file') as is_file:
   self.assertFalse(mod.cert_covers('../other',['1002-w1-preview.cloudiff.duckdns.org']))
   is_file.assert_not_called()
 def test_missing_certificate_fails(self):
  with patch.object(mod.Path,'is_file',return_value=False):
   self.assertFalse(mod.cert_covers('dedicated-cert',['1002-w1-preview.cloudiff.duckdns.org']))
 def test_openssl_timeout_fails_closed(self):
  with patch.object(mod.Path,'is_file',return_value=True),patch.object(mod.subprocess,'run',side_effect=subprocess.TimeoutExpired('openssl',15)):
   self.assertFalse(mod.cert_covers('dedicated-cert',['1002-w1-preview.cloudiff.duckdns.org']))
 def test_cached_certificate_is_rechecked(self):
  state={'stages':{'1002-w1-preview':{'cert':'shared-original'}}}
  with patch.object(mod,'cert_exists',return_value=True) as exists,patch.object(mod,'cert_covers',return_value=True) as cover,patch.object(mod,'ensure_cert') as issue:
   result=mod.ensure_stage(state,1002,'preview',1)
  self.assertEqual(result['hostname'],'1002-w1-preview.cloudiff.duckdns.org')
  self.assertEqual(state['stages']['1002-w1-preview']['cert'],'shared-original')
  exists.assert_called_once_with('shared-original')
  cover.assert_called_once_with('shared-original',['1002-w1-preview.cloudiff.duckdns.org'])
  issue.assert_not_called()
 def test_stale_shared_cert_replaced_with_dedicated_without_mutating_shared(self):
  state={'stages':{'1002-w1-preview':{'cert':'shared-other-hosts'}}}
  with patch.object(mod,'cert_exists',return_value=True),patch.object(mod,'cert_covers',return_value=False),patch.object(mod,'ensure_cert',return_value='cloudif-stage-1002-w1-preview') as issue:
   mod.ensure_stage(state,1002,'preview',1)
  issue.assert_called_once_with('cloudif-stage-1002-w1-preview',['1002-w1-preview.cloudiff.duckdns.org'])
  self.assertEqual(state['stages']['1002-w1-preview']['cert'],'cloudif-stage-1002-w1-preview')
 def test_missing_stage_creates_dedicated(self):
  state={}
  with patch.object(mod,'ensure_cert',return_value='cloudif-stage-1024-w1-preview') as issue:
   mod.ensure_stage(state,1024,'preview',1)
  issue.assert_called_once_with('cloudif-stage-1024-w1-preview',['1024-w1-preview.cloudiff.duckdns.org'])
 def test_cert_issuance_failure_does_not_update_state(self):
  state={'stages':{'1002-w1-preview':{'cert':'old'}}}
  with patch.object(mod,'cert_exists',return_value=False),patch.object(mod,'ensure_cert',side_effect=RuntimeError('ACME_UNAVAILABLE')):
   with self.assertRaises(RuntimeError):mod.ensure_stage(state,1002,'preview',1)
  self.assertEqual(state,{'stages':{'1002-w1-preview':{'cert':'old'}}})
 def test_wrong_stage_name_rejected_before_cert(self):
  with patch.object(mod,'ensure_cert') as issue:
   with self.assertRaises(ValueError):mod.ensure_stage({},1002,'unexpected',1)
   issue.assert_not_called()
 def test_both_deployment_copies_identical(self):
  self.assertEqual(MODULE.read_bytes(),REPLICA.read_bytes())
if __name__=='__main__':unittest.main()
