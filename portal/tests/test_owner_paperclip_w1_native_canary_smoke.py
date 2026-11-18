#!/usr/bin/env python3
import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch,Mock

P=Path(__file__).resolve().parents[1] / "tools" / "owner_paperclip_w1_native_canary_smoke.py"
sp=importlib.util.spec_from_file_location("canary",P)
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)

class CanaryTests(TestCase):
    def test_target_is_mauricio_only(self):
        with patch.object(m.socket,"gethostname",return_value="forja"):
            with patch.object(m.os,"geteuid",return_value=0):
                with self.assertRaisesRegex(ValueError,"MAURICIO_ROOT_REQUIRED"):
                    m.check_host()
    def test_unprivileged_blocked(self):
        with patch.object(m.socket,"gethostname",return_value="mauricio"):
            with patch.object(m.os,"geteuid",return_value=1000):
                with self.assertRaisesRegex(ValueError,"MAURICIO_ROOT_REQUIRED"):
                    m.check_host()
    def test_exact_nonproduction_targets(self):
        self.assertTrue(m.CONTAINER.startswith("cloudif-paperclip-1025-native-smoke-"))
        self.assertTrue(m.VOLUME.startswith("cloudif-paperclip-1025-native-smoke-data-"))
        self.assertNotIn("cloudif-p1025-w1-preview-web",(m.CONTAINER,m.VOLUME))
        self.assertTrue(m.IMAGE.endswith(":dfcaaf831438"))
    def test_path_check_rejects_traversal(self):
        for path in ("http://example.org/","/../secret","//other","relative"):
            with self.subTest(path=path),self.assertRaises(ValueError):
                m.get_http(path)
    def test_image_missing_fails_closed_before_mutation(self):
        with patch.object(m,"check_host"):
            with patch.object(m,"inspect_image",return_value=""):
                with patch.object(m,"already_exists",side_effect=AssertionError("unexpected")):
                    with self.assertRaisesRegex(ValueError,"VERIFIED_NATIVE_IMAGE"):
                        m.smoke()
    def test_resource_collision_blocks_before_volume_create(self):
        with patch.object(m,"check_host"):
            with patch.object(m,"inspect_image",return_value="sha256:"+"a"*64):
                with patch.object(m,"already_exists",return_value=True):
                    with patch.object(m,"run",side_effect=AssertionError("no docker mut")):
                        with self.assertRaisesRegex(ValueError,"RESOURCE_COLLISION"):
                            m.smoke()
    def test_inspect_image_is_metadata_only(self):
        with patch.object(m,"run",return_value=Mock(returncode=0,stdout="sha256:"+"a"*64)):
            self.assertEqual(m.inspect_image(),"sha256:"+"a"*64)
    def test_script_has_no_public_or_private_mounts(self):
        s=P.read_text()
        for bad in ("--publish","--privileged","--network=host",
                    "10.62.91.2:3100","docker.sock","chmod 777"):
            self.assertNotIn(bad,s)
        self.assertIn('"--network","none"',s)
        self.assertIn('"--security-opt","no-new-privileges:true"',s)
        self.assertIn('"--memory","4g"',s)
if __name__=="__main__":main()
