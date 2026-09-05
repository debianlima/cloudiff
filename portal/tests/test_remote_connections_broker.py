import importlib.util, tempfile, threading, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_remote_connections.py'
spec=importlib.util.spec_from_file_location('cloudif_remote_connections_test',MOD_PATH)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class FakeDriver:
    configured=True
    def __init__(self):self.created=[];self.deleted=[];self.lock=threading.Lock()
    def health(self):return True
    def create_tcp(self,name,client_id,local_ip,local_port,remote_port):
        with self.lock:self.created.append((name,client_id,local_ip,local_port,remote_port))
        return name
    def delete(self,name,client_id):
        with self.lock:self.deleted.append((name,client_id))
        return True

def row(slug='teste-sofa',tenant='iff1742962-testesofa'):
    return {'project_slug':slug,'tenant':tenant,'owner_user':'iff1742962','instructions':{'mcp_endpoint':'https://cloudiff.duckdns.org/cloudiff/mcp'}}

class RemoteConnectionsBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'portal.db';self.driver=FakeDriver();self.now=[100000]
        self.b=mod.RemoteBroker(self.db,{'edge_host':'cloudiff.duckdns.org','port_start':24000,'port_end':24009,'default_ttl':1800,'max_ttl':7200,'postgres_tls':False},self.driver,lambda:self.now[0])
    def tearDown(self):self.tmp.cleanup()
    def test_inventory_is_project_scoped_secretless_and_web_ready(self):
        d=self.b.inventory([row()],'iff1742962')
        self.assertTrue(d['ok']);self.assertFalse(d['secrets_exposed']);self.assertEqual(len(d['projects']),1)
        p=d['projects'][0];self.assertEqual(p['project_slug'],'teste-sofa')
        self.assertIn('https://cloudiff.duckdns.org/git/iff1742962/cloudif-teste-sofa.git',[x['url'] for x in p['web']])
        states={x['id']:x['state'] for x in p['raw']};self.assertEqual(states['forgejo_ssh'],'ready');self.assertEqual(states['postgres'],'tls_required')
        self.assertNotIn('password',str(d).lower());self.assertNotIn('panel_token',str(d).lower())
    def test_forgejo_lease_is_idempotent_and_releasable(self):
        first=self.b.create_lease([row()],'iff1742962','teste-sofa','forgejo_ssh',1800)
        second=self.b.create_lease([row()],'iff1742962','teste-sofa','forgejo_ssh',1800)
        self.assertFalse(first['existing']);self.assertTrue(second['existing']);self.assertEqual(first['lease_id'],second['lease_id']);self.assertEqual(len(self.driver.created),1)
        out=self.b.release([row()],'iff1742962',first['lease_id']);self.assertEqual(out['status'],'released');self.assertEqual(len(self.driver.deleted),1)
    def test_postgres_is_fail_closed_without_tls_gateway(self):
        with self.assertRaises(mod.BrokerError) as cm:self.b.create_lease([row()],'iff1742962','teste-sofa','postgres',1800)
        self.assertEqual(cm.exception.code,'tls_required');self.assertEqual(len(self.driver.created),0)
    def test_cross_project_actor_cannot_create_or_release(self):
        lease=self.b.create_lease([row('p1','t1')],'student','p1','forgejo_ssh',1800)
        with self.assertRaises(mod.BrokerError) as cm:self.b.create_lease([row('p2','t2')],'student','p1','forgejo_ssh',1800)
        self.assertEqual(cm.exception.code,'project_denied')
        with self.assertRaises(mod.BrokerError) as cm:self.b.release([row('p2','t2')],'student',lease['lease_id'])
        self.assertEqual(cm.exception.code,'lease_denied')
    def test_expired_lease_is_revoked_during_inventory(self):
        lease=self.b.create_lease([row()],'student','teste-sofa','forgejo_ssh',300)
        self.now[0]+=301;d=self.b.inventory([row()],'student')
        self.assertEqual(len(self.driver.deleted),1);self.assertEqual({x['id']:x['state'] for x in d['projects'][0]['raw']}['forgejo_ssh'],'ready')
    def test_concurrent_projects_receive_distinct_ports(self):
        out=[];errs=[];barrier=threading.Barrier(3)
        def worker(slug):
            try:barrier.wait();out.append(self.b.create_lease([row(slug,slug+'-db')],'student',slug,'forgejo_ssh',1800))
            except Exception as e:errs.append(e)
        ts=[threading.Thread(target=worker,args=(s,)) for s in ('teste-3','teste-4')]
        for t in ts:t.start()
        barrier.wait()
        for t in ts:t.join()
        self.assertFalse(errs);self.assertEqual(len(out),2);self.assertEqual(len({x['edge_port'] for x in out}),2)
    def test_frp_panel_delete_resolves_shadow_client_id(self):
        class Driver(mod.FrpPanelDriver):
            def __init__(self):super().__init__('http://panel','token');self.calls=[]
            def _request(self,path,payload=None,method='POST'):
                self.calls.append((path,payload,method))
                if path.endswith('/list_configs'):
                    return {'proxy_configs':[{'name':'lease-a','origin_client_id':'cloudiff-broker.c.forja','client_id':'cloudiff-broker.c.forja@7'}]}
                return {'status':{'code':1}}
        d=Driver();self.assertTrue(d.delete('lease-a','cloudiff-broker.c.forja'))
        self.assertEqual(d.calls[-1][1]['clientId'],'cloudiff-broker.c.forja@7')

    def test_dialog_is_overlay_and_warns_about_dynamic_ports(self):
        html=mod.render_dialog('csrf-test')
        self.assertIn('<dialog id="remote-connections-dialog"',html);self.assertIn('Conexões remotas',html)
        self.assertIn('/cloudiff/portal/api/remote-connections',html);self.assertIn('Ativar por 30 min',html)
        self.assertNotIn('CLOUDIF_REMOTE_FRP_PANEL_TOKEN',html)

    def test_rendered_dialog_javascript_is_syntax_valid(self):
        import re, shutil, subprocess, tempfile
        html=mod.render_dialog('csrf-test');scripts=re.findall(r'<script[^>]*>(.*?)</script>',html,re.S|re.I)
        self.assertEqual(len(scripts),1)
        node=shutil.which('node')
        if not node:self.skipTest('node unavailable')
        with tempfile.NamedTemporaryFile('w',suffix='.js',delete=False) as fh:
            fh.write(scripts[0]);name=fh.name
        try:
            proc=subprocess.run([node,'--jitless','--check',name],capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,0,proc.stderr)
        finally:Path(name).unlink(missing_ok=True)

    def test_portal_routes_enforce_origin_csrf_and_existing_project_acl(self):
        src=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        block=src[src.index('# CloudIF project-scoped remote connections BEGIN'):src.index('# CloudIF project-scoped remote connections END')]
        for marker in ('_oi_visible(user)','_cloudif_security_valid_origin(self)','_prod_csrf_equal','/api/remote-connections/create','/api/remote-connections/release'):
            self.assertIn(marker,block)
        self.assertNotIn('CLOUDIF_REMOTE_FRP_PANEL_TOKEN=',block)

if __name__=='__main__':unittest.main()
