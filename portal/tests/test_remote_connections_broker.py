import importlib.util, tempfile, threading, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_remote_connections.py'
spec=importlib.util.spec_from_file_location('cloudif_remote_connections_test',MOD_PATH)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def row(slug='teste-sofa',tenant='iff1742962-testesofa'):
    return {'project_slug':slug,'tenant':tenant,'owner_user':'iff1742962','instructions':{'mcp_endpoint':'https://cloudiff.duckdns.org/cloudiff/mcp'}}

class RemoteConnectionsBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.db=root/'portal.db';self.now=[100000]
        self.old_tenant_root=mod.TENANT_ROOT;mod.TENANT_ROOT=root/'tenants';td=mod.TENANT_ROOT/'iff1742962-testesofa';td.mkdir(parents=True);(td/'.env').write_text('POSTGRES_PORT=54404\nPOOLER_PROXY_PORT_TRANSACTION=65414\n')
        for slug in ('p1','p2','teste-3','teste-4'):
            t=mod.TENANT_ROOT/(slug+'-db');t.mkdir(parents=True,exist_ok=True);(t/'.env').write_text('POSTGRES_PORT=54409\n')
        self.b=mod.RemoteBroker(self.db,{'gateway_host':'cloudiff.duckdns.org','gateway_port':443,'gateway_enabled':True,'default_ttl':1800,'max_ttl':7200},lambda:self.now[0])
    def tearDown(self):mod.TENANT_ROOT=self.old_tenant_root;self.tmp.cleanup()
    def test_inventory_is_project_scoped_and_443_only(self):
        d=self.b.inventory([row()],'iff1742962');self.assertTrue(d['ok']);self.assertFalse(d['secrets_exposed']);self.assertEqual(d['gateway']['public_ports'],[443]);self.assertEqual(len(d['projects']),1)
        p=d['projects'][0];self.assertEqual(p['project_slug'],'teste-sofa');self.assertEqual(p['remote_access']['gateway_port'],443);self.assertEqual(p['remote_access']['state'],'ready')
        targets={x['id']:x for x in p['remote_access']['targets']};self.assertEqual(targets['forgejo_ssh']['local_port'],12222);self.assertEqual(targets['postgres']['local_port'],15432);self.assertNotIn('gateway_port',targets['postgres']);self.assertNotIn('upstream_port',targets['postgres'])
        self.assertIn('https://cloudiff.duckdns.org/git/iff1742962/cloudif-teste-sofa.git',[x['url'] for x in p['web']])
        self.assertNotIn('private_key',str(d).lower());self.assertNotIn('gateway_token',str(d).lower())
    def test_activation_delivers_key_once_and_is_idempotent(self):
        first=self.b.create_lease([row()],'iff1742962','teste-sofa',1800);second=self.b.create_lease([row()],'iff1742962','teste-sofa',1800)
        self.assertFalse(first['existing']);self.assertTrue(first['private_key'].startswith('-----BEGIN OPENSSH PRIVATE KEY-----'));self.assertTrue(first['gateway_user'].startswith('cifremote'))
        self.assertTrue(second['existing']);self.assertEqual(first['lease_id'],second['lease_id']);self.assertIsNone(second['private_key'])
        pub=first['ssh_public_key'].split();line=self.b.authorize_gateway_key(first['gateway_user'],pub[0],pub[1]);self.assertIsNotNone(line);self.assertIn('permitopen="10.62.91.2:2222"',line);self.assertIn('permitopen="127.0.0.1:54404"',line)
        self.assertNotIn(first['private_key'],str(self.b.inventory([row()],'iff1742962')))
    def test_release_revokes_future_authentication(self):
        lease=self.b.create_lease([row()],'student','teste-sofa',1800);pub=lease['ssh_public_key'].split();self.assertTrue(self.b.authorize_gateway_key(lease['gateway_user'],pub[0],pub[1]))
        out=self.b.release([row()],'student',lease['lease_id']);self.assertEqual(out['status'],'released');self.assertIsNone(self.b.authorize_gateway_key(lease['gateway_user'],pub[0],pub[1]))
    def test_rotate_replaces_user_and_key(self):
        first=self.b.create_lease([row()],'student','teste-sofa',1800);second=self.b.create_lease([row()],'student','teste-sofa',1800,rotate=True)
        self.assertNotEqual(first['lease_id'],second['lease_id']);self.assertNotEqual(first['ssh_fingerprint'],second['ssh_fingerprint']);self.assertFalse(second['existing'])
        pub=first['ssh_public_key'].split();self.assertIsNone(self.b.authorize_gateway_key(first['gateway_user'],pub[0],pub[1]))
    def test_cross_project_actor_cannot_create_or_release(self):
        lease=self.b.create_lease([row('p1','p1-db')],'student','p1',1800)
        with self.assertRaises(mod.BrokerError) as cm:self.b.create_lease([row('p2','p2-db')],'student','p1',1800)
        self.assertEqual(cm.exception.code,'project_denied')
        with self.assertRaises(mod.BrokerError) as cm:self.b.release([row('p2','p2-db')],'student',lease['lease_id'])
        self.assertEqual(cm.exception.code,'lease_denied')
    def test_expired_lease_is_removed_from_active_users_and_auth(self):
        lease=self.b.create_lease([row()],'student','teste-sofa',300);pub=lease['ssh_public_key'].split();self.now[0]+=301
        self.assertEqual(self.b.active_gateway_users(),[]);self.assertIsNone(self.b.authorize_gateway_key(lease['gateway_user'],pub[0],pub[1]));self.assertEqual(self.b.inventory([row()],'student')['projects'][0]['remote_access']['state'],'ready')
    def test_concurrent_projects_receive_distinct_gateway_accounts(self):
        out=[];errs=[];barrier=threading.Barrier(3)
        def worker(slug):
            try:barrier.wait();out.append(self.b.create_lease([row(slug,slug+'-db')],'student',slug,1800))
            except Exception as e:errs.append(e)
        ts=[threading.Thread(target=worker,args=(s,)) for s in ('teste-3','teste-4')]
        for t in ts:t.start()
        barrier.wait()
        for t in ts:t.join()
        self.assertFalse(errs);self.assertEqual(len(out),2);self.assertEqual(len({x['gateway_user'] for x in out}),2)
    def test_internal_auth_requires_source_and_bearer_token(self):
        cfg=lambda k,d='':{'CLOUDIF_REMOTE_GATEWAY_ALLOWED_IPS':'10.62.91.3','CLOUDIF_REMOTE_GATEWAY_TOKEN':'secret-token-for-test'}.get(k,d)
        self.assertTrue(mod.verify_internal_request('10.62.91.3','Bearer secret-token-for-test',cfg));self.assertFalse(mod.verify_internal_request('10.62.91.4','Bearer secret-token-for-test',cfg));self.assertFalse(mod.verify_internal_request('10.62.91.3','Bearer wrong',cfg))
    def test_public_payload_contains_commands_but_not_public_service_ports(self):
        lease=self.b.create_lease([row()],'student','teste-sofa',1800);p=mod.public_lease_payload(lease)
        self.assertEqual(p['gateway_port'],443);self.assertIn('-L 15432:127.0.0.1:54404',p['commands']['linux']);self.assertIn('-L 12222:10.62.91.2:2222',p['commands']['linux']);self.assertTrue(p['one_time_key_delivery']);self.assertNotIn('gateway_port',p['targets'][1]);self.assertNotIn('upstream_port',p['targets'][1])
    def test_hospedagem_connector_schema_is_reverse_loopback_only(self):
        lease=self.b.create_lease([row()],'student','teste-sofa',1800)
        targets=__import__('json').loads(lease['targets_json'])
        pg=next(x for x in targets if x['id']=='postgres')
        self.assertEqual(pg['connector'],'hospedagem')
        self.assertEqual(pg['gateway_host'],'127.0.0.1')
        self.assertEqual(pg['gateway_port'],54404)
        self.assertEqual(pg['upstream_host'],'127.0.0.1')
        self.assertEqual(pg['upstream_port'],54404)

    def test_dialog_is_overlay_and_explains_443_only(self):
        page=mod.render_dialog('csrf-test');self.assertIn('<dialog id="remote-connections-dialog"',page);self.assertIn('HTTPS e túnel SSH compartilham somente a porta pública 443',page);self.assertIn('Ativar acesso',page);self.assertIn('Baixar chave',page);self.assertNotIn('24000',page)
    def test_rendered_dialog_javascript_is_syntax_valid(self):
        import re, shutil, subprocess
        page=mod.render_dialog('csrf-test');scripts=re.findall(r'<script[^>]*>(.*?)</script>',page,re.S|re.I);self.assertEqual(len(scripts),1);node=shutil.which('node')
        if not node:self.skipTest('node unavailable')
        fn=Path(self.tmp.name)/'dialog.js';fn.write_text(scripts[0]);proc=subprocess.run([node,'--jitless','--check',str(fn)],capture_output=True,text=True,timeout=20);self.assertEqual(proc.returncode,0,proc.stderr)
    def test_portal_routes_enforce_project_acl_browser_csrf_and_internal_token(self):
        src=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text();block=src[src.index('# CloudIF project-scoped remote connections BEGIN'):src.index('# CloudIF project-scoped remote connections END')]
        for marker in ('_oi_visible(user)','_cloudif_security_valid_origin(self)','_prod_csrf_equal','/api/remote-connections/create','/internal/remote-ssh/active-users','_rc_internal_ok(self)'):self.assertIn(marker,block)
        self.assertNotIn('/internal/remote-ssh/authorized-key',block)
        self.assertNotIn('CLOUDIF_REMOTE_GATEWAY_TOKEN=',block)

if __name__=='__main__':unittest.main()
