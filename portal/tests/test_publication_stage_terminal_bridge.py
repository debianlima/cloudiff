from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PORTAL=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class PublicationStageTerminalBridgeTests(unittest.TestCase):
    def test_newest_homologation_candidate_wins_in_backend_and_ui(self):
        block=PORTAL[PORTAL.index("if environment=='homologation':",PORTAL.index('def stage_terminal')):PORTAL.index("    else:\n        release=",PORTAL.index('def stage_terminal'))]
        self.assertIn("order by candidate_number desc limit 1",block)
        self.assertNotIn("case when status in ('homologated','published')",block)
        ui=BASE[BASE.index("if(environment==='homologation')"):BASE.index("   const active=",BASE.index("if(environment==='homologation')"))]
        self.assertIn("candidate_number",ui)
        self.assertIn(".sort((a,b)=>Number(b.candidate_number||0)-Number(a.candidate_number||0))",ui)

    def test_linked_preview_is_not_blocked_before_runtime_validation(self):
        block=PORTAL[PORTAL.index('def preview_terminal('):PORTAL.index('def stage_terminal(',PORTAL.index('def preview_terminal('))]
        self.assertIn("/komodo/project/preview/terminal",block)
        self.assertNotIn('O terminal deste Preview usa o stack Forgejo/Komodo',block)
        self.assertNotIn('_linked_compose_binding',block)

    def test_runtime_has_strict_bridge_identity_fallback(self):
        helper=RUNTIME[RUNTIME.index('def _cloudif_bridge_stage_ready'):RUNTIME.index('def _cloudif_preview_create',RUNTIME.index('def _cloudif_bridge_stage_ready'))]
        for marker in (
            "'org.cloudiff.project'",
            "'org.cloudiff.public-number'",
            "'org.cloudiff.stage'",
            "'org.cloudiff.stage-number'",
            "org.cloudiff.source-preview-bridge",
            "org.cloudiff.publication-bridge",
            "cloudif-publications",
            "active_alias_missing",
        ):
            self.assertIn(marker,helper)
        self.assertIn("if health and health!='healthy'",helper)
        self.assertIn("if not state.get('Running')",helper)

    def test_runtime_uses_bridge_only_when_classic_state_is_missing(self):
        block=RUNTIME[RUNTIME.index('def cloudif_stage_terminal'):RUNTIME.index('def cloudif_preview_snapshot',RUNTIME.index('def cloudif_stage_terminal'))]
        self.assertIn("if rows:",block)
        self.assertIn("_cloudif_bridge_stage_ready(container,project,num,'homologation',candidate)",block)
        self.assertIn("_cloudif_bridge_stage_ready(container,project,num,'publication',publication,True)",block)
        self.assertIn("if not bridge_ready and not _cloudif_wait_health",block)

    def test_preview_runtime_can_accept_strict_preview_bridge_without_healthcheck(self):
        block=RUNTIME[RUNTIME.index('def cloudif_preview_terminal'):RUNTIME.index('def cloudif_stage_terminal',RUNTIME.index('def cloudif_preview_terminal'))]
        self.assertIn("_cloudif_bridge_stage_ready(container,project,num,'preview',generation)",block)
        self.assertIn("if not health.get('ok') and not bridge.get('ok')",block)

if __name__=='__main__': unittest.main()
