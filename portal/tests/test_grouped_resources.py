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
        self.assertIn('Meus sites', output)
        self.assertIn('class="owner-resource-group" open', output)
        self.assertIn('bob', output)
        self.assertEqual(output.count('publication-project card'), 2)

    @patch("portal.core.legacy_shell._resource_ownership")
    def test_other_sites_scope_filters_current_user_and_opens_other_groups(self, ownership):
        ownership.return_value = ({"site-a": "alice", "site-b": "bob", "site-c": "carol"}, {})
        body = (
            '<div class="publication-shell">'
            '<article class="publication-project card"><h2>site-a</h2></article>'
            '<article class="publication-project card"><h2>site-b</h2></article>'
            '<article class="publication-project card"><h2>site-c</h2></article>'
            '</div>'
        )
        output = group_resources_by_user(body, "publicacao", self.identity, resource_scope="others")
        self.assertIn('id="other-user-sites"', output)
        self.assertNotIn('<h2>site-a</h2>', output)
        self.assertIn('<h2>site-b</h2>', output)
        self.assertIn('<h2>site-c</h2>', output)
        self.assertIn('<span>bob</span>', output)
        self.assertIn('class="owner-resource-group" open', output)

    @patch("portal.core.legacy_shell._resource_ownership")
    def test_databases_without_owner_are_not_misattributed(self, ownership):
        ownership.return_value = ({}, {"alice-db": "alice"})
        body = (
            '<article class="card db96-card" data-tenant="alice-db"><article class="nested">inner</article></article>'
            '<article class="card db96-card" data-tenant="orphan-db"></article>'
        )
        output = group_resources_by_user(body, "bancos", self.identity)
        self.assertIn('data-current-user="alice"', output)
        self.assertIn('data-tenant="alice-db" data-resource-owner="alice"', output)
        self.assertIn('data-tenant="orphan-db" data-resource-owner=""', output)
        self.assertEqual(output.count('db96-card'), 2)
        self.assertIn('<article class="nested">inner</article>', output)

    @patch("portal.core.legacy_shell._resource_ownership")
    def test_full_publication_transform_applies_other_user_scope(self, ownership):
        from portal.core.legacy_shell import transform
        ownership.return_value = ({"site-a": "alice", "site-b": "bob"}, {})
        markup = (
            '<html><head><title>Publicações</title></head><body>'
            '<main id="conteudo-principal">'
            '<section class="publication-shell">'
            '<article class="publication-project card"><h2>site-a</h2></article>'
            '<article class="publication-project card"><h2>site-b</h2></article>'
            '</section></main></body></html>'
        )
        output = transform(markup, self.identity, "publicacao", resource_scope="others")
        self.assertIn('id="other-user-sites"', output)
        self.assertIn('<h2>site-b</h2>', output)
        self.assertNotIn('<h2>site-a</h2>', output)
        self.assertIn('data-legacy-tab="publicacao"', output)

    def test_other_tabs_remain_untouched(self):
        body = '<article class="publication-project card">site-a</article>'
        self.assertEqual(group_resources_by_user(body, "projetos", self.identity), body)


if __name__ == "__main__":
    unittest.main()

class IndividualPublicationTest(unittest.TestCase):
    def test_selected_project_keeps_only_matching_card(self):
        from portal.core.legacy_shell import filter_publication_project
        body = (
            '<p>before</p>'
            '<article class="publication-project card"><input name="slug" value="alpha"></article>'
            '<article class="publication-project card"><input name="slug" value="beta"></article>'
            '<p>after</p>'
        )
        output = filter_publication_project(body, "beta")
        self.assertNotIn('value="alpha"', output)
        self.assertIn('value="beta"', output)
        self.assertIn('<p>before</p>', output)
        self.assertIn('<p>after</p>', output)


class IndividualPublicationPresentationTest(unittest.TestCase):
    def test_individual_manager_returns_only_selected_card(self):
        from portal.core.legacy_shell import individual_publication_body
        body = (
            '<section class="publication-shell">'
            '<div class="page-hero"><span>Meus Projetos</span><h1>Publicação</h1></div>'
            '<div class="publication-summary card"><strong>Fila</strong><span>Em execução</span></div>'
            '<article class="publication-project card"><input name="slug" value="alpha"><h2>Alpha</h2></article>'
            '<article class="publication-project card"><input name="slug" value="beta"><h2>Beta</h2></article>'
            '</section>'
        )
        output = individual_publication_body(body, "beta")
        self.assertIn('value="beta"', output)
        self.assertNotIn('value="alpha"', output)
        self.assertNotIn('Meus Projetos', output)
        self.assertNotIn('publication-summary', output)
        self.assertNotIn('owner-resource-group', output)
        self.assertNotIn('Em execução', output)
        self.assertIn('class="publication-single"', output)
