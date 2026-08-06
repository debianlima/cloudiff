from pathlib import Path
import ast
import unittest

SOURCE = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text()
TREE = ast.parse(SOURCE)
FUNCTION = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == '_confirmation_matches')
MODULE = ast.Module(body=[FUNCTION], type_ignores=[])
ast.fix_missing_locations(MODULE)
NS = {}
exec(compile(MODULE, '<delete-confirmation>', 'exec'), NS)
MATCHES = NS['_confirmation_matches']


class ProjectDeleteConfirmationNormalizationTests(unittest.TestCase):
    def test_keyword_and_slug_are_case_insensitive(self):
        self.assertTrue(MATCHES('silvipro', 'EXCLUIR silvipro'))
        self.assertTrue(MATCHES('silvipro', 'excluir Silvipro'))

    def test_surrounding_and_repeated_whitespace_are_normalized(self):
        self.assertTrue(MATCHES('silvipro', '  EXCLUIR   silvipro  '))

    def test_phrase_still_requires_keyword_and_complete_slug(self):
        self.assertFalse(MATCHES('silvipro', 'silvipro'))
        self.assertFalse(MATCHES('silvipro', 'EXCLUIR silvi'))
        self.assertFalse(MATCHES('silvipro', 'REMOVER silvipro'))

    def test_invalid_confirmation_is_rejected_before_job_creation(self):
        start = SOURCE[SOURCE.index('def start_job'):SOURCE.index('def h(')]
        validation = start.index('if not _confirmation_matches(slug, confirmation)')
        job_id = start.index('job_id = uuid.uuid4().hex')
        self.assertLess(validation, job_id)
        self.assertIn("'error': 'invalid_confirmation'", start[:job_id])


if __name__ == '__main__':
    unittest.main()
