"""Read-backed equivalence of an original release and its publisher syndication."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editorial_coverage import history_id, validate_coverage
from research_integrity import attest_cache


class SyndicatedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.title = 'Example Data Platform introduces human-governed business ontologies'
        self.paragraph = ('Example Data Platform business ontologies define concepts and relationships. '
                          'The AI Discovery agent generates business ontologies from schemas and documentation. '
                          'Business experts then review and approve these ontologies before deployment. '
                          'These governed ontologies provide consistent context for enterprise agents and applications.')
        self.stage = 'New Example Data Platform capabilities will be available within the next 12 months.'
        self.urls = ['https://www.example.com/news/release/', 'https://www.prnewswire.com/news-releases/example-123.html']
        self.evidence = []
        for index, url in enumerate(self.urls):
            text = '\n'.join([self.title, 'Oct 27, 2026', self.paragraph, self.stage, 'SOURCE Example'])
            cache = self.root / f'cache-{index}.json'
            cache.write_text(json.dumps({'url': url, 'retrieved_at': '2026-11-03T07:00:00Z', 'text': text}))
            receipt = self.root / f'receipt-{index}.json'
            attest_cache(cache, url, receipt)
            self.evidence.append({'url': url, 'receipt': str(receipt), 'excerpt': self.paragraph,
                                  'date_quote': 'Oct 27, 2026'})
        self.candidate = {'id': 'candidate', 'url': self.urls[0], 'published_at': '2026-10-27',
                          'change_type': 'announcement', 'headline_terms': ['Example Data Platform'],
                          'development': 'AI Discovery erzeugt Geschäftsontologien aus Schemata.',
                          'summary': 'Fachverantwortliche prüfen und genehmigen die Ergebnisse.'}
        self.item = {'title': 'AI Discovery für Geschäftsontologien angekündigt', 'date': '2026-10-27',
                     'change_type': 'announcement', 'sources': [{'url': self.urls[1]}],
                     'summary': 'AI Discovery erzeugt Geschäftsontologien aus Schemata, die Fachverantwortliche prüfen und genehmigen.[1]'}
        self.proof = {'summary_quote': self.item['summary'],
                      'development_terms': ['Geschäftsontologien aus Schemata', 'prüfen und genehmigen'],
                      'development_subjects': ['AI Discovery'],
                      'source_identity': {'kind': 'publisher_syndication', 'publisher': 'Example',
                                          'publisher_domain': 'example.com', 'release_title': self.title,
                                          'original': self.evidence[0], 'syndicated': self.evidence[1],
                                          'stage_quote': self.stage, 'change_type': 'announcement'}}

    def validate(self, candidate=None, item=None, proof=None):
        candidate, item, proof = candidate or self.candidate, item or self.item, proof or self.proof
        decision = {'id': 'candidate', 'decision': 'duplicate',
                    'duplicate_of': {'history_id': history_id(item)}, 'history_coverage': proof}
        return validate_coverage({'candidate': candidate}, [decision], [], [], [item])

    def test_original_and_syndicated_release_prove_short_historical_product_name(self):
        self.assertEqual(self.validate()['duplicates'], 1)
    def test_shared_product_text_cannot_replace_release_stage_evidence(self):
        proof = copy.deepcopy(self.proof)
        proof['source_identity']['stage_quote'] = self.paragraph
        with self.assertRaisesRegex(ValueError, 'release-stage'):
            self.validate(proof=proof)

    def test_bound_identity_rejects_unrelated_sources_products_dates_and_witnesses(self):
        cases = [
            ('original URL', lambda p: p['source_identity']['original'].update(url='https://www.example.com/unrelated')),
            ('history URL', lambda p: p['source_identity']['syndicated'].update(url='https://www.prnewswire.com/other')),
            ('publisher domain', lambda p: p['source_identity'].update(publisher_domain='evil.example.com')),
            ('publisher attribution', lambda p: p['source_identity'].update(publisher='Someone Else')),
            ('different release title', lambda p: p['source_identity'].update(release_title='Unrelated Example Data Platform announcement')),
            ('invented paragraph', lambda p: p['source_identity']['original'].update(excerpt=self.paragraph + ' Invented claims.')),
            ('different date', lambda p: p['source_identity']['original'].update(date_quote='Oct 28, 2026')),
            ('different subject', lambda p: p.update(development_subjects=['AI Registry'])),
            ('invented history quote', lambda p: p.update(summary_quote=self.item['summary'] + ' More claims.')),
            ('generic product names', lambda p: p.update(development_terms=['AI Discovery', 'AI Discovery'])),
            ('different milestone', lambda p: p['source_identity'].update(change_type='general_availability')),
            ('missing receipt', lambda p: p['source_identity']['syndicated'].pop('receipt')),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                proof = copy.deepcopy(self.proof)
                mutate(proof)
                with self.assertRaises(ValueError):
                    self.validate(proof=proof)
        candidate = {**self.candidate, 'headline_terms': ['Example AI Registry']}
        with self.assertRaisesRegex(ValueError, 'headline anchor'):
            self.validate(candidate=candidate)
        with self.assertRaisesRegex(ValueError, 'date differs'):
            self.validate(item={**self.item, 'date': '2026-10-28'})
        with self.assertRaisesRegex(ValueError, 'change_type'):
            self.validate(item={**self.item, 'change_type': 'preview'})
        proof = copy.deepcopy(self.proof)
        proof.pop('source_identity')
        with self.assertRaisesRegex(ValueError, 'exact candidate source URL'):
            self.validate(proof=proof)

    def test_tampered_retrieval_remains_rejected(self):
        cache = self.root / 'cache-1.json'
        cache.write_text(cache.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.validate()

    def test_syndication_exception_does_not_infer_preview_beta_or_ga(self):
        for stage in ('preview', 'public_beta', 'general_availability'):
            with self.subTest(stage=stage):
                candidate, item, proof = map(copy.deepcopy, (self.candidate, self.item, self.proof))
                candidate['change_type'] = item['change_type'] = proof['source_identity']['change_type'] = stage
                with self.assertRaisesRegex(ValueError, 'announcement'):
                    self.validate(candidate, item, proof)


if __name__ == '__main__':
    unittest.main()
