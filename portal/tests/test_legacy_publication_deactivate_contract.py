from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
KOMODO=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
PORTAL=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'

class LegacyPublicationDeactivateContractTests(unittest.TestCase):
    def test_portal_route_has_matching_komodo_handler(self):
        portal=PORTAL.read_text();source=KOMODO.read_text()
        self.assertIn("ku+'/komodo/publication/deactivate-legacy'",portal)
        self.assertIn('def cloudif_publication_deactivate_legacy(handler):',source)
        self.assertIn('"/komodo/publication/deactivate-legacy"',source)

    def test_deactivation_is_fail_closed_on_active_alias(self):
        source=KOMODO.read_text()
        start=source.index('def cloudif_publication_deactivate_legacy(handler):')
        end=source.index('def cloudif_publication_release_delete(handler):',start)
        block=source[start:end]
        self.assertIn("if active in aliases:return send(handler,409,{'ok':False,'error':'legacy_production_still_routed'})",block)
        self.assertIn("['docker','stop','--time','20',target]",block)
        self.assertNotIn("['docker','rm'",block)
        self.assertIn("'resourcesPreserved':True",block)
        self.assertIn("'containersRemoved':0",block)
        self.assertIn("'volumesRemoved':0",block)

    def test_deactivation_is_idempotent_and_preserves_rollback_record(self):
        source=KOMODO.read_text()
        start=source.index('def cloudif_publication_deactivate_legacy(handler):')
        end=source.index('def cloudif_publication_release_delete(handler):',start)
        block=source[start:end]
        self.assertIn("stage_production_releases set is_active=0",block)
        self.assertIn("publication_runtimes set is_active=0",block)
        self.assertNotIn("stage_production_releases set status='deleted'",block)

if __name__=='__main__':unittest.main()
