from pathlib import Path
import unittest


class InitialPublicationVersionedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(
            'components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py'
        ).read_text()

    def test_initial_publication_calls_versioned_deploy(self):
        for marker in (
            '/komodo/publication/deploy',
            'next_recorded_deploy_number(slug)',
            "'deploy_number': deploy_number",
            "CLOUDIF_INITIAL_DEPLOY_REQUEST_TIMEOUT",
            'versioned_deploy_not_ready',
            'immutable_deploy_conflict',
        ):
            self.assertIn(marker, self.source)

    def test_health_is_checked_after_promotion(self):
        promotion = self.source.index('promotion = promote_initial_runtime(')
        version_health = self.source.index(
            "wait_public(publisher['version_url'], timeout=public_timeout)"
        )
        stable_health = self.source.index(
            "wait_public(publisher['stable_url'], timeout=public_timeout)"
        )
        self.assertLess(promotion, version_health)
        self.assertLess(version_health, stable_health)

    def test_full_deploy_error_is_preserved(self):
        self.assertIn("'response': last", self.source)
        self.assertIn("'http': last_status", self.source)
        self.assertIn("'expected_container': expected", self.source)
        self.assertIn("'deploy_number': deploy_number", self.source)


if __name__ == '__main__':
    unittest.main()
