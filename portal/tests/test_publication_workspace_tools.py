from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PORTAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
PUB_UI=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py'
DESIGN=ROOT/'portal/design/components.css'


class PublicationWorkspaceToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal=PORTAL.read_text()
        cls.pub=PUB_UI.read_text()
        cls.design=DESIGN.read_text()

    def test_runtime_cards_progressively_open_the_workspace(self):
        for kind in ('php','node'):
            self.assertIn(f'data-publication-tool="{kind}"',self.pub)
            self.assertIn(f'&amp;kind={kind}',self.pub)
        self.assertIn('target="_blank" rel="noopener"',self.pub)
        self.assertIn('event.preventDefault();publicationEnvironmentOpen(button)',self.portal)

    def test_workspace_keeps_environment_and_tool_navigation_together(self):
        self.assertIn('publication-workspace-tools',self.portal)
        for environment in ('preview','homologation','production'):
            self.assertIn(f'data-publication-env-tab="{environment}"',self.portal)
        for tool in ('overview','php','node','variables'):
            self.assertIn(f'data-publication-tool="{tool}"',self.portal)
        self.assertIn("tool:'overview'",self.portal)
        self.assertIn('function publicationEnvironmentToolSelect(name)',self.portal)

    def test_runtime_preview_uses_authenticated_json_without_iframe(self):
        workspace=self.portal[self.portal.index("const publicationTools="):self.portal.index("const backdrop=document.createElement('div');")]
        runtime=workspace[workspace.index('async function publicationRuntimeLoad'):workspace.index('function publicationTerminalRender')]
        self.assertIn('/cloudiff/portal/api/project-runtime-info?slug=',runtime)
        self.assertIn('publication-runtime-preview',runtime)
        self.assertIn("envEsc(data.output||'')",runtime)
        self.assertNotIn('<iframe',runtime)
        self.assertNotIn('innerHTML=data.output',runtime)
        self.assertIn('<iframe',workspace)  # Site is the only intentionally framed tool.

    def test_variables_are_previewed_without_exposing_secrets(self):
        workspace=self.portal[self.portal.index("const publicationTools="):self.portal.index("const backdrop=document.createElement('div');")]
        self.assertIn('includePublicValues=true',workspace)
        self.assertIn("item.secret?'••••••••'",workspace)
        self.assertIn("item.secret?'Secret protegido':'Valor público'",workspace)
        self.assertIn('data-env-wizard',workspace)
        self.assertNotIn("if(event.target.closest('[data-env-wizard]'))publicationEnvironmentClose()",workspace)

    def test_async_workspace_requests_ignore_stale_project_results(self):
        self.assertIn('loadRequest:0',self.portal)
        self.assertIn('requestId!==publicationEnvironmentModel.loadRequest||slug!==publicationEnvironmentModel.slug',self.portal)
        self.assertIn('requestId!==publicationEnvironmentModel.toolRequest',self.portal)

    def test_workspace_is_large_but_visually_minimal(self):
        self.assertIn('width:min(1180px,100%);height:min(94vh,900px)',self.design)
        self.assertIn('grid-template-rows:auto auto auto minmax(0,1fr) auto',self.design)
        self.assertIn('.publication-workspace-tools{display:flex',self.design)
        self.assertIn('.publication-runtime-preview pre{',self.design)
        self.assertIn('.publication-variable-row{display:grid',self.design)


if __name__=='__main__':
    unittest.main()
