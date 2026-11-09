import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_stories import grouped


class SourceStoryTests(unittest.TestCase):
    def row(self, url, **fields):
        return dict({'title': 'Review', 'date': '2026-11-06', 'sources': [{'url': url}]}, **fields)

    def test_same_article_across_topics_keeps_the_two_angles(self):
        url = 'https://github.blog/changelog/copilot-code-review'
        a = self.row(url, topic='Tools')
        b = self.row(url + '/?utm_source=feed', title='Kosten pro Review', topic='Enterprise')
        self.assertEqual(grouped([a, b]), [dict(a, angles=[b])])
        self.assertNotIn('angles', a)

    def test_different_articles_milestones_dates_and_query_ids_stay_separate(self):
        url = 'https://github.blog/changelog/copilot'
        rows = [self.row(url, change_type='preview'), self.row(url, change_type='general_availability'),
                self.row(url, date='2026-11-07'), self.row(url + '-billing'),
                self.row(url + '?id=1'), self.row(url + '?id=2')]
        self.assertEqual(grouped(rows), rows)

    def test_indexes_roundups_or_secondary_links_cannot_merge_stories(self):
        for path in ('/', '/changelog', '/insights/radar-brief-2026-11-07'):
            rows = [self.row('https://example.com' + path, title=str(i)) for i in range(2)]
            self.assertEqual(grouped(rows), rows)
        a, b = self.row('https://example.com/a'), self.row('https://example.com/b')
        b['sources'].extend(a['sources'])
        self.assertEqual(grouped([a,b]), [a,b])
