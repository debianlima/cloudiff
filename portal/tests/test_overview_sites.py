import unittest
from portal.modules.overview.views import _site_card


class OverviewSiteCardTest(unittest.TestCase):
    def test_published_site_keeps_new_tab_and_individual_manage_link(self):
        markup = _site_card({
            "project_slug": "library-test", "name": "Library", "stable_hostname": "library.example",
            "published": True,
        })
        self.assertIn('target="_blank"', markup)
        self.assertIn('tab=publicacao&project=library-test', markup)
        self.assertIn('Publicado', markup)

    def test_unpublished_site_has_manage_action_without_public_link(self):
        markup = _site_card({
            "project_slug": "draft-site", "name": "Draft", "stable_hostname": None,
            "published": False,
        })
        self.assertIn('Ainda não publicado', markup)
        self.assertIn('tab=publicacao&project=draft-site', markup)
        self.assertNotIn('target="_blank"', markup)


if __name__ == "__main__":
    unittest.main()
