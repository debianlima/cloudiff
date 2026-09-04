import ast
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'

def load_function(name):
    source=SRC.read_text()
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    module=ast.Module(body=[node],type_ignores=[])
    ns={'re':re}
    exec(compile(module,str(SRC),'exec'),ns)
    return ns[name]

class BancosRunningDetectionTests(unittest.TestCase):
    def test_global_realtime_container_is_not_attributed_to_personal_tenant(self):
        fn=load_function('service_from_container_v21')
        self.assertEqual(fn('iff1742962-testesofa','realtime-dev.supabase-realtime'),'')

    def test_global_realtime_container_still_belongs_to_akadmin(self):
        fn=load_function('service_from_container_v21')
        self.assertEqual(fn('akadmin','realtime-dev.supabase-realtime'),'realtime')

    def test_personal_tenant_container_mapping_remains_intact(self):
        fn=load_function('service_from_container_v21')
        self.assertEqual(fn('iff1742962-testesofa','cloudif_iff1742962-testesofa-db-1'),'db')

if __name__=='__main__':
    unittest.main()
