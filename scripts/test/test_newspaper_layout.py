"""Public newspaper structure and retained content contracts."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render
from search import build_search_page
from test_render import BRIEFING


class NewspaperLayout(unittest.TestCase):
    def test_shared_masthead_and_navigation_at_every_depth(self):
        for key, _, _ in render.RANGES:
            for page in (render.build_overview(BRIEFING, key), render.build_topic_page(BRIEFING['topics'][0], BRIEFING['meta'], BRIEFING['topics'], key)):
                self.assertIn('class="masthead"', page)
                self.assertIn('>AI Briefing</a>', page)
                self.assertIn('href="ai-news.html"', page)
                self.assertIn('href="' + ('' if key == 'today' else '../') + 'search.html"', page)
                self.assertNotIn('fonts.googleapis.com', page)
        self.assertIn('class="masthead"', build_search_page())


    def test_overviews_keep_search_and_detail_pages_keep_complete_payload(self):
        for key, _, _ in render.RANGES:
            overview = render.build_overview(BRIEFING, key)
            prefix = '' if key == 'today' else '../'
            self.assertIn('role="search" method="get" action="' + prefix + 'search.html"', overview)
            self.assertIn('name="q"', overview)
            self.assertIn('href="' + prefix + '30d/index.html"', overview)
            topic = BRIEFING['topics'][0]
            page = render.build_topic_page(topic, BRIEFING['meta'], BRIEFING['topics'], key)
            self.assertIn(render.build_detail(topic['items']), page)
            self.assertIn(render.build_radar_svg(topic['items']), page)
            self.assertIn('Wie sich der Impact bestimmt', page)
            self.assertIn('Nummer</b> = siehe Meldungen unten', page)

    def test_featured_text_and_sources_are_escaped_without_data_mutation(self):
        briefing = copy.deepcopy(BRIEFING)
        briefing['topics'][0]['items'][0]['title'] = '<img src=x onerror=alert(1)>'
        briefing['topics'][0]['items'][0]['summary'] = '<script>bad()</script>'
        before = copy.deepcopy(briefing)
        page = render.build_overview(briefing)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;script&gt;bad()', page)
        self.assertIn('https://example.com/a', page)
        self.assertEqual(briefing, before)

    def test_search_page_can_share_edition_and_full_navigation(self):
        header = render.newspaper_header(BRIEFING['meta'], 'index', 'today', 'Das Archiv')
        page = build_search_page(header, render.nav_html(BRIEFING['topics'], 'search'))
        self.assertIn('Ausgabe vom 10. Juni 2026', page)
        self.assertIn('href="ai-news.html"', page)
        for marker in ('id="search-form"', 'id="search-status"', 'id="search-more"', '<noscript>'):
            self.assertIn(marker, page)

    def test_overview_search_reserves_space_for_outside_focus_ring(self):
        # Desktop grid rows used to touch: the 3px outline + 3px offset
        # painted over the help text. Mobile already has an 8px margin.
        import re
        grid_rule = next(rule for rule in re.findall(r'\.overview-search\{([^}]+)\}', render.CSS)
                         if 'display:grid' in rule)
        gap = re.search(r'row-gap:(\d+)px', grid_rule)
        self.assertIsNotNone(gap, 'Reserve a row gap between search controls and help text')
        self.assertGreaterEqual(int(gap.group(1)), 8)
        self.assertIn(':focus-visible{outline:3px solid var(--blue);outline-offset:3px}', render.CSS)

    def test_lead_and_legend_share_a_natural_height_column(self):
        from html.parser import HTMLParser

        class Columns(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.parents = {}

            def handle_starttag(self, tag, attrs):
                cls = dict(attrs).get('class', '')
                if cls in ('lead-story', 'edition-aside', 'headlines'):
                    self.parents[cls] = list(self.stack)
                if tag not in ('br', 'input', 'meta', 'link'):
                    self.stack.append(cls)

            def handle_endtag(self, tag):
                if self.stack:
                    self.stack.pop()

        for key, _, _ in render.RANGES:
            parser = Columns()
            parser.feed(render.build_overview(BRIEFING, key))
            self.assertIn('front-primary', parser.parents['lead-story'])
            self.assertIn('front-primary', parser.parents['edition-aside'])
            self.assertNotIn('front-primary', parser.parents['headlines'])

    def test_topic_desks_are_independent_and_keep_contiguous_reading_order(self):
        from html.parser import HTMLParser

        class Desks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.columns = []
                self.in_heading = False

            def handle_starttag(self, tag, attrs):
                cls = dict(attrs).get('class')
                if cls == 'edition-column':
                    self.columns.append([])
                self.in_heading = tag == 'h3' and bool(self.columns)

            def handle_data(self, data):
                if self.in_heading:
                    self.columns[-1].append(data)

            def handle_endtag(self, tag):
                if tag == 'h3':
                    self.in_heading = False

        for key, _, _ in render.RANGES:
            for length in (0, 1, 8, 9):
                for summary in ('', 'Kurz.', 'Lange Zusammenfassung. ' * 100):
                    briefing = copy.deepcopy(BRIEFING)
                    briefing['topics'] = [dict(copy.deepcopy(BRIEFING['topics'][0]),
                        id=f'topic-{i}', name=f'Thema {i}', summary=summary,
                        group='Praxis' if i < 6 else 'Recht',
                        items=[] if i % 2 else copy.deepcopy(BRIEFING['topics'][0]['items']))
                        for i in range(length)]
                    before = copy.deepcopy(briefing)
                    parser = Desks()
                    parser.feed(render.build_overview(briefing, key))
                    self.assertEqual([name for column in parser.columns for name in column],
                                     [t['name'] for t in briefing['topics']])
                    self.assertTrue(all(len(c) <= (length + 1) // 2 for c in parser.columns))
                    self.assertEqual(briefing, before)
        import re
        match = re.search(r'\.edition-sections\{([^}]+)\}', render.CSS)
        self.assertIsNotNone(match)
        rule = match.group(1) if match else ''
        self.assertIn('display:grid', rule)
        self.assertIn('align-items:start', rule)
        self.assertNotRegex(rule, r'(?:^|;)columns:')

    def test_radar_number_ink_meets_text_contrast(self):
        for _, _, color in render.CATS:
            ink = render.contrast_text(color)
            a, b = sorted((render.lum(color), render.lum(ink)))
            self.assertGreaterEqual((b + .05) / (a + .05), 4.5, color)

    def test_reading_landmark_and_named_navigation(self):
        page = render.build_overview(BRIEFING)
        self.assertIn('<main class="sheet">', page)
        self.assertIn('aria-label="Zeitraum"', page)
        self.assertIn('aria-label="Themen"', page)
        detail = render.build_detail(BRIEFING['topics'][0]['items'])
        self.assertIn('color:var(--ink)', detail)

    def test_lead_uses_impact_then_date_then_stable_identity(self):
        briefing = copy.deepcopy(BRIEFING)
        topic = briefing['topics'][0]
        base = topic['items'][0]
        topic['items'] = [dict(base, title='Zebra', date='08.06.2026'),
                          dict(base, title='Beta', date='09.06.2026'),
                          dict(base, title='Alpha', date='09.06.2026')]
        lead_topic, lead = render.select_lead(briefing['topics'])
        self.assertEqual(lead['title'], 'Alpha')
        self.assertEqual(lead_topic['id'], 'ai-news')
        page = render.build_overview(briefing)
        self.assertIn('class="lead-story"', page)
        self.assertEqual(page.count('>Alpha</a>'), 1)
        self.assertIn('Heute-Lede.', page)
        self.assertIn('09.06.2026', page)
        topic['items'].reverse()
        self.assertEqual(render.select_lead(briefing['topics'])[1]['title'], 'Alpha')
        topic['items'].append(dict(base, title='Impact wins', impact=5, date='01.06.2026'))
        self.assertEqual(render.select_lead(briefing['topics'])[1]['title'], 'Impact wins')
        topic['items'] = []
        self.assertIsNone(render.select_lead(briefing['topics']))
        self.assertNotIn('class="lead-story"', render.build_overview(briefing))


if __name__ == '__main__':
    unittest.main()
