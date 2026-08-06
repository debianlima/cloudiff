from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import re
import types
import unittest
import urllib.parse
from pathlib import Path

SOURCE = Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
TREE = ast.parse(SOURCE)
WANTED_FUNCS = {
    '_change_set_canonical_digest', '_change_set_validate_payload',
    '_change_set_existing_pr', 'cloudif_proposal_change_set_create',
}
WANTED_ASSIGNS = {
    '_CHANGESET_WORKSPACE_RE', '_CHANGESET_DIGEST_RE', '_CHANGESET_PATH_RE',
    '_CHANGESET_MAX_FILES', '_CHANGESET_MAX_FILE_BYTES', '_CHANGESET_MAX_TOTAL_BYTES',
}
NODES = []
for node in TREE.body:
    if isinstance(node, ast.FunctionDef) and node.name in WANTED_FUNCS:
        NODES.append(node)
    elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in WANTED_ASSIGNS for target in node.targets):
        NODES.append(node)
MODULE = ast.Module(body=NODES, type_ignores=[])
ast.fix_missing_locations(MODULE)


class FakeForgejo:
    def __init__(self, fail_on_put=False):
        self.base = {
            'a.txt': {'content': 'old', 'sha': 'forgejo-sha-a'},
            'delete.txt': {'content': 'remove', 'sha': 'forgejo-sha-delete'},
        }
        self.branch = None
        self.branch_files = {}
        self.pr = None
        self.deleted_branch = False
        self.fail_on_put = fail_on_put

    def api(self, method, path, payload=None, timeout=45):
        if method == 'GET' and '/branches/' in path:
            return {'ok': self.branch is not None, 'status': 200 if self.branch else 404, 'data': {}}
        if method == 'POST' and path.endswith('/branches'):
            self.branch = payload['new_branch_name']; self.branch_files = dict(self.base)
            return {'ok': True, 'status': 201, 'data': {'name': self.branch}}
        if method == 'DELETE' and '/branches/' in path:
            self.branch = None; self.branch_files = {}; self.deleted_branch = True
            return {'ok': True, 'status': 204, 'data': {}}
        if method == 'POST' and path.endswith('/pulls'):
            self.pr = {'number': 7, 'title': payload['title'], 'draft': True, 'state': 'open', 'html_url': 'https://forgejo/pr/7', 'head': {'ref': payload['head']}}
            return {'ok': True, 'status': 201, 'data': self.pr}
        if method == 'GET' and '/pulls?' in path:
            return {'ok': True, 'status': 200, 'data': [self.pr] if self.pr else []}
        return {'ok': False, 'status': 500, 'data': {}}

    def get_file(self, owner, repo, path, branch):
        source = self.base if branch == 'main' else self.branch_files
        item = source.get(path)
        return {'exists': bool(item), 'content': item['content'] if item else None, 'sha': item['sha'] if item else '', 'error': False}

    def put_file(self, owner, repo, path, branch, content, message, sha=''):
        if self.fail_on_put:
            return 500, {'error': 'forced'}
        self.branch_files[path] = {'content': content, 'sha': 'new-sha-' + path}
        return 201, {'commit': {'sha': hashlib.sha1(path.encode()).hexdigest()}}

    def delete_file(self, owner, repo, path, branch, message, sha):
        self.branch_files.pop(path, None)
        return 200, {'commit': {'sha': hashlib.sha1(('delete:' + path).encode()).hexdigest()}}


def namespace(fake):
    events = []
    ns = {
        're': re, 'base64': base64, 'hashlib': hashlib, 'hmac': hmac,
        'json': json, 'urllib': types.SimpleNamespace(parse=urllib.parse),
        'SLUG_RE': re.compile(r'^[a-z0-9][a-z0-9._-]{1,62}$'),
        '_PROPOSAL_APPROVAL_RE': re.compile(r'^apr_[a-f0-9]{20}$'),
        'load_project': lambda slug: {'project_slug': slug},
        '_proposal_repo': lambda project, slug: ('owner', 'repo'),
        '_proposal_api': fake.api,
        '_v118_get_file': fake.get_file,
        '_v118_put_file': fake.put_file,
        '_v118_delete_file': fake.delete_file,
        'save_event': lambda *args: events.append(args),
        'now': lambda: '2026-08-06T18:00:00',
        'json_response': lambda handler, code, data: (code, data),
        'ValueError': ValueError,
    }
    exec(compile(MODULE, '<forja-change-set>', 'exec'), ns)
    return ns, events


def payload(ns):
    changes = [
        {'operation': 'update', 'path': 'a.txt', 'expected_sha256': hashlib.sha256(b'old').hexdigest(), 'content_base64': base64.b64encode(b'new').decode(), 'content_sha256': hashlib.sha256(b'new').hexdigest(), 'size': 3},
        {'operation': 'create', 'path': 'new.txt', 'content_base64': base64.b64encode(b'created').decode(), 'content_sha256': hashlib.sha256(b'created').hexdigest(), 'size': 7},
        {'operation': 'delete', 'path': 'delete.txt', 'expected_sha256': hashlib.sha256(b'remove').hexdigest()},
        {'operation': 'mkdir', 'path': 'scripts', 'effective_path': 'scripts/.gitkeep', 'content_base64': '', 'content_sha256': hashlib.sha256(b'').hexdigest(), 'size': 0},
    ]
    digest = ns['_change_set_canonical_digest']('project-a', 'main', 'a' * 64, 'Normalize project', 'Validated changes', changes)
    return {
        'project_slug': 'project-a', 'base_branch': 'main',
        'workspace_id': 'ws_' + '1' * 24, 'change_set_digest': digest,
        'archive_sha256': 'a' * 64, 'ref': 'main', 'title': 'Normalize project',
        'description': 'Validated changes', 'changes': changes,
        'trace_id': 'trace-1', 'approval_id': 'apr_' + '2' * 20,
        'requested_by': 'project-client',
    }


class ForjaChangeSetProposalTests(unittest.TestCase):
    def test_complete_change_set_creates_branch_commits_and_draft_pr(self):
        fake = FakeForgejo(); ns, events = namespace(fake); data = payload(ns)
        code, result = ns['cloudif_proposal_change_set_create'](None, data)
        self.assertEqual(code, 201)
        self.assertTrue(result['ok'])
        self.assertEqual(result['file_count'], 4)
        self.assertTrue(result['pull_request']['draft'])
        self.assertFalse(result['main_modified'])
        self.assertEqual(fake.base['a.txt']['content'], 'old')
        self.assertEqual(fake.branch_files['a.txt']['content'], 'new')
        self.assertIn('new.txt', fake.branch_files)
        self.assertNotIn('delete.txt', fake.branch_files)
        self.assertIn('scripts/.gitkeep', fake.branch_files)
        self.assertTrue(events)
        self.assertNotIn('content_base64', json.dumps(events))

    def test_commit_failure_deletes_branch_and_keeps_main(self):
        fake = FakeForgejo(fail_on_put=True); ns, _ = namespace(fake); data = payload(ns)
        code, result = ns['cloudif_proposal_change_set_create'](None, data)
        self.assertEqual(code, 502)
        self.assertTrue(result['branch_cleaned'])
        self.assertFalse(result['main_modified'])
        self.assertTrue(fake.deleted_branch)
        self.assertEqual(fake.base['a.txt']['content'], 'old')
        self.assertIsNone(fake.pr)

    def test_digest_or_base_hash_mismatch_is_rejected_before_branch(self):
        fake = FakeForgejo(); ns, _ = namespace(fake); data = payload(ns)
        data['change_set_digest'] = 'f' * 64
        code, result = ns['cloudif_proposal_change_set_create'](None, data)
        self.assertEqual(code, 400)
        self.assertEqual(result['error'], 'change_set_digest_mismatch')
        self.assertIsNone(fake.branch)
        data = payload(ns); data['changes'][0]['expected_sha256'] = '0' * 64
        data['change_set_digest'] = ns['_change_set_canonical_digest']('project-a', 'main', 'a' * 64, 'Normalize project', 'Validated changes', data['changes'])
        code, result = ns['cloudif_proposal_change_set_create'](None, data)
        self.assertEqual(code, 409)
        self.assertEqual(result['error'], 'hash_mismatch')
        self.assertIsNone(fake.branch)

    def test_route_and_mirrors_are_present(self):
        self.assertIn('/project/proposal/change-set/create', SOURCE)
        self.assertIn('content_stored', SOURCE)
        self.assertIn("branch='cloudif-proposal-'+request['change_set_digest'][:20]", SOURCE)
        mirror = Path('components/runtime/usr/local/sbin/cloudif-forja-agent.py').read_text()
        self.assertEqual(SOURCE, mirror)


if __name__ == '__main__':
    unittest.main()
