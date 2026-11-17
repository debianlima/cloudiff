"""Independent PR41 security regression: canonical public_number on manual activation.

Load the effective release/activate handler from AST. No real DB, Komodo,
Docker, network, permissions, or secrets; all effects are simulated.
"""
import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'

class PublicationActivationAliasBindingTests(unittest.TestCase):
    def _call(self,requested):
        tree=ast.parse(SRC.read_text())
        handlers=[node for node in tree.body if isinstance(node,ast.FunctionDef)
                  and node.name=='cloudif_publication_release_activate']
        self.assertEqual(len(handlers),2)
        operations=[]
        stored={'project':'alpha','public_number':1200,'publication_number':7,
                'container':'cloudif-p1200-d3-web','deploy_number':3,'status':'ready'}
        class Noop:
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def finish(self):operations.append(('journal_finish',))
        def db_query(sql,params=()):
            operations.append(('query_params',tuple(params)))
            if len(params)==3 and tuple(params)!=(stored['project'],
                   stored['publication_number'],stored['public_number']):
                return []
            return [stored]
        def fake_run(argv,**kwargs):
            operations.append(('docker',argv[1]))
            return SimpleNamespace(returncode=0,stdout='true',stderr='')
        def reconnect(public_number,destination):
            operations.append(('alias',public_number,destination))
            return None
        namespace={
            '_cloudif_pub_auth':lambda _:True,
            '_cloudif_pub_json':lambda _:dict(project='alpha',
                       public_number=requested,publication_number=7),
            'safe_slug':lambda slug:slug,
            'db_query':db_query,
            'subprocess':SimpleNamespace(run=fake_run,PIPE=-1,DEVNULL=-3),
            '_cloudif_wait_health':lambda *_:{'ok':True},
            '_cloudif_v145_operation_gate':lambda *_:Noop(),
            '_cloudif_v144_reconnect_active':reconnect,
            '_cloudif_v144_atomic_updates':lambda updates:operations.append(('db_updates',len(updates))),
            'now':lambda :'synthetic',
            'send':lambda handler,status,payload:(operations.append(('response',status)),
                                                {'status':status,'payload':payload})[1],
            'sqlite3':sqlite3,
        }
        exec(compile(ast.Module(body=[handlers[-1]],type_ignores=[]),str(SRC),'exec'),
             namespace,namespace)
        return namespace['cloudif_publication_release_activate'](object()),operations

    def test_cross_public_alias_never_reaches_docker_or_network(self):
        result,events=self._call(requested=9999)
        self.assertEqual(result['status'],404)
        self.assertEqual([e for e in events if e[0]=='query_params'],
                         [('query_params',('alpha',7,9999))])
        self.assertFalse(any(e[0] in ('alias','docker','db_updates','journal_finish') for e in events))

    def test_matching_alias_still_proceeds_in_synthetic_harness(self):
        result,events=self._call(requested=1200)
        self.assertEqual(result['status'],200)
        self.assertIn(('alias',1200,'cloudif-p1200-d3-web'),events)
        self.assertIn(('journal_finish',),events)
        self.assertIn(('db_updates',2),events)

if __name__=='__main__':unittest.main()

