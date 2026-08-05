from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ProvisionWorkerSystemdRecoveryTest(unittest.TestCase):
    def test_project_jobs_run_in_independent_systemd_units(self):
        source = (
            ROOT / "components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py"
        ).read_text()
        block = source[source.index("def _project_provision_unit"):source.index("WORKER_CODE =")]
        for marker in (
            '"/usr/bin/systemd-run"',
            '"--collect"',
            '"--property=Type=exec"',
            '"--property=RuntimeMaxSec=4h"',
            '"/usr/bin/flock"',
            '"/srv/cloudif/lib/cloudif_project_provision_worker.py"',
            'job["systemd_unit"]',
        ):
            self.assertIn(marker, block)
        self.assertNotIn("subprocess.Popen(", block)
        self.assertNotIn("pass_fds=", block)
        self.assertNotIn("start_new_session=True", block)

    def test_interrupted_jobs_have_periodic_recovery(self):
        source = (
            ROOT / "components/control-plane/srv/cloudif/lib/cloudif_project_provision_recover.py"
        ).read_text()
        for marker in (
            "project-provision-*.json",
            "status not in {\"queued\", \"running\"}",
            "CLOUDIF_PROJECT_JOB_STALE_SECONDS",
            '"/usr/bin/systemd-run"',
            '"/usr/bin/flock"',
            "systemctl",
            "is-active",
        ):
            self.assertIn(marker, source)

        service = (
            ROOT / "components/control-plane/etc/systemd/system/cloudif-project-provision-recover.service"
        ).read_text()
        timer = (
            ROOT / "components/control-plane/etc/systemd/system/cloudif-project-provision-recover.timer"
        ).read_text()
        self.assertIn("cloudif_project_provision_recover.py", service)
        self.assertIn("OnUnitInactiveSec=1min", timer)
        self.assertIn("Persistent=true", timer)

    def test_reconcile_watcher_does_not_retrigger_on_existing_marker(self):
        path_unit = (
            ROOT / "components/control-plane/etc/systemd/system/cloudif-reconcile-worker.path"
        ).read_text()
        service = (
            ROOT / "components/control-plane/etc/systemd/system/cloudif-reconcile-worker.service"
        ).read_text()
        timer = (
            ROOT / "components/control-plane/etc/systemd/system/cloudif-reconcile-worker.timer"
        ).read_text()
        self.assertIn("PathChanged=/var/lib/cloudif/reconcile-queue/incoming", path_unit)
        self.assertIn("MakeDirectory=true", path_unit)
        self.assertNotIn("PathExistsGlob=", path_unit)
        self.assertIn("StartLimitIntervalSec=0", service)
        self.assertIn("OnUnitInactiveSec=30s", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main()
