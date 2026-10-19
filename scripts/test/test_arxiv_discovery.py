import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def listing(total, start, count, day='Mon, 19 Oct 2026'):
    return (f'<html><div>Total of {total} entries</div><dl id="articles">'
            f'<h3>{day} (showing {count} of {total} entries)</h3>' + ''.join(
                f'<dt><a href="/abs/2610.{i:05}">arXiv:2610.{i:05}</a></dt>'
                f'<dd><div class="list-title mathjax"><span>Title:</span> Paper {i} &amp; safety</div></dd>'
                for i in range(start, start + count)) + '</dl></html>')


class ArxivFreshnessTests(unittest.TestCase):
    def dates(self, **changes):
        return {'submitted_at': '2026-10-16T17:57:55Z', 'listed_on': '2026-10-19',
                'listing_url': 'https://arxiv.org/list/cs.AI/recent?skip=0&show=2000',
                'announce_type': 'new', 'announcement_url': 'https://arxiv.org/list/cs.AI/new',
                'version': 1, **changes}

    def test_friday_submission_monday_public_listing_is_fresh_without_relabeling(self):
        import arxiv_discovery as a
        dates = self.dates()
        self.assertEqual(a.freshness_date(dates, '2026-10-16'), '2026-10-19')
        self.assertEqual(dates['submitted_at'], '2026-10-16T17:57:55Z')


    def test_candidate_window_uses_public_listing_but_retains_submission_date(self):
        import research_pipeline as p
        import editor_context as context
        c = {'title': 'Paper', 'summary': 'A verified research finding.',
             'url': 'https://arxiv.org/abs/2610.23845', 'published_at': '2026-10-16',
             'arxiv_dates': self.dates(), 'evidence': [
                 {'url': url, 'excerpt': 'Actual retrieved source metadata and original evidence.',
                  'method': 'direct', 'retrieved_at': '2026-10-19T08:00:00Z'} for url in
                 ('https://arxiv.org/abs/2610.23845', self.dates()['listing_url'], self.dates()['announcement_url'])]}
        saved = p.validate_candidates([c], '2026-10-19', '2026-10-17', arxiv_policy=True)[0]
        self.assertEqual(saved['published_at'], '2026-10-16')
        self.assertEqual(context.candidate_view(saved)['freshness_date'], '2026-10-19')
        with self.assertRaisesRegex(ValueError, 'outside research window'):
            p.validate_candidates([c], '2026-10-20', '2026-10-20', arxiv_policy=True)
        with self.assertRaisesRegex(ValueError, 'arxiv_dates'):
            p.validate_candidates([{k: v for k, v in c.items() if k != 'arxiv_dates'}], '2026-10-19', '2026-10-17', arxiv_policy=True)
        # No retroactive new requirement on historical manifests.
        old = {**c, 'published_at': '2026-10-18'}
        del old['arxiv_dates']
        self.assertEqual(len(p.validate_candidates([old], '2026-10-19', '2026-10-17')), 1)

    def test_arxiv_public_release_survives_record_assemble_and_editor_check(self):
        import research_pipeline as p
        from source_policy_fixtures import title_discovery_fixture
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root, run = Path(temp) / 'repo', Path(temp) / 'run'
            briefing = {'meta': {'generated': '2026-10-18'}, 'topics': [{'id': str(i), 'items': []} for i in range(8)]}
            p.write(root / 'data/briefing.json', briefing)
            manifest = p.prepare(root, run, '2026-10-19')
            dates = self.dates()
            candidate = {'title': 'Example research release', 'summary': 'Submitted 16 October; publicly listed 19 October.',
                         'development': 'Example research is publicly released.', 'headline_terms': ['Example research'],
                         'change_type': 'research', 'url': 'https://arxiv.org/abs/2610.23845',
                         'published_at': '2026-10-16', 'arxiv_dates': dates,
                         'evidence': [{'url': url, 'excerpt': 'Synthetic test source evidence supporting the example research release.',
                                       'method': 'direct', 'retrieved_at': '2026-10-19T08:00:00Z'}
                                      for url in ('https://arxiv.org/abs/2610.23845', dates['listing_url'], dates['announcement_url'])]}
            for task in manifest['tasks']:
                for source in task.get('sources', []):
                    if source['domain'] == 'arxiv.org':
                        source['since'] = '2026-10-17'
            p.write(run / 'manifest.json', manifest)
            for task in manifest['tasks']:
                if task['kind'] == 'discovery':
                    p.record(run, task['id'], {'topics_checked': list(p.TOPICS), 'result': 'All topics checked; optional feed unavailable.', 'candidates': []})
                for source in task.get('sources', []):
                    entry = {'domain': source['domain'], 'checked_url': source['url'], 'status': 'checked',
                             'result': 'Synthetic fixture check.', 'candidates': [candidate] if source['domain'] == 'arxiv.org' else [],
                             'checks': [{'url': url, 'status': 'checked', 'result': 'Synthetic original check.'} for url in source['required_checks']]}
                    if source['domain'] == 'arxiv.org':
                        entry['title_discovery'] = title_discovery_fixture()
                    p.record(run, task['id'], entry)
            self.assertEqual(p.assemble(run)['sources'], 40)
            saved = p.read(run / 'candidates.json')[0]
            self.assertEqual(saved['published_at'], '2026-10-16')
            self.assertEqual(saved['freshness_date'], '2026-10-19')
            audit = p.read(root / 'data/research-audit/2026-10-19.json')
            self.assertEqual(len(next(s for s in audit['sources'] if s['domain'] == 'arxiv.org')['title_discovery']), 3)
            briefing['meta']['generated'] = '2026-10-19'
            briefing['topics'][0]['items'] = [{'title': candidate['title'], 'summary': candidate['summary'],
                'date': saved['freshness_date'], 'impact': 3, 'candidate_ids': [saved['id']], 'change_type': 'research',
                'sources': [{'url': candidate['url']}]}]
            p.write(root / 'data/briefing.json', briefing)
            p.write(run / 'editor-decisions.json', [{'id': saved['id'], 'decision': 'selected', 'reason': 'Test new public release.'}])
            self.assertEqual(p.check_editor(run)['status'], 'ready_to_publish')

    def test_updates_need_substantive_change_and_do_not_become_first_publication(self):
        import arxiv_discovery as a
        dates = self.dates(submitted_at='2026-09-01T12:00:00Z', announce_type='replace',
                           updated_at='2026-10-16T19:00:00Z', version=2, substantive_update=True)
        self.assertEqual(a.freshness_date(dates, '2026-09-01'), '2026-10-19')
        for changes in ({'substantive_update': False}, {'announce_type': 'cross'}, {'announce_type': 'new'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                a.freshness_date({**dates, **changes}, '2026-09-01')

    def test_release_metadata_rejects_missing_fields_and_impossible_instant(self):
        import arxiv_discovery as a
        with self.assertRaises(ValueError):
            a.freshness_date({}, '2026-10-16')
        with self.assertRaises(ValueError):
            a.freshness_date(self.dates(submitted_at='2026-10-18T23:30:00Z',
                                       announced_at='2026-10-18T22:30:00Z'), '2026-10-18')

    def test_timezone_announcement_and_submission_dates_are_distinct(self):
        import arxiv_discovery as a
        # Sunday evening US / Monday UTC and Berlin; never derive from weekdays.
        dates = self.dates(announced_at='2026-10-18T20:00:00-04:00')
        self.assertEqual(a.freshness_date(dates, '2026-10-16'), '2026-10-19')
        dates = self.dates(submitted_at='2026-10-18T23:30:00Z', announced_at='2026-10-19T02:30:00+02:00')
        self.assertEqual(a.freshness_date(dates, '2026-10-18'), '2026-10-19')
        with self.assertRaises(ValueError):
            a.freshness_date(self.dates(announced_at='2026-10-18T21:30:00Z'), '2026-10-16')
        with self.assertRaises(ValueError):
            a.freshness_date(self.dates(submitted_at='2026-10-16T17:57:55'), '2026-10-16')


class ArxivListingTests(unittest.TestCase):
    def test_all_saved_titles_can_be_reviewed_without_a_hidden_50_title_limit(self):
        import arxiv_discovery as a
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'titles.json'
            path.write_text(json.dumps({'titles': [{'id': str(i), 'title': f'Title {i}'} for i in range(174)]}))
            offset, seen = 0, []
            while offset is not None:
                page = a.title_page(path, offset)
                seen.extend(page['items'])
                offset = page['next_offset']
            self.assertEqual(len(seen), 174)
            self.assertEqual(len({item['id'] for item in seen}), 174)
            self.assertEqual(page['total'], 174)

    def test_api_discovery_paginates_update_titles_without_relabeling_submission_timestamps(self):
        import arxiv_discovery as a
        def fetch(url, timeout):
            start = int(parse_qs(urlparse(url).query)['start'][0])
            return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:os="http://a9.com/-/spec/opensearch/1.1/">'
                    f'<os:totalResults>2</os:totalResults><os:startIndex>{start}</os:startIndex>'
                    f'<entry><id>http://arxiv.org/abs/2609.{start:05}v2</id><title>Updated paper {start}</title>'
                    '<published>2026-09-01T12:00:00Z</published><updated>2026-10-16T19:00:00Z</updated>'
                    '</entry></feed>')
        result = a.collect_updates('2026-10-17', '2026-10-19', fetch=fetch, page_size=1, pause=0)
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['collected_count'], 2)
        self.assertEqual(result['titles'][0]['submitted_at'], '2026-09-01T12:00:00Z')
        self.assertEqual(result['titles'][0]['updated_at'], '2026-10-16T19:00:00Z')
        self.assertNotIn('listed_on', result['titles'][0])
        self.assertEqual(result['titles'][0]['version'], 2)
        self.assertIn('20261009', result['query'])  # Berlin midnight minus seven days converted to UTC.

    def test_latest_changes_include_replacements_and_announcement_type(self):
        import arxiv_discovery as a
        html = ('<h3>Showing new listings for Monday, 19 October 2026</h3>'
                '<dl><h3>New submissions (showing 1 of 1 entries)</h3>' +
                listing(1, 1, 1).split('<dt>')[1].split('</dl>')[0].join(['<dt>', '']) +
                '<h3>Replacement submissions (showing 1 of 1 entries)</h3>' +
                listing(1, 2, 1).split('<dt>')[1].split('</dl>')[0].join(['<dt>', '']) + '</dl>')
        result = a.collect('2026-10-19', '2026-10-19', fetch=lambda *_: html, kind='changes', pause=0)
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['declared_total'], 2)
        self.assertEqual([e['announce_type'] for e in result['titles']], ['new', 'replace'])

    def test_duplicate_page_never_claims_full_coverage(self):
        import arxiv_discovery as a
        result = a.collect('2026-10-19', '2026-10-19', fetch=lambda *_: listing(174, 0, 50), page_size=50, pause=0)
        self.assertFalse(result['complete'])
        self.assertEqual(result['collected_count'], 50)
        self.assertTrue(any('Duplicate' in reason for reason in result['limitations']))
        self.assertIsNotNone(result['next_skip'])

    def test_declared_total_change_and_page_budget_are_explicit_gaps(self):
        import arxiv_discovery as a
        pages = iter([listing(174, 0, 50), listing(175, 50, 50)])
        result = a.collect('2026-10-19', '2026-10-19', fetch=lambda *_: next(pages), page_size=50, pause=0)
        self.assertFalse(result['complete'])
        self.assertTrue(any('total changed' in reason for reason in result['limitations']))
        result = a.collect('2026-10-19', '2026-10-19', fetch=lambda *_: listing(174, 0, 50), max_pages=1, page_size=50)
        self.assertFalse(result['complete'])
        self.assertTrue(any('budget' in reason for reason in result['limitations']))

    def test_outside_window_and_wrong_page_do_not_become_current_titles(self):
        import arxiv_discovery as a
        result = a.collect('2026-10-20', '2026-10-20', fetch=lambda *_: listing(2, 0, 2), pause=0)
        self.assertEqual(result['titles'], [])
        self.assertFalse(result['window_complete'])
        result = a.collect('2026-10-19', '2026-10-19', fetch=lambda *_: '<html>blocked</html>', pause=0)
        self.assertFalse(result['complete'])
        self.assertTrue(result['limitations'])

    def test_collects_all_174_titles_across_pages(self):
        import arxiv_discovery as a
        calls = []
        def fetch(url, timeout):
            skip = int(parse_qs(urlparse(url).query)['skip'][0])
            calls.append(skip)
            return listing(174, skip, min(50, 174 - skip))
        result = a.collect('2026-10-17', '2026-10-19', fetch=fetch, page_size=50, pause=0)
        self.assertTrue(result['complete'], result['limitations'])
        self.assertEqual(result['declared_total'], 174)
        self.assertEqual(result['collected_count'], 174)
        self.assertEqual(len(result['titles']), 174)
        self.assertEqual(calls, [0, 50, 100, 150])
        self.assertEqual(result['titles'][0]['listed_on'], '2026-10-19')
        self.assertEqual(result['titles'][0]['title'], 'Paper 0 & safety')
        self.assertTrue(all(p['url'].startswith('https://arxiv.org/list/') for p in result['pages']))
