import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "apply_portal_v2_lib_release.sh"


class PortalV2LibReleaseContractTests(unittest.TestCase):
    def test_release_script_contract(self):
        self.assertTrue(SCRIPT.is_file(), "rollout versionado precisa existir")
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "/srv/cloudif/lib-releases/portal-v2",
            "/srv/cloudif/releases",
            "pre-state",
            "rollback.sh",
            "CLOUDIF_PORTAL_HOST=127.0.0.1",
            "CLOUDIFF_PORTAL_V2_SHADOW_PORT",
            "python3 -m py_compile",
            "mv -Tf",
            "current",
            "previous",
            "cloudif-admin-portal.service",
            "Meus sites",
            "Meus bancos",
            "Saúde da plataforma",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("cp -a /srv/cloudif/lib ", text)
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_prepare_is_immutable_idempotent_and_keeps_live_untouched(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            root = Path(td)
            source = root / "candidate.py"
            live = root / "live" / "cloudif_portal_v2_coexist.py"
            releases = root / "lib-releases" / "portal-v2"
            metadata = root / "releases"
            state_dir = root / "state"
            source.write_text("VALUE = 'candidate'\n", encoding="utf-8")
            live.parent.mkdir(parents=True)
            live.write_text("VALUE = 'baseline'\n", encoding="utf-8")
            live_before = live.read_bytes()
            candidate_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            env = os.environ.copy()
            env.update(
                CLOUDIFF_PORTAL_V2_ALLOW_NONROOT="1",
                CLOUDIFF_PORTAL_V2_SOURCE_FILE=str(source),
                CLOUDIFF_PORTAL_V2_LIVE_FILE=str(live),
                CLOUDIFF_PORTAL_V2_RELEASE_ROOT=str(releases),
                CLOUDIFF_RELEASE_META_ROOT=str(metadata),
                CLOUDIFF_PORTAL_V2_STATE=str(state_dir),
            )
            first = subprocess.run(
                ["bash", str(SCRIPT), "prepare"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("PORTAL_V2_LIB_PREPARE=PASS", first.stdout)
            release_id = "portal-v2-lib-" + candidate_hash[:16]
            payload = releases / release_id / "cloudif_portal_v2_coexist.py"
            self.assertEqual(payload.read_bytes(), source.read_bytes())
            self.assertFalse(payload.stat().st_mode & stat.S_IWUSR)
            self.assertEqual(live.read_bytes(), live_before)
            current_target = (releases / "current").resolve()
            self.assertTrue(current_target.name.startswith("baseline-"))

            meta = metadata / release_id
            self.assertTrue((meta / "pre-state" / "live.sha256").is_file())
            rollback = meta / "rollback.sh"
            self.assertTrue(rollback.is_file())
            self.assertTrue(os.access(rollback, os.X_OK))
            subprocess.run(["bash", "-n", str(rollback)], check=True)

            second = subprocess.run(
                ["bash", str(SCRIPT), "prepare"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("PORTAL_V2_LIB_PREPARE=PASS", second.stdout)
            self.assertEqual((releases / "current").resolve(), current_target)
            self.assertEqual(payload.read_bytes(), source.read_bytes())
            self.assertEqual(live.read_bytes(), live_before)

            for item in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                try:
                    if item.is_dir():
                        item.chmod(0o755)
                    elif not item.is_symlink():
                        item.chmod(item.stat().st_mode | stat.S_IWUSR)
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    unittest.main()
