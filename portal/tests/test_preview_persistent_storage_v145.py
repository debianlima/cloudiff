from pathlib import Path
import ast,json,os,re,tempfile,unittest

ROOT=Path(__file__).resolve().parents[2]
AGENT=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'

class PreviewPersistentStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=AGENT.read_text();cls.tree=ast.parse(cls.source)
    def function_source(self,name):
        nodes=[n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
        self.assertTrue(nodes,name);n=nodes[-1];lines=self.source.splitlines(True)
        return ''.join(lines[n.lineno-1:n.end_lineno])
    def load_helper(self):
        ns={'Path':Path,'json':json,'os':os,'re':re}
        exec(self.function_source('_cloudif_v144_preview_persistent_mounts'),ns)
        return ns['_cloudif_v144_preview_persistent_mounts']
    def test_manifest_creates_managed_mount_outside_checkout(self):
        fn=self.load_helper()
        with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as data:
            root=Path(td);(root/'.cloudif').mkdir()
            (root/'.cloudif/runtime.json').write_text(json.dumps({'preview':{'persistentStorage':[{'name':'data'},{'name':'attachments'}]}}))
            old=os.environ.get('CLOUDIF_PREVIEW_DATA_ROOT');os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=data
            try:r=fn(root,1022)
            finally:
                if old is None:os.environ.pop('CLOUDIF_PREVIEW_DATA_ROOT',None)
                else:os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=old
            self.assertEqual([x['target'] for x in r],['/var/lib/cloudif-data/data','/var/lib/cloudif-data/attachments'])
            self.assertTrue(all(Path(x['source']).is_dir() for x in r))
            self.assertTrue(all(str(Path(x['source'])).startswith(data) for x in r))
            self.assertTrue(all((Path(x['source']).stat().st_mode & 0o077)==0 for x in r))
    def test_manifest_rejects_invalid_entries(self):
        fn=self.load_helper()
        bad=[
          {'preview':{'persistentStorage':[{'name':'../data'}]}},
          {'preview':{'persistentStorage':[{'name':'data','source':'/tmp'}]}},
          {'preview':{'persistentStorage':[{'name':'data'},{'name':'data'}]}},
        ]
        for manifest in bad:
            with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as data:
                root=Path(td);(root/'.cloudif').mkdir();(root/'.cloudif/runtime.json').write_text(json.dumps(manifest))
                old=os.environ.get('CLOUDIF_PREVIEW_DATA_ROOT');os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=data
                try:
                    with self.assertRaises(ValueError):fn(root,1022)
                finally:
                    if old is None:os.environ.pop('CLOUDIF_PREVIEW_DATA_ROOT',None)
                    else:os.environ['CLOUDIF_PREVIEW_DATA_ROOT']=old
    def test_stack_and_sync_consume_manifest(self):
        stack=self.function_source('_cloudif_v144_preview_stack')
        ensure=self.function_source('cloudif_preview_request')
        self.assertIn('_cloudif_v144_preview_persistent_mounts(base_dir,public_number)',stack)
        self.assertIn("mounts.extend((item['target'],item['source'],False)",stack)
        self.assertIn('source_changed=bool(old_head and new_head and old_head!=new_head)',ensure)
        self.assertIn("_cloudif_preview_create(project,num,payload.get('actor') or 'portal'",ensure)

if __name__=='__main__':unittest.main()
