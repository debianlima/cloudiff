"""Git HTTP integration: synthetic credentials and a loopback redirect only."""
import ast
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib

SOURCE=(Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
TOKEN='FAKE_GIT_TOKEN_FOR_LOOPBACK_TEST_ONLY'

def auth(port):
    functions=[n for n in ast.parse(SOURCE.read_text()).body if
               isinstance(n,ast.FunctionDef) and n.name=='_v119_git_ephemeral_auth']
    assert len(functions)==1
    def config(name,default=''):
        return ({'FORGEJO_URL':f'http://127.0.0.1:{port}',
                 'FORGEJO_TOKEN':TOKEN,'FORGEJO_SERVICE_USER':'fake-user'}).get(name,default)
    ns={'_v118_cfg':config,'urllib':urllib,'base64':base64}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_git_ephemeral_auth']('team','repo')

def redirect_probe(follow):
    seen={'initial':[],'redirected':[]}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/team/repo.git/info/refs'):
                seen['initial'].append(bool(self.headers.get('Authorization')))
                self.send_response(302)
                self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/team/other.git/info/refs?service=git-upload-pack')
            else:
                seen['redirected'].append(bool(self.headers.get('Authorization')))
                self.send_response(404)
            self.end_headers()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url,env=auth(server.server_port)
        if follow:
            # A negative control exercises the old Git redirect behavior.
            env=dict(env,GIT_CONFIG_COUNT='1')
        with tempfile.TemporaryDirectory() as home:
            full={**os.environ,**env,'HOME':home,'GIT_CONFIG_NOSYSTEM':'1','GIT_TERMINAL_PROMPT':'0'}
            result=subprocess.run(['git','ls-remote',url],env=full,capture_output=True,timeout=10)
        return seen,result.returncode
    finally:
        server.shutdown();thread.join(timeout=3);server.server_close()

class GitRedirectProtection(unittest.TestCase):
    def test_baseline_git_follows_and_forwards_auth_to_other_repo(self):
        seen,code=redirect_probe(follow=True)
        self.assertNotEqual(code,0)
        self.assertEqual(seen['initial'],[True])
        self.assertEqual(seen['redirected'],[True])

    def test_protected_git_rejects_redirect_before_other_repo(self):
        seen,code=redirect_probe(follow=False)
        self.assertNotEqual(code,0)
        self.assertEqual(seen['initial'],[True])
        self.assertEqual(seen['redirected'],[])

if __name__=='__main__':unittest.main()
