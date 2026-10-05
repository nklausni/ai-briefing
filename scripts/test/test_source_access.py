import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as pipeline
import validate_research_audit as validator


class SourceAccessTests(unittest.TestCase):
    def test_checked_entry_points_are_used(self):
        expected = {
            'latent.space': 'https://www.latent.space/feed',
            'semianalysis.com': 'https://newsletter.semianalysis.com/feed',
            'marktechpost.com': 'https://www.marktechpost.com/feed/',
            'microsoft.ai': 'https://microsoft.ai/?post_type=new',
            'venturebeat.com': 'https://venturebeat.com/category/ai/',
            'qwen.ai': 'https://qwen.ai/research',
        }
        for domain, url in expected.items():
            with self.subTest(domain=domain):
                self.assertEqual(pipeline.URL_OVERRIDES.get(domain), url)
                self.assertTrue(validator.domain_matches(url, domain))

    def test_latent_space_migration_preserves_historical_registries(self):
        self.assertIn('latent.space', dict(validator.SOURCES))
        self.assertNotIn('latentspace.com', dict(validator.SOURCES))
        self.assertEqual(validator.REGISTRY_VERSION, 4)
        for version in (1, 2, 3):
            registry = validator.SOURCE_REGISTRIES[version]
            self.assertIn('latentspace.com', dict(registry))
            self.assertNotIn('latent.space', dict(registry))
            self.assertEqual(pipeline.registry_for_manifest({'registry': list(registry)})[0], version)


if __name__ == '__main__':
    unittest.main()
