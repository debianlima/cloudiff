import unittest
from unittest.mock import patch

from portal.core.auth import Identity
from portal.core.legacy_shell import group_resources_by_user


class GroupedResourcesTest(unittest.TestCase):
    def setUp(self):
        self.identity = Identity("alice", "alice@example.invalid", frozenset({"CloudIF-Tenants-Admin"}))

    @patch("portal.core.legacy_shell._resource_ownership")
    def test_publications_are_grouped_and_current_user_opens(self, ownership):
        ownership.return_value = ({"site-a": "alice", "site-b": "bob"}, {})
        body = (
            '<div class="publication-shell">'
            '<article class="publication-project card"><h2>site-a</h2></article>'
            '<article class="publication-project card"><h2>site-b</h2></article>'
            '</div>'
        )
        output = group_resources_by_user(body, "publicacao", self.identity)
        self.assertIn('alice · você', output)
        self.assertIn('class="owner-resource-group" open', output)
        self.assertIn('bob', output)
        self.assertEqual(output.count('publication-project card'), 2)

    @patch("portal.core.legacy_shell._resource_ownership")
    def test_databases_without_owner_are_not_misattributed(self, ownership):
        ownership.return_value = ({}, {"alice-db": "alice"})
        body = (
            '<article class="card db96-card" id="alice-db"><article class="nested">inner</article></article>'
            '<article class="card db96-card" id="orphan-db"></article>'
        )
        output = group_resources_by_user(body, "bancos", self.identity)
        self.assertIn('data-current-user="alice"', output)
        self.assertIn('id="alice-db" data-resource-owner="alice"', output)
        self.assertIn('id="orphan-db" data-resource-owner=""', output)
        self.assertEqual(output.count('db96-card'), 2)
        self.assertIn('<article class="nested">inner</article>', output)

    def test_other_tabs_remain_untouched(self):
        body = '<article class="publication-project card">site-a</article>'
        self.assertEqual(group_resources_by_user(body, "projetos", self.identity), body)


if __name__ == "__main__":
    unittest.main()
