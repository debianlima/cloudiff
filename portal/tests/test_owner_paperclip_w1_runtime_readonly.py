import importlib.util
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("mod",Path(__file__).resolve().parents[1] / "tools" / "owner_paperclip_w1_runtime_readonly.py")
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(TestCase):
    def test_untrusted_command(self):
        self.assertIsNone(m.cmd(["curl","https://x"]))
        self.assertIsNone(m.cmd(["docker","rm",m.TARGET]))
        self.assertIsNone(m.cmd(["docker","inspect","--format","{{json .Config.Env}}",m.TARGET]))
        self.assertIsNone(m.cmd(["docker","exec",m.TARGET,"cat","/run/secrets"]))
    def test_unprivileged_block(self):
        with patch.object(m.socket,"gethostname",return_value="forja"),patch.object(m.os,"geteuid",return_value=1000):
            self.assertEqual(m.report()["status"],"BLOCKED_REQUIRES_AUTHORIZED_ROOT")
    def test_wrong_host_block(self):
        with patch.object(m.socket,"gethostname",return_value="pghd-server"),patch.object(m.os,"geteuid",return_value=0):
            self.assertEqual(m.report()["status"],"BLOCKED_WRONG_HOST")
    def test_no_raw_env_in_specs(self):
        for template in ["{{json .Config.Env}}","{{json .Mounts}}","{{json .Config}}"]:
            self.assertIsNone(m.cmd(["docker","inspect","--format",template,m.TARGET]))
    def test_file_scope(self):
        self.assertTrue(all(x.startswith("/var/www/html/") for x in m.FILES.values()))
    def test_invalid_mount_sanitized(self):
        self.assertFalse(m.SAFE_MOUNT.fullmatch("/tmp/a:password=foobar"))
    def test_bad_immutable_source_label_is_false(self):
        with patch.object(m.socket,"gethostname",return_value="forja"),patch.object(m.os,"geteuid",return_value=0):
            def fake(argv):
                if argv[1]=="exec":return False
                t=argv[3]
                if t=="{{.State.Status}}":return "running"
                if t=="{{.Config.Image}}":return "sha256:"+"a"*64
                if "Mounts" in t:return ""
                if "org.cloudiff.project" in t:return "paperclip"
                if "org.cloudiff.public-number" in t:return "1025"
                if "org.cloudiff.stage-number" in t:return "1"
                if "org.cloudiff.stage" in t:return "preview"
                if "org.cloudiff.source-preview-bridge" in t:return "true"
                if "org.cloudiff.source-commit" in t:return "main"
            with patch.object(m,"cmd",side_effect=fake):
                result=m.report()
        self.assertEqual(result["status"],"METADATA_ONLY_NOT_A_RUNTIME_FIX")
        self.assertFalse(result["immutable_source_commit_labeled"])

    def test_unavailable_docker_fails_closed(self):
        with patch.object(m.socket,"gethostname",return_value="forja"),patch.object(m.os,"geteuid",return_value=0),patch.object(m,"cmd",return_value=None):
            self.assertEqual(m.report()["status"],"BLOCKED_DOCKER_INSPECT")
    def test_expected_fields_present(self):
        with patch.object(m.socket,"gethostname",return_value="forja"),patch.object(m.os,"geteuid",return_value=0):
            def fake(argv):
                template=argv[3] if argv[1]=="inspect" else ""
                if argv[1]=="exec":return False
                if template=="{{.State.Status}}":return "running"
                if template=="{{.Config.Image}}":return "cloudif/runtime-apache-php8.3-node22:v2"
                if "Mounts" in template:return "/etc/komodo/stacks/cloudif-paperclip"
                if "org.cloudiff.project" in template:return "paperclip"
                if "org.cloudiff.stage-number" in template:return "1"
                if "org.cloudiff.stage" in template:return "preview"
                if "org.cloudiff.public-number" in template:return "1025"
                if "org.cloudiff.source-preview-bridge" in template:return "true"
                if "org.cloudiff.source-commit" in template:return "a"*40
            with patch.object(m,"cmd",side_effect=fake):
                r=m.report()
        self.assertEqual(r["status"],"METADATA_ONLY_NOT_A_RUNTIME_FIX")
        self.assertFalse(r["files_exist"]["root_index_html"])
        self.assertTrue(r["mount_looks_like_paperclip_checkout"])
        self.assertNotIn("env",r)
        self.assertTrue(r["public_number_expected"])
        self.assertTrue(r["preview_bridge_marker_expected"])
        self.assertTrue(r["immutable_source_commit_labeled"])
if __name__=="__main__":main()
