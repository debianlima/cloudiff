from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'


class PortalApprovalRedirectV2Tests(unittest.TestCase):
    def test_canonical_approval_targets_are_never_prefixed_twice(self):
        source=BASE.read_text()
        start=source.index('    def redirect(self, path=None):')
        end=source.index('\n    def do_GET(self):',start)
        helper=source[start:end]
        base='/cloudiff/portal'
        def emulate(path):
            if not path:
                return base+'/'
            if path.startswith(('/cloudiff/portal','/cloudif/portal')):
                return path
            if path.startswith('/?'):
                return base+path
            if path.startswith('?'):
                return base+'/'+path
            if path.startswith('/'):
                return base+path
            return path
        for target in ('/cloudiff/portal/?tab=agentes','/cloudiff/portal/?tab=aprovacoes','/cloudif/portal/?tab=agentes'):
            result=emulate(target)
            self.assertEqual(result,target)
            self.assertNotIn('/cloudiff/portal/cloudiff/portal/',result)
        self.assertIn('path.startswith(("/cloudiff/portal", "/cloudif/portal"))',helper)

    def test_connector_approval_uses_303_no_store_to_agents(self):
        source=BASE.read_text()
        start=source.index('# CloudIF human approvals BEGIN')
        end=source.index('# CloudIF human approvals END',start)
        block=source[start:end]
        self.assertIn("return_to=val('return_to').strip()",block)
        self.assertIn("'agentes' if return_to=='agentes' else 'aprovacoes'",block)
        self.assertIn('self.send_response(303)',block)
        self.assertIn("self.send_header('Cache-Control','no-store')",block)


if __name__=='__main__':unittest.main()
