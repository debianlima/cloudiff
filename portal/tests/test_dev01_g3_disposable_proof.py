"""Static/CLI safety tests; NEVER connect to a Docker daemon in CI."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

SCRIPT=Path(__file__).resolve().parents[2]/'scripts/dev01-g3-disposable-docker-proof.py'


def load_module():
    spec=importlib.util.spec_from_file_location('pgh_g3_disposable_proof',SCRIPT)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class DisposableG3ProofContractTests(unittest.TestCase):
    def test_default_is_read_only_without_docker_dependency(self):
        result=subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,timeout=6)
        self.assertEqual(result.returncode,0)
        self.assertIn('"READ_ONLY"',result.stdout)
        self.assertIn('requires --execute',result.stdout)

    def test_help_does_not_require_docker(self):
        result=subprocess.run([sys.executable,str(SCRIPT),'--help'],capture_output=True,text=True,timeout=6)
        self.assertEqual(result.returncode,0)
        self.assertIn('--execute',result.stdout)

    def test_cpu_pressure_denies_before_entering_main(self):
        m=load_module()
        with mock.patch.object(m.os,'getloadavg',return_value=(12.0,8.0,6.0)),\
             mock.patch.object(m.os,'cpu_count',return_value=4),\
             mock.patch.object(m,'main') as run,\
             mock.patch.object(sys,'argv',[str(SCRIPT),'--execute']):
            with self.assertRaisesRegex(RuntimeError,'host_cpu_load_above_disposable_budget'):
                m.entrypoint()
        run.assert_not_called()

    def test_wrong_host_denies_before_any_docker_command(self):
        m=load_module()
        with mock.patch.object(m.socket,'gethostname',return_value='forja'),\
             mock.patch.object(m.os,'geteuid',return_value=1000),\
             mock.patch.object(m,'run') as execute:
            with self.assertRaisesRegex(RuntimeError,'refusing_wrong_host_or_root_identity'):
                m.main()
        execute.assert_not_called()

    def test_root_denies_before_any_docker_command(self):
        m=load_module()
        with mock.patch.object(m.socket,'gethostname',return_value='hospedagem'),\
             mock.patch.object(m.os,'geteuid',return_value=0),\
             mock.patch.object(m,'run') as execute:
            with self.assertRaisesRegex(RuntimeError,'refusing_wrong_host_or_root_identity'):
                m.main()
        execute.assert_not_called()

    def test_script_has_strict_cleanup_and_bounded_resources(self):
        source=SCRIPT.read_text()
        for marker in ('--pull=never','--cpus','--memory','--pids-limit',
                       '--internal','--network-alias','os.replace(temp_marker,marker)',
                       'shutil.rmtree(tempfile_dir,ignore_errors=True)',
                       "run('docker','rm','-f',n", "run('docker','network','rm',net"):
            with self.subTest(marker=marker):
                self.assertIn(marker,source)


if __name__=='__main__':unittest.main()
