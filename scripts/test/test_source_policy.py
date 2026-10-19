import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as p
import validate_research_audit as v


class SourcePolicyTests(unittest.TestCase):
    def test_historical_registry_fingerprints_are_frozen(self):
        import hashlib
        expected = {1: 'a14a6315e4960cd6040f99bd0363cf920f21437a28b450c2c2992f47c74d4b46',
                    2: 'e9b020de7c73550a4679e794edb101c3588bbaa23274dbe65cc81508b10d2da7',
                    3: '3b1e477f0f8ff36ddea0f2753167f3b99fc5c6c45c66606a8b01be21c16f784c',
                    4: '5f48dcffa93c9347c20ccd1bdc457b171086e5fa1af7eddffae430cc90fa0419'}
        for version, digest in expected.items():
            self.assertEqual(hashlib.sha256(json.dumps(v.SOURCE_REGISTRIES[version], ensure_ascii=False).encode()).hexdigest(), digest)

    def test_v5_removes_only_semianalysis_and_preserves_old_registries(self):
        self.assertEqual(v.REGISTRY_VERSION, 5)
        self.assertEqual(len(v.SOURCES), 40)
        self.assertEqual(set(v.SOURCE_REGISTRIES[4]) - set(v.SOURCES),
                         {('semianalysis.com', 'SemiAnalysis')})
        for version, count in ((1, 42), (2, 41), (3, 41), (4, 41)):
            self.assertEqual(len(v.SOURCE_REGISTRIES[version]), count)
            self.assertIn('semianalysis.com', dict(v.SOURCE_REGISTRIES[version]))
            self.assertEqual(p.registry_for_manifest({'registry': v.SOURCE_REGISTRIES[version]})[0], version)
        self.assertTrue({'qwen.ai', 'ai.meta.com', 'chinatalk.media', 'heise.de', 'latent.space', 'venturebeat.com'} <= dict(v.SOURCES).keys())

    def test_checked_arxiv_requires_honest_counted_discovery_only_prospectively(self):
        entry = {'domain': 'arxiv.org', 'status': 'checked', 'checked_url': 'https://arxiv.org/list/cs.AI/recent', 'result': 'Titles reviewed; not all fulltexts.'}
        def errors(version):
            return [e for e in v.validate({'schema_version': 1, 'registry_version': version,
                    'date': '2026-10-20', 'sources': [entry]}, '2026-10-20') if not e.startswith('fehlende Quellen:')]
        self.assertEqual(errors(4), [])
        self.assertTrue(any('title_discovery' in e for e in errors(5)))
        entry['title_discovery'] = [
            {'listing_kind': kind, 'source_url': ('https://export.arxiv.org/api/query' if kind == 'updates' else 'https://arxiv.org/list/cs.AI/' + suffix),
             'declared_total': 174, 'collected_count': 50, 'complete': False,
             'window_complete': False, 'limitations': ['Only first page retrieved'],
             'pages': [{'url': ('https://export.arxiv.org/api/query' if kind == 'updates' else 'https://arxiv.org/list/cs.AI/' + suffix) + '?skip=0&show=50', 'skip': 0}],
             'next_skip': 50} for kind, suffix in [('recent', 'recent'), ('changes', 'new'), ('updates', 'updates')]]
        self.assertEqual(errors(5), [])  # A documented source gap does not kill the entire audit.
        entry['title_discovery'][0]['complete'] = True
        self.assertTrue(errors(5))
        entry['status'] = 'unavailable'
        del entry['title_discovery']
        self.assertEqual(errors(5), [])

    def test_invalid_registry_and_malformed_coverage_return_validation_errors(self):
        from source_policy_fixtures import title_discovery_fixture
        from arxiv_discovery import validate_title_discovery
        self.assertTrue(v.validate({'schema_version': 1, 'registry_version': '5', 'date': '2026-10-19',
                                    'sources': [{'domain': 'arxiv.org', 'status': 'checked',
                                                 'checked_url': 'https://arxiv.org/', 'result': 'Checked'}]}, '2026-10-19'))
        reports = title_discovery_fixture()
        reports[0]['pages'] = None
        self.assertTrue(validate_title_discovery(reports))

    def test_partial_listing_does_not_advance_source_watermark(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / 'data/research-audit/2026-10-19.json'
            p.write(audit, {'date': '2026-10-19', 'sources': [{'domain': 'arxiv.org', 'status': 'checked',
                    'title_discovery': [{'complete': False, 'window_complete': False}]}]})
            from datetime import date
            self.assertEqual(p.source_windows(root, date(2026, 10, 20), [('arxiv.org', 'arXiv')])['arxiv.org'], '2026-10-13')

    def test_semianalysis_topic_requires_actual_free_original_not_optional_paywall_url(self):
        candidate = {'title': 'Datacenter expansion', 'summary': 'A supported development.',
                     'published_at': '2026-10-19', 'url': 'https://newsletter.semianalysis.com/p/example',
                     'development': 'Expansion announced', 'headline_terms': ['Datacenter'], 'change_type': 'announcement',
                     'evidence': [{'url': 'https://newsletter.semianalysis.com/p/example',
                                   'excerpt': 'An optional feed teaser is not free corroboration.',
                                   'method': 'feed', 'retrieved_at': '2026-10-19T08:00:00Z'}]}
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / 'run'
            p.prepare(temp, run, '2026-10-19')
            entry = {'topics_checked': list(p.TOPICS), 'result': 'Optional topic discovered.', 'candidates': [candidate]}
            with self.assertRaisesRegex(ValueError, 'SemiAnalysis'):
                p.record(run, 'discovery', entry)
            candidate['url'] = 'https://example.org/original-announcement'
            candidate['evidence'].append({'url': candidate['url'], 'excerpt': 'An actually retrieved freely readable original announcement.',
                                          'method': 'direct', 'retrieved_at': '2026-10-19T08:00:00Z'})
            self.assertEqual(p.record(run, 'discovery', entry)['candidates'], 1)

    def test_optional_source_is_assigned_only_to_discovery_with_unchanged_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = p.prepare(temp, Path(temp) / 'run', '2026-10-20')
            assigned = [s for t in manifest['tasks'] for s in t.get('sources', [])]
            self.assertEqual(len(assigned), 40)
            self.assertNotIn('semianalysis.com', [s['domain'] for s in assigned])
            discovery = next(t for t in manifest['tasks'] if t['kind'] == 'discovery')
            self.assertEqual(discovery['optional_sources'], [{'domain': 'semianalysis.com', 'name': 'SemiAnalysis', 'url': 'https://newsletter.semianalysis.com/feed'}])
            self.assertEqual(manifest['search_budget_per_task'], 35)
            p.record(Path(temp) / 'run', 'discovery', {'topics_checked': list(p.TOPICS), 'result': 'Optional SemiAnalysis feed failed; all eight topics searched.', 'candidates': []})
            self.assertEqual(p.missing(Path(temp) / 'run', discovery), [])
