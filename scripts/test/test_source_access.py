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
            'microsoft.ai': 'https://microsoft.ai/blog/',
            'venturebeat.com': 'https://venturebeat.com/category/ai/',
            'qwen.ai': 'https://qwen.ai/research',
        }
        for domain, url in expected.items():
            with self.subTest(domain=domain):
                self.assertEqual(pipeline.URL_OVERRIDES.get(domain), url)
                self.assertTrue(validator.domain_matches(url, domain))

    def test_meta_assignment_uses_verified_current_source_owned_index(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            manifest = pipeline.prepare(Path(directory) / 'repo', Path(directory) / 'run', '2026-10-19')
        specs = {s['domain']: s for task in manifest['tasks'] if task['kind'] == 'sources' for s in task['sources']}
        self.assertEqual(specs['ai.meta.com']['url'], 'https://research.meta.ai/')
        self.assertEqual(specs['ai.meta.com']['access_policy'], 'docs/qwen-meta-source-policy.md')
        self.assertIn('https://ai.meta.com/research/', specs['ai.meta.com']['alternate_urls'])
        self.assertEqual(specs['qwen.ai']['fetch_helper'], 'scripts/qwen_source_fetch.py')
        self.assertIn('https://qwen.ai/api/v2/article/retrieval?type=qwen_ai&language=en-US',
                      specs['qwen.ai']['alternate_urls'])
        self.assertIn('https://api.github.com/repos/QwenLM/qwen-code/releases?per_page=30',
                      specs['qwen.ai']['alternate_urls'])
        self.assertEqual(len(specs), 40)
        self.assertEqual(validator.REGISTRY_VERSION, 5)

    def test_only_verified_meta_alternate_host_is_accepted_for_its_checkpoint(self):
        audit = {'schema_version': 1, 'registry_version': 5, 'date': '2026-10-19', 'sources': [
            {'domain': domain, 'name': name, 'status': 'unavailable',
             'checked_url': 'https://' + domain + '/', 'result': 'Synthetic access test'}
            for domain, name in validator.SOURCES]}
        entry = next(item for item in audit['sources'] if item['domain'] == 'ai.meta.com')
        entry['checked_url'] = 'https://research.meta.ai/'
        self.assertEqual(validator.validate(audit, audit['date']), [])
        self.assertFalse(validator.domain_matches('https://research.meta.ai/', 'ai.meta.com'),
                         'Generic domain matching must not be loosened')
        for url in ('https://unrelated.meta.ai/', 'https://research.meta.ai.evil.example/',
                    'https://sub.research.meta.ai/', 'https://user@research.meta.ai/',
                    'http://research.meta.ai/', 'https://research.meta.ai:8443/'):
            entry['checked_url'] = url
            with self.subTest(url=url):
                self.assertTrue(validator.validate(audit, audit['date']))
        entry['checked_url'] = 'https://ai.meta.com/blog/'
        qwen = next(item for item in audit['sources'] if item['domain'] == 'qwen.ai')
        qwen['checked_url'] = 'https://research.meta.ai/'
        self.assertTrue(validator.validate(audit, audit['date']))

    def test_latent_space_migration_preserves_historical_registries(self):
        self.assertIn('latent.space', dict(validator.SOURCES))
        self.assertNotIn('latentspace.com', dict(validator.SOURCES))
        self.assertEqual(validator.REGISTRY_VERSION, 5)
        for version in (1, 2, 3):
            registry = validator.SOURCE_REGISTRIES[version]
            self.assertIn('latentspace.com', dict(registry))
            self.assertNotIn('latent.space', dict(registry))
            self.assertEqual(pipeline.registry_for_manifest({'registry': list(registry)})[0], version)


if __name__ == '__main__':
    unittest.main()
