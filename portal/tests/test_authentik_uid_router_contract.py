from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
FILES=[
 ROOT/'components/control-plane/srv/cloudif/router/conf.d/default.conf',
 ROOT/'components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh',
 ROOT/'components/control-plane/srv/cloudif/bin/cloudif-apply-router-portal-v1.sh',
 ROOT/'components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh',
]

class AuthentikUidRouterContractTests(unittest.TestCase):
    def test_router_and_generators_propagate_stable_authentik_uid(self):
        for path in FILES:
            src=path.read_text()
            self.assertIn('authentik_uid',src,path)
            self.assertIn('x_authentik_uid',src,path)
            self.assertIn('X-authentik-uid',src,path)

    def test_live_router_portal_location_sets_uid_from_auth_subrequest(self):
        src=FILES[0].read_text()
        block=src.split('location ^~ /cloudiff/portal/ {',1)[1].split('}',1)[0]
        self.assertIn('auth_request_set $authentik_uid $upstream_http_x_authentik_uid;',block)
        self.assertIn('proxy_set_header X-authentik-uid $authentik_uid;',block)

    def test_mcp_resume_also_carries_stable_uid(self):
        src=FILES[0].read_text()
        block=src.split('location = /cloudiff/mcp/oauth/resume {',1)[1].split('}',1)[0]
        self.assertIn('auth_request_set $authentik_uid $upstream_http_x_authentik_uid;',block)
        self.assertIn('proxy_set_header X-authentik-uid $authentik_uid;',block)

if __name__=='__main__': unittest.main()
