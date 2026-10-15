import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render
import history
from test_render import BRIEFING


class SearchIndexTests(unittest.TestCase):
    def test_current_history_monthly_and_legacy_archives_deduplicated_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            b = copy.deepcopy(BRIEFING)
            item = b['topics'][0]['items'][0]
            old = dict(item, topic_id='ai-news', date='2026-06-09')
            historic = dict(old, title='Archivfund', date='2026-01-01')
            (archive / 'history-2026-01.json').write_text(json.dumps({'items': [historic, old, None, {'title': []}]}))
            legacy = copy.deepcopy(b)
            legacy['topics'][0]['items'][0]['title'] = 'Legacyfund'
            (archive / '2026-06-08-briefing.json').write_text(json.dumps(legacy))
            hostile = dict(old, title='<img src=x onerror=alert(1)>', sources=[None, {'label': '<script>x</script>', 'url': 'javascript:alert(1)'}, {'label': 'Sicher', 'url': 'https://example.com/safe'}])
            rows = render.build_search_index(b, {'items': [old, hostile]}, archive)
            self.assertEqual(len(rows), 4)
            self.assertEqual({r['title'] for r in rows}, {'Meldung', 'Archivfund', 'Legacyfund', hostile['title']})
            self.assertEqual(next(r for r in rows if r['title'] == 'Meldung')['date'], '2026-06-09')
            attack = next(r for r in rows if r['title'] == hostile['title'])
            self.assertEqual(attack['sources'], [{'label': '<script>x</script>', 'url': ''}, {'label': 'Sicher', 'url': 'https://example.com/safe'}])
            self.assertEqual(attack['topic'], 'AI News')
            self.assertEqual(rows, render.build_search_index(b, {'items': [old, hostile]}, archive))


    def test_release_milestones_and_distinct_topics_are_not_collapsed(self):
        b = copy.deepcopy(BRIEFING)
        original = dict(b['topics'][0]['items'][0], topic_id='ai-news', date='2026-06-09')
        with tempfile.TemporaryDirectory() as tmp:
            pool = {'items': [dict(original, change_type='preview'),
                              dict(original, change_type='general_availability', date='2026-06-10'),
                              dict(original, topic_id='other-topic')]}
            rows = render.build_search_index({'topics': []}, pool, Path(tmp))
            self.assertEqual(len(rows), 3)

    def test_broken_archive_fails_build_instead_of_claiming_full_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            (archive / 'broken.json').write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                render.build_search_index(BRIEFING, {'items': []}, archive)


class SearchGenerationTests(unittest.TestCase):
    def test_assets_relative_navigation_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/briefing.json').write_text(json.dumps(BRIEFING))
            original = render.DATA, render.SITE, history.HISTORY
            try:
                render.DATA, render.SITE, history.HISTORY = root / 'data/briefing.json', root / 'site', root / 'data/history.json'
                render.main()
                for sub in ('', '7d', '14d', '30d'):
                    for page in ('index.html', 'ai-news.html'):
                        text = (render.SITE / sub / page).read_text()
                        self.assertIn('href="' + ('../' if sub else '') + 'search.html"', text)
                for asset in ('search.html', 'search.js', 'search-index.json'):
                    self.assertTrue((render.SITE / asset).exists())
                page = (render.SITE / 'search.html').read_text()
                self.assertIn('<label for="search-query">', page)
                self.assertIn('<noscript>', page)
                self.assertIn('aria-live="polite">Die Suche benötigt JavaScript.</p>', page)
                self.assertIn('src="search.js" defer', page)
                before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                render.main()
                self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            finally:
                render.DATA, render.SITE, history.HISTORY = original
