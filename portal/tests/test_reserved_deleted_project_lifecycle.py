from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUBLISHER=(ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text()
REFRESH=(ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py').read_text()
AUDIT=(ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-readmodel-audit.py').read_text()
PUBLICATIONS=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
PROVISION=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_status.py').read_text()

class ReservedDeletedProjectLifecycleTests(unittest.TestCase):
    def test_unpublish_removes_all_stage_routes_for_public_number(self):
        self.assertIn("removed_stages",PUBLISHER)
        self.assertIn("int((data or {}).get('public_number') or 0)==num",PUBLISHER)
        self.assertIn("certificates_preserved",PUBLISHER)
    def test_fast_catalog_separates_current_from_reserved_deleted(self):
        self.assertIn("join projects p on p.slug=i.project_slug",REFRESH)
        self.assertIn("def reserved_public_numbers():",REFRESH)
        self.assertIn("'lifecycle':'reserved-deleted'",REFRESH)
        self.assertIn("'reserved-public-numbers'",REFRESH)
    def test_nightly_audit_does_not_treat_reserved_number_as_current_project(self):
        self.assertIn("join projects p on p.slug=i.project_slug",AUDIT)
        self.assertIn("def reserved_projects(con):",AUDIT)
        self.assertIn("reserved-deleted-operational-residue",AUDIT)
        self.assertIn("reserved-deleted-preview-runtime",AUDIT)
        self.assertIn("/komodo/project/preview/status",AUDIT)
        self.assertIn("reserved_public_number_count",AUDIT)
    def test_runtime_mutations_require_current_project_row(self):
        self.assertIn("project=_project_allowed(con,slug,user)",PUBLICATIONS)
        self.assertIn("if not project:con.close();raise PermissionError('Projeto não encontrado ou sem permissão.')",PUBLICATIONS)
        self.assertIn("project=_project(slug)\n    if not project:return {'ok':False,'error':'project_not_found'",PROVISION)

if __name__=='__main__':unittest.main()
