from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
CURRENT=ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py'
MIRROR=ROOT/'components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py'

class PublisherAliasReservationReconciliationTests(unittest.TestCase):
    def test_runtime_alias_reservation_is_canonical(self):
        src=CURRENT.read_text()
        for marker in (
            'def reserve_alias(state,num,alias):',
            "'active_deploy':0",
            "item['status']='reserved'",
            "'reserved':True",
            'Aguardando publicação',
            "dep=int(a.get('active_deploy') or 0)",
            'if dep<1:',
            "result=(ensure_alias(state,num,dep,alias) if dep>0 else reserve_alias(state,num,alias))",
        ):
            self.assertIn(marker,src)
        self.assertEqual(src,MIRROR.read_text())

    def test_stage_framing_fix_is_added_without_touching_reserved_alias_behavior(self):
        src=CURRENT.read_text()
        stage=src[src.index("for stage_name,stage in sorted(state.get('stages',{}).items()):"):src.index("for alias,a in sorted(state.get('aliases',{}).items()):")]
        self.assertIn('proxy_hide_header X-Frame-Options;',stage)
        self.assertIn('proxy_hide_header Content-Security-Policy;',stage)
        self.assertIn("frame-ancestors 'self' https://cloudiff.duckdns.org",stage)
        self.assertNotIn('frame-ancestors *',stage)

if __name__=='__main__':unittest.main()
