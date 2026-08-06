from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / 'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
CLIENT_ID = 'project-laboratorio-de-hardware'
SLUG = 'laboratorio-de-hardware'


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


class FakeControl(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/health':
            return self.reply(200, {'ok': True})
        project = {
            'project_id': 'prj_test', 'slug': SLUG, 'name': 'Laboratório de Hardware',
            'owner': 'iff1742962', 'tenant': 'iff1742962-laboratoriodehardware', 'status': 'active',
        }
        if path == '/v1/projects':
            return self.reply(200, {'ok': True, 'projects': [project, {**project, 'slug': 'outro-projeto'}]})
        if path == f'/v1/projects/{SLUG}':
            return self.reply(200, {'ok': True, 'project': project, 'connectors': [], 'acl': [
                {'subject_type': 'user', 'subject': 'iff1742962', 'role': 'owner'},
                {'subject_type': 'group', 'subject': 'CloudIF-Lab-Hardware', 'role': 'viewer'},
            ]})
        return self.reply(404, {'ok': False, 'error': 'not_found'})


class FakeAgent(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if urlparse(self.path).path == '/v1/clients':
            return self.reply(200, {'ok': True, 'clients': [{
                'client_id': CLIENT_ID, 'status': 'active', 'owner_user': 'iff1742962',
                'project_slugs_json': json.dumps([SLUG]),
                'scopes_json': json.dumps(['project:read', 'workspace:prepare']),
            }]})
        return self.reply(404, {'ok': False})

    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0'))
        data = json.loads(self.rfile.read(n) or b'{}')
        if urlparse(self.path).path == '/v1/authorize-public':
            allowed = data.get('client_id') == CLIENT_ID and data.get('project_slug') == SLUG
            return self.reply(200, {
                'ok': allowed, 'reason': 'allowed' if allowed else 'project_denied',
                'client_id': CLIENT_ID, 'owner_user': 'iff1742962',
                'authorized_user': data.get('authorized_user'), 'project_slugs': [SLUG],
                'minute_calls': 1, 'daily_calls': 1,
            })
        return self.reply(404, {'ok': False})


class MCPPublicOAuthFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control_port = free_port()
        cls.agent_port = free_port()
        cls.gateway_port = free_port()
        cls.control = ThreadingHTTPServer(('127.0.0.1', cls.control_port), FakeControl)
        cls.agent = ThreadingHTTPServer(('127.0.0.1', cls.agent_port), FakeAgent)
        cls.control_thread = threading.Thread(target=cls.control.serve_forever, daemon=True)
        cls.agent_thread = threading.Thread(target=cls.agent.serve_forever, daemon=True)
        cls.control_thread.start(); cls.agent_thread.start()
        env = os.environ.copy()
        env.update({
            'CLOUDIF_MCP_HOST': '127.0.0.1', 'CLOUDIF_MCP_PORT': str(cls.gateway_port),
            'CLOUDIF_MCP_PUBLIC_ORIGIN': 'https://cloudiff.duckdns.org',
            'CLOUDIF_CONTROL_URL': f'http://127.0.0.1:{cls.control_port}', 'CLOUDIF_CONTROL_TOKEN': 'test',
            'CLOUDIF_AGENT_URL': f'http://127.0.0.1:{cls.agent_port}', 'CLOUDIF_AGENT_ADMIN_TOKEN': 'test',
        })
        cls.proc = subprocess.Popen(['python3', str(GATEWAY)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                c = http.client.HTTPConnection('127.0.0.1', cls.gateway_port, timeout=1)
                c.request('GET', '/health'); r = c.getresponse(); r.read(); c.close()
                if r.status in (200, 503):
                    break
            except OSError:
                time.sleep(.1)
        else:
            out, err = cls.proc.communicate(timeout=2)
            raise RuntimeError(f'gateway did not start: {out!r} {err!r}')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(timeout=3)
        except subprocess.TimeoutExpired: cls.proc.kill()
        cls.control.shutdown(); cls.agent.shutdown()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.gateway_port, timeout=5)
        payload = body.encode() if isinstance(body, str) else body
        conn.request(method, path, body=payload, headers=headers or {})
        response = conn.getresponse(); raw = response.read(); returned_headers = dict(response.getheaders()); conn.close()
        return response.status, returned_headers, raw

    def oauth_token(self):
        verifier = 'a' * 64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        callback = 'http://127.0.0.1:53682/callback'
        query = urlencode({
            'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': callback,
            'state': 'state-test', 'code_challenge': challenge, 'code_challenge_method': 'S256',
        })
        status, headers, _ = self.request('GET', '/cloudiff/mcp/oauth/authorize?' + query, headers={
            'X-authentik-username': 'iff1742962', 'X-authentik-groups': 'CloudIF-Lab-Hardware|Domain Users',
        })
        self.assertEqual(status, 302)
        code = parse_qs(urlparse(headers['Location']).query)['code'][0]
        form = urlencode({
            'grant_type': 'authorization_code', 'client_id': CLIENT_ID, 'code': code,
            'redirect_uri': callback, 'code_verifier': verifier,
        })
        status, _, raw = self.request('POST', '/cloudiff/mcp/oauth/token', form, {
            'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': str(len(form)),
        })
        self.assertEqual(status, 200, raw)
        data = json.loads(raw)
        self.assertNotIn('client_secret', data)
        return data['access_token']

    def rpc(self, token, method, params=None, request_id=1, expected_status=200):
        raw = json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params or {}})
        status, _, body = self.request('POST', '/mcp', raw, {
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token,
            'Content-Length': str(len(raw)),
        })
        self.assertEqual(status, expected_status, body)
        return json.loads(body)

    def test_public_oauth_pkce_tools_and_project_isolation(self):
        token = self.oauth_token()
        initialized = self.rpc(token, 'initialize')
        self.assertEqual(initialized['result']['serverInfo']['name'], 'cloudif-mcp-gateway')
        tools = self.rpc(token, 'tools/list', request_id=2)['result']['tools']
        self.assertTrue(tools)
        self.assertTrue(all(set(('readOnlyHint','destructiveHint','idempotentHint','openWorldHint')) <= set(t['annotations']) for t in tools))
        project = self.rpc(token, 'tools/call', {'name': 'project.get', 'arguments': {'slug': SLUG}}, 3)
        self.assertNotIn('error', project)
        denied = self.rpc(token, 'tools/call', {'name': 'project.get', 'arguments': {'slug': 'outro-projeto'}}, 4, expected_status=403)
        self.assertEqual(denied['error']['message'], 'project_denied')
        listed = self.rpc(token, 'tools/call', {'name': 'project.list', 'arguments': {}}, 5)
        content = json.loads(listed['result']['content'][0]['text'])
        self.assertEqual([row['slug'] for row in content], [SLUG])

    def test_project_specific_openapi_schema_and_privacy(self):
        status, headers, raw = self.request('GET', f'/cloudiff/mcp/openapi/{CLIENT_ID}.json')
        self.assertEqual(status, 200, raw)
        schema = json.loads(raw)
        self.assertEqual(schema['openapi'], '3.1.0')
        self.assertEqual(schema['x-cloudiff-project'], SLUG)
        self.assertEqual(schema['x-cloudiff-client-id'], CLIENT_ID)
        self.assertEqual(schema['servers'], [{'url': 'https://cloudiff.duckdns.org'}])
        self.assertEqual(schema['info']['x-privacy-policy-url'], 'https://cloudiff.duckdns.org/cloudiff/mcp/privacy')
        paths = schema['paths']
        self.assertFalse(paths['/cloudiff/mcp/actions/v1/project']['get']['x-openai-isConsequential'])
        self.assertFalse(paths['/cloudiff/mcp/actions/v1/read']['post']['x-openai-isConsequential'])
        self.assertTrue(paths['/cloudiff/mcp/actions/v1/write']['post']['x-openai-isConsequential'])
        schemas = schema['components']['schemas']
        self.assertIsInstance(schemas, dict)
        read_ref = paths['/cloudiff/mcp/actions/v1/read']['post']['requestBody']['content']['application/json']['schema']['$ref']
        write_ref = paths['/cloudiff/mcp/actions/v1/write']['post']['requestBody']['content']['application/json']['schema']['$ref']
        read_schema = schemas[read_ref.rsplit('/', 1)[-1]]
        write_schema = schemas[write_ref.rsplit('/', 1)[-1]]
        read_enum = read_schema['properties']['tool']['enum']
        write_enum = write_schema['properties']['tool']['enum']
        self.assertIn('project.get', read_enum)
        self.assertNotIn('workspace.prepare', read_enum)
        self.assertIn('workspace.prepare', write_enum)
        for name, item in schemas.items():
            if item.get('type') == 'object':
                self.assertIn('properties', item, name)
        response_ref = paths['/cloudiff/mcp/actions/v1/project']['get']['responses']['200']['content']['application/json']['schema']['$ref']
        self.assertEqual(response_ref, '#/components/schemas/ActionResponse')
        oauth = schema['components']['securitySchemes']['cloudiffOAuth']['flows']['authorizationCode']
        self.assertEqual(oauth['authorizationUrl'], 'https://cloudiff.duckdns.org/cloudiff/mcp/oauth/authorize')
        self.assertEqual(oauth['tokenUrl'], 'https://cloudiff.duckdns.org/cloudiff/mcp/oauth/token')
        status, headers, raw = self.request('HEAD', f'/cloudiff/mcp/openapi/{CLIENT_ID}.json')
        self.assertEqual(status, 200)
        self.assertIn('application/json', headers.get('Content-Type', ''))
        self.assertEqual(raw, b'')
        status, headers, raw = self.request('GET', '/cloudiff/mcp/privacy')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers.get('Content-Type', ''))
        self.assertIn('Privacidade do conector CloudIFF', raw.decode())
        status, headers, raw = self.request('HEAD', '/cloudiff/mcp/privacy')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers.get('Content-Type', ''))
        self.assertEqual(raw, b'')

    def test_actions_rest_bridge_is_bound_to_project(self):
        token = self.oauth_token()
        auth = {'Authorization': 'Bearer ' + token}
        status, _, raw = self.request('GET', '/cloudiff/mcp/actions/v1/project', headers=auth)
        self.assertEqual(status, 200, raw)
        data = json.loads(raw)
        self.assertEqual(data['project_slug'], SLUG)
        self.assertEqual(data['result']['slug'], SLUG)
        status, _, raw = self.request('GET', '/cloudiff/mcp/actions/v1/tools', headers=auth)
        self.assertEqual(status, 200, raw)
        names = [item['name'] for item in json.loads(raw)['result']]
        self.assertIn('project.get', names)
        self.assertIn('workspace.prepare', names)
        payload = json.dumps({'tool': 'project.get', 'arguments': {'slug': 'outro-projeto'}})
        status, _, raw = self.request('POST', '/cloudiff/mcp/actions/v1/read', payload, {
            **auth, 'Content-Type': 'application/json', 'Content-Length': str(len(payload)),
        })
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['result']['slug'], SLUG)
        payload = json.dumps({'tool': 'workspace.prepare', 'arguments': {}})
        status, _, raw = self.request('POST', '/cloudiff/mcp/actions/v1/read', payload, {
            **auth, 'Content-Type': 'application/json', 'Content-Length': str(len(payload)),
        })
        self.assertEqual(status, 403, raw)
        self.assertEqual(json.loads(raw)['error'], 'write_tool_not_allowed_on_read_endpoint')
        payload = json.dumps({'tool': 'project.get', 'arguments': {}})
        status, _, raw = self.request('POST', '/cloudiff/mcp/actions/v1/write', payload, {
            **auth, 'Content-Type': 'application/json', 'Content-Length': str(len(payload)),
        })
        self.assertEqual(status, 403, raw)
        self.assertEqual(json.loads(raw)['error'], 'read_tool_not_allowed_on_write_endpoint')

    def test_authorize_requires_authenticated_user_and_s256(self):
        callback = 'http://127.0.0.1:53682/callback'
        base = {'response_type':'code','client_id':CLIENT_ID,'redirect_uri':callback,'code_challenge':'abc'}
        status, _, _ = self.request('GET', '/cloudiff/mcp/oauth/authorize?' + urlencode(base))
        self.assertEqual(status, 400)
        status, _, _ = self.request('GET', '/cloudiff/mcp/oauth/authorize?' + urlencode(base), headers={'X-authentik-username':'iff1742962'})
        self.assertEqual(status, 400)


if __name__ == '__main__':
    unittest.main()
