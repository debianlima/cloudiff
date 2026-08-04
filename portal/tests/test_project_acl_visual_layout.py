from pathlib import Path
import unittest

class ProjectAclVisualLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py').read_text()
    def test_modal_has_clear_visual_sections(self):
        for marker in ('acl-modal-meta','Permissões atuais','acl-modal-section','acl-selection-grid','acl-form-actions','Gerenciar permissões'):
            self.assertIn(marker,self.source)
    def test_duplicate_bottom_close_was_removed(self):
        self.assertNotIn('class="cm-btn cm-secondary" href="#" onclick="cloudifHideWizard',self.source)
        self.assertIn('aria-label="Fechar"',self.source)
    def test_acl_contract_is_unchanged(self):
        for marker in ('/cloudiff/portal/action/project_acl','name="op" value="add"','name="op" value="remove"','name="principal" required','name="principal_type" required','cloudifValidateAclSelection_'):
            self.assertIn(marker,self.source)
    def test_owner_protection_remains(self):
        self.assertIn('dono protegido',self.source)
        self.assertIn('is_owner_principal',self.source)

if __name__=='__main__': unittest.main()
