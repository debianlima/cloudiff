from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
EXEC=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'


def load_module():
    spec=importlib.util.spec_from_file_location('snapshot_archive_retry_test',EXEC)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    spec.loader.exec_module(module)
    module.SNAPSHOT_ARCHIVE_ATTEMPTS=3
    module.SNAPSHOT_ARCHIVE_RETRY_DELAY_SECONDS=0
    return module


class SnapshotArchiveRetryTests(unittest.TestCase):
    def test_docker_cp_archive_retries_transient_failure_before_snapshot_fails(self):
        module=load_module();calls=[]
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'volume.tar'
            def fake_run(command,stdout=None,stderr=None,timeout=None,**kwargs):
                calls.append(command)
                if len(calls)==1:
                    return subprocess.CompletedProcess(command,1,stderr=b'transient docker archive failure')
                stdout.write(b'valid tar bytes')
                return subprocess.CompletedProcess(command,0,stderr=b'')
            with mock.patch.object(module.subprocess,'run',side_effect=fake_run):
                module._tar_container_path('preview-app','/data',target)
            self.assertEqual(len(calls),2);self.assertGreater(target.stat().st_size,0)

    def test_bind_archive_retries_transient_failure_before_snapshot_fails(self):
        module=load_module();calls=[]
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source';source.mkdir();(source/'file.txt').write_text('ok')
            target=Path(td)/'bind.tar'
            def fake_run(command,stdout=None,stderr=None,timeout=None,**kwargs):
                calls.append(command)
                if len(calls)==1:
                    return subprocess.CompletedProcess(command,2,stdout='',stderr='file changed')
                Path(command[command.index('-cpf')+1]).write_bytes(b'valid tar bytes')
                return subprocess.CompletedProcess(command,0,stdout='',stderr='')
            with mock.patch.object(module.subprocess,'run',side_effect=fake_run):
                module._tar_path(source,target)
            self.assertEqual(len(calls),2);self.assertGreater(target.stat().st_size,0)

    def test_archive_failure_remains_terminal_after_bounded_retries(self):
        module=load_module();module.SNAPSHOT_ARCHIVE_ATTEMPTS=2
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'volume.tar'
            failure=subprocess.CompletedProcess(['docker','cp'],1,stderr=b'persistent failure')
            with mock.patch.object(module.subprocess,'run',return_value=failure) as run:
                with self.assertRaises(module.DeploymentError) as caught:
                    module._tar_container_path('preview-app','/data',target)
            self.assertEqual(caught.exception.code,'compose_snapshot_archive_failed')
            self.assertEqual(caught.exception.detail['attempts'],2)
            self.assertEqual(run.call_count,2)


if __name__=='__main__':
    unittest.main()
