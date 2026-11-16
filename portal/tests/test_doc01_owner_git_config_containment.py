"""G4 fixture-only tests: no actual tokens, hosts, Git remotes, or production."""
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

MODULE=Path(__file__).resolve().parents[2]/'scripts/owner_git_config_containment.py'
SPEC=importlib.util.spec_from_file_location('g4_config_containment',MODULE)
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

# Assemble synthetic userinfo only at test runtime: never store a literal
# credential-bearing URL in source, even if it uses an invalid example host.
SYNTHETIC_URL=b'https'+b'://'+b'example-user'+b':FAKE_FIXTURE@'+b'example.invalid/project.git'
AUTH=b'[remote "origin"]\n    url = '+SYNTHETIC_URL+b'\n'
PUSH=b'[remote "origin"]\n    pushurl = "'+SYNTHETIC_URL+b'"\n'
PLAIN=b'[remote "origin"]\n    url = https://example.invalid/project.git\n'


class G4GitModeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/'repo-root'
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.uid=os.geteuid()
        self.manifest=self.root/'root-only-manifest.json'

    def config(self,name='project',content=AUTH,mode=0o644):
        base=self.root/name/'.git'
        base.mkdir(parents=True,exist_ok=True)
        base.chmod(0o700)
        base.parent.chmod(0o700)
        target=base/'config'
        target.write_bytes(content)
        target.chmod(mode)
        return target

    def rows(self):
        return mod.build_plan([str(self.root)],self.uid)

    def test_plan_detects_userinfo_without_emitting_credential(self):
        self.config()
        rows=self.rows()
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['auth'])
        self.assertNotIn('FAKE_FIXTURE',json.dumps(rows))
        self.assertEqual(rows[0]['mode'],0o644)

    def test_apply_and_restore_modes_without_touching_git_content(self):
        cfg=self.config()
        before=cfg.read_bytes()
        out=mod.apply_plan(self.rows(),[str(self.root)],self.uid,1,self.manifest)
        self.assertEqual(out['configs_tightened'],1)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode),0o600)
        self.assertEqual(cfg.read_bytes(),before)
        self.assertEqual(stat.S_IMODE(self.manifest.stat().st_mode),0o600)
        self.assertNotIn('FAKE_FIXTURE',self.manifest.read_text())
        out=mod.rollback(self.manifest,self.uid,[str(self.root)])
        self.assertEqual(out['configs_restored'],1)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode),0o644)
        self.assertEqual(cfg.read_bytes(),before)

    def test_pushurl_quoted_is_protected(self):
        self.config(content=PUSH)
        self.assertTrue(self.rows()[0]['auth'])

    def test_normal_url_not_modified(self):
        cfg=self.config(content=PLAIN)
        self.assertFalse(self.rows()[0]['auth'])
        with self.assertRaisesRegex(RuntimeError,'count_mismatch'):
            mod.apply_plan(self.rows(),[str(self.root)],self.uid,1,self.manifest)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode),0o644)
        self.assertFalse(self.manifest.exists())

    def test_wrong_expected_count_rejected_before_manifest(self):
        self.config()
        with self.assertRaisesRegex(RuntimeError,'count_mismatch'):
            mod.apply_plan(self.rows(),[str(self.root)],self.uid,2,self.manifest)
        self.assertFalse(self.manifest.exists())

    def test_wrong_service_user_not_allowed(self):
        self.config()
        rows=self.rows()
        rows[0]['owner_uid']+=1
        with self.assertRaisesRegex(PermissionError,'service_user_not_file_owner'):
            mod.apply_plan(rows,[str(self.root)],self.uid,1,self.manifest)
        self.assertFalse(self.manifest.exists())

    def test_changed_file_after_plan_rejected(self):
        cfg=self.config()
        plan=self.rows()
        cfg.write_bytes(AUTH+b'# changed by another actor\n')
        with self.assertRaisesRegex(RuntimeError,'changed_since_inventory'):
            mod.apply_plan(plan,[str(self.root)],self.uid,1,self.manifest)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode),0o644)

    def test_symlink_target_cannot_be_used(self):
        source=self.config(name='source')
        link=self.root/'link'
        (link/'.git').mkdir(parents=True,exist_ok=True)
        target=link/'.git'/'config'
        target.symlink_to(source)
        with self.assertRaises(ValueError):
            self.rows()

    def test_hardlink_config_denied(self):
        source=self.config()
        alias=self.root/'hardlink'
        os.link(source,alias)
        with self.assertRaisesRegex(ValueError,'single_regular'):
            self.rows()

    def test_control_char_url_fails_closed(self):
        self.config(content=AUTH.replace(b'FAKE_FIXTURE',b'FAKE\x00FIXTURE'))
        with self.assertRaisesRegex(ValueError,'unsafe_git_remote_url'):
            self.rows()

    def test_rollback_refuses_world_readable_manifest(self):
        cfg=self.config()
        mod.apply_plan(self.rows(),[str(self.root)],self.uid,1,self.manifest)
        self.manifest.chmod(0o644)
        with self.assertRaisesRegex(PermissionError,'manifest_not_root_private'):
            mod.rollback(self.manifest,self.uid,[str(self.root)])
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode),0o600)

    def test_rollback_preflight_prevents_partial_restore(self):
        a=self.config('alpha')
        b=self.config('beta')
        mod.apply_plan(self.rows(),[str(self.root)],self.uid,2,self.manifest)
        b.write_bytes(AUTH+b'# changed after apply\n')
        with self.assertRaisesRegex(RuntimeError,'rollback_file_changed'):
            mod.rollback(self.manifest,self.uid,[str(self.root)])
        self.assertEqual(stat.S_IMODE(a.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(b.stat().st_mode),0o600)

if __name__=='__main__':
    unittest.main()
