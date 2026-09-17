from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT/'components/control-plane/current-apps/audit-current/cloudif-academic-audit-api.py'
EVAL = ROOT/'components/control-plane/current-apps/evaluations-current/cloudif-evaluation-api.py'
ACL = ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py'
PORTAL = ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'


class AcademicAuditStudentScopeTests(unittest.TestCase):
    def test_audit_supports_subject_filter_and_redacts_sensitive_attrs(self):
        src=AUDIT.read_text(); ast.parse(src)
        self.assertIn("q.get('subject')", src)
        self.assertIn('lower(actor_id)=lower(?) or lower(delegated_user_id)=lower(?)', src)
        self.assertIn('SENSITIVE_ATTR', src)
        self.assertIn('authorization', src.lower())

    def test_evaluation_requests_student_scoped_evidence(self):
        src=EVAL.read_text(); ast.parse(src)
        self.assertIn("'subject':student", src)
        self.assertIn('audit_events(slug,student)', src)

    def test_acl_sync_failure_no_longer_prevents_durable_enqueue(self):
        acl=ACL.read_text(); portal=PORTAL.read_text()
        self.assertNotIn("raise RuntimeError('Permissão salva, mas a sincronização com o Komodo falhou", acl)
        self.assertIn('sincronização imediata com o Komodo pendente', acl)
        self.assertIn('"project.membership.changed"', portal)
        self.assertLess(portal.index('project_acl.handle_project_acl_action'), portal.index('"project.membership.changed"'))


if __name__ == '__main__':
    unittest.main()
