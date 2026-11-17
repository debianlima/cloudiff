"""Git HTTP integration: synthetic credentials and a loopback redirect only."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

SOURCE=(Path(__file__).resolve().parents[2]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
TOKEN='FAKE_GIT_TOKEN_FOR_LOOPBACK_TEST_ONLY'

def auth(port):
    """Create a loopback-only *synthetic* Git configuration for probing Git.

    Production `_v119_git_ephemeral_auth` now correctly rejects HTTP. This
    isolated test is specifically about the Git binary's redirect behavior,
    not an invocation of the credential-bearing CloudIFF helper.
    """
    url=f'http://127.0.0.1:{port}/team/repo.git'
    encoded=base64.b64encode(('fake-user:'+TOKEN).encode()).decode()
    env={'GIT_CONFIG_COUNT':'2',
         'GIT_CONFIG_KEY_0':f'http.{url}.extraHeader',
         'GIT_CONFIG_VALUE_0':'Authorization: Basic '+encoded,
         'GIT_CONFIG_KEY_1':'http.followRedirects',
         'GIT_CONFIG_VALUE_1':'false',
         'GIT_TERMINAL_PROMPT':'0'}
    return url,env

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
