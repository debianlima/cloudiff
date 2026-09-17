from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PUBLISHER=ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py'
MIRROR=ROOT/'components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py'

class PublicationEmbeddedPreviewHeadersTests(unittest.TestCase):
    def test_w_h_p_stage_edge_allows_only_cloudiff_portal_to_frame(self):
        src=PUBLISHER.read_text()
        stage=src[src.index("for stage_name,stage in sorted(state.get('stages',{}).items()):"):src.index("for alias,a in sorted(state.get('aliases',{}).items()):")]
        self.assertIn('frame-ancestors \'self\' https://cloudiff.duckdns.org',stage)
        self.assertIn('proxy_hide_header X-Frame-Options;',stage)
        self.assertIn('proxy_hide_header Content-Security-Policy;',stage)
        self.assertIn('proxy_pass http://10.62.91.2:18150;',stage)
        # Direct public host is still protected by an explicit edge CSP; only the
        # conflicting upstream frame policy is suppressed on W/H/P stage hosts.
        self.assertNotIn('frame-ancestors *',stage)
        self.assertEqual(src,MIRROR.read_text())

if __name__=='__main__':unittest.main()
