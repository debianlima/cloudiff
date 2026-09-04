import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CSS=(ROOT/'portal/design/components.css').read_text()

class CodeDarkBadgesTests(unittest.TestCase):
    def test_code_identifiers_use_dark_surface_tokens(self):
        self.assertIn('html[data-theme="dark"] .tab-git .legacy-content code{',CSS)
        self.assertIn('background:var(--iff-wash)!important;',CSS)
        self.assertIn('color:var(--iff-dark)!important;',CSS)

    def test_positive_status_badges_use_green_dark_tokens(self):
        self.assertIn(':is(.ci-pill-ok,.pill.ok,.badge.ok)',CSS)
        self.assertIn('background:var(--iff-wash)!important;',CSS)
        self.assertIn('color:var(--iff-dark)!important;',CSS)

    def test_neutral_status_badges_do_not_use_legacy_white(self):
        self.assertIn(':is(.ci-pill-off,.ci-pill:not(.ci-pill-ok),.pill:not(.ok),.badge:not(.ok))',CSS)
        self.assertIn('background:var(--surface)!important;',CSS)

if __name__=='__main__':unittest.main()
