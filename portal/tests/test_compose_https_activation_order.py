import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[2]
PATHS=[
 ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py',
 ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py',
]

class ComposeHTTPSActivationOrder(unittest.TestCase):
    def test_publisher_failure_cannot_reach_bridge_activation(self):
        for path in PATHS:
            tree=ast.parse(path.read_text())
            f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_publish_linked_compose_homologated_candidate')
            lines=path.read_text().splitlines()
            body='\n'.join(lines[f.lineno-1:f.end_lineno])
            publisher=body.index("pstatus,publisher=_post('http://10.62.91.3/publish'")
            failure=body.index("if pstatus//100!=2 or not publisher.get('ok')",publisher)
            activation=body.index("activation=_multiservice_activate_bridge(")
            stable=body.index("if not _external_ok(stable)")
            cleanup=body.index("h_cleanup=_publisher_delete_stage")
            self.assertLess(publisher,failure)
            self.assertLess(failure,activation)
            self.assertLess(activation,stable)
            self.assertLess(stable,cleanup)

    def test_runtime_effect_blocked_on_publisher_error(self):
        for path in PATHS:
            tree=ast.parse(path.read_text())
            f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_publish_linked_compose_homologated_candidate')
            i=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Tuple) and any(isinstance(x,ast.Name) and x.id=='pstatus' for x in t.elts) for t in n.targets))
            fragment=ast.Module(body=f.body[i:i+3],type_ignores=[])
            activate=Mock()
            env={'_post':Mock(return_value=(422,{'ok':False})),'_publication_error':Mock(return_value='HTTPS falhou'),'_multiservice_activate_bridge':activate,'slug':'demo','num':1021,'publication':13,'candidate':{'deploy_number':13},'alias':'demo','npm_token':'test-only','trace':'test'}
            with self.assertRaisesRegex(RuntimeError,'Publisher /publish'):
                exec(compile(fragment,str(path),'exec'),env)
            activate.assert_not_called()

if __name__=='__main__':unittest.main()
