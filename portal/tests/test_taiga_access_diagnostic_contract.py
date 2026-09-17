from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'

class TaigaAccessDiagnosticContractTests(unittest.TestCase):
    def test_denial_diagnostic_logs_booleans_not_csrf_value(self):
        src=COEXIST.read_text()
        block=src[src.index('cloudif_taiga_access_denied actor='):src.index('return send_response_object(self,response)',src.index('cloudif_taiga_access_denied actor='))]
        for marker in ('origin_ok=','csrf_ok=','profile_ok='):
            self.assertIn(marker,block)
        self.assertNotIn("form.get(\"csrf_token\", \"\")+",block)
        self.assertNotIn('Authorization',block)

if __name__=='__main__':unittest.main()
