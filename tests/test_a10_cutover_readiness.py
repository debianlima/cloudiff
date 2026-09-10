import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'deploy/a10-release-gate/cutover-readiness.sh'


class CutoverReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'cloudif'
        self.release_id = 'candidate-test'
        self.source_commit = 'a' * 40
        self.pre = self.root / 'releases' / self.release_id / 'pre-state'
        self.candidate = self.root / 'releases' / self.release_id / 'candidate'
        self.current_release = self.root / 'app-releases' / 'portal' / 'old'
        self.previous_release = self.root / 'app-releases' / 'portal' / 'older'
        self.portal_release = self.root / 'lib-releases' / 'portal-v2' / 'old'
        for p in (self.pre, self.candidate, self.current_release, self.previous_release, self.portal_release, self.root / 'app-pointers', self.root / 'lib'):
            p.mkdir(parents=True, exist_ok=True)
        (self.current_release / 'app.py').write_text('old app\n')
        (self.previous_release / 'app.py').write_text('older app\n')
        (self.portal_release / 'ui.py').write_text('old portal\n')
        (self.root / 'lib' / 'helper.py').write_text('old helper\n')
        os.symlink(self.current_release, self.root / 'app-pointers' / 'portal-current')
        os.symlink(self.previous_release, self.root / 'app-pointers' / 'portal-previous')
        os.symlink(self.portal_release, self.root / 'lib' / 'portal')
        self.systemctl = Path(self.tmp.name) / 'systemctl'
        self.systemctl.write_text("""#!/bin/sh
if [ \"$1\" = show ]; then
  echo ActiveState=active
  echo SubState=running
  echo MainPID=4242
  exit 0
fi
if [ \"$1\" = is-active ]; then exit 0; fi
exit 0
""")
        self.systemctl.chmod(0o755)
        self._write_prestate()
        self.archive = self.candidate / f'{self.release_id}.tar.gz'
        self._write_candidate()
        self.archive_sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _sha_line(path):
        return f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path}\n"

    def _write_prestate(self):
        (self.pre / 'current.target').write_text(str(self.current_release) + '\n')
        (self.pre / 'previous.target').write_text(str(self.previous_release) + '\n')
        (self.pre / 'portal.type').write_text('symlink\n')
        (self.pre / 'portal.link').write_text(str(self.portal_release) + '\n')
        (self.pre / 'portal.real').write_text(str(self.portal_release) + '\n')
        (self.pre / 'service.txt').write_text('ActiveState=active\nSubState=running\nMainPID=4242\n')
        (self.pre / 'current.sha256').write_text(self._sha_line(self.current_release / 'app.py'))
        portal_sha = hashlib.sha256((self.portal_release / 'ui.py').read_bytes()).hexdigest()
        (self.pre / 'portal-runtime.sha256').write_text(f'{portal_sha}  ./ui.py\n')
        (self.pre / 'portal-runtime.tgz').write_bytes(b'placeholder')
        (self.pre / 'lib-root.sha256').write_text(self._sha_line(self.root / 'lib' / 'helper.py'))
        (self.pre / 'lib-root-files.tgz').write_bytes(b'placeholder')
        rows = []
        for p in sorted(self.pre.iterdir()):
            if p.name in {'PRESTATE.SHA256', 'PRESTATE_COMPLETE'} or not p.is_file():
                continue
            rows.append(self._sha_line(p))
        (self.pre / 'PRESTATE.SHA256').write_text(''.join(rows))
        (self.pre / 'PRESTATE_COMPLETE').touch()

    def _write_candidate(self):
        build = Path(self.tmp.name) / self.release_id
        build.mkdir()
        manifest = {
            'release_id': self.release_id,
            'source_commit': self.source_commit,
            'promotion_authorized': False,
            'requires_live_preflight': True,
            'files': {},
        }
        (build / 'release-manifest.json').write_text(json.dumps(manifest))
        with tarfile.open(self.archive, 'w:gz') as tf:
            tf.add(build, arcname=self.release_id)

    def run_check(self, expected_sha=None):
        return subprocess.run(
            [str(SCRIPT), self.release_id, expected_sha or self.archive_sha, self.source_commit],
            env={**os.environ, 'CLOUDIF_ROOT': str(self.root), 'SYSTEMCTL_BIN': str(self.systemctl)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_ready_candidate_passes_without_mutation(self):
        before = sorted((p.relative_to(self.root), p.stat().st_mtime_ns, p.stat().st_size) for p in self.root.rglob('*') if p.is_file())
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CUTOVER_READINESS=PASS', result.stdout)
        after = sorted((p.relative_to(self.root), p.stat().st_mtime_ns, p.stat().st_size) for p in self.root.rglob('*') if p.is_file())
        self.assertEqual(before, after)

    def test_wrong_candidate_hash_fails_closed(self):
        result = self.run_check('0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('candidate archive hash mismatch', result.stderr)

    def test_active_pointer_drift_fails_closed(self):
        other = self.root / 'app-releases' / 'portal' / 'other'
        other.mkdir(parents=True)
        current = self.root / 'app-pointers' / 'portal-current'
        current.unlink()
        os.symlink(other, current)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('portal-current drifted since preflight', result.stderr)

    def test_tampered_prestate_fails_closed(self):
        (self.pre / 'service.txt').write_text('tampered\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pre-state integrity failed', result.stderr)


if __name__ == '__main__':
    unittest.main()
