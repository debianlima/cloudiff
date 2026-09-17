from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
API=ROOT/'components/proxy/current-apps/access-telemetry-current/cloudif-access-api.py'
PUSH=ROOT/'components/proxy/current-apps/access-telemetry-current/cloudif-access-push.py'

class AccessTelemetryPublicSplitContractTests(unittest.TestCase):
    def test_api_and_push_split_public_internal_per_host(self):
        for path in (API,PUSH):
            src=path.read_text()
            for marker in ('public_requests','internal_requests','public_unique_visitors','public_errors','internal_errors'):
                self.assertIn(marker,src)
            self.assertIn("source='public'",src)
            self.assertIn("source='internal'",src)

if __name__=='__main__':unittest.main()
