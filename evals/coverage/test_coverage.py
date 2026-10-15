import copy
import unittest
from .freeze import validate, verify
from .score import Scorer
from evals.score import Scorer as LegacyScorer


class AnnotationTests(unittest.TestCase):
    def test_frozen_sources_labels_requests(self):
        data, requests, cases = validate()
        self.assertEqual(len(cases), 16)
        self.assertEqual(len(data['documents']), 8)
        verify('data')
        self.assertTrue(all('expected' not in r for r in requests.values()))

    def fixture(self):
        data = {'documents': [{'id': 'd', 'sha256': 'hash'}], 'evidence': [{'id': 'e', 'document_id': 'd',
            'locator': {'kind': 'text', 'byte_start': 0, 'byte_end': 12}, 'expected': 'Launch\n\n1971', 'content_runs': [[0, 6], [8, 12]]}]}
        docs = {'d': {'document_id': 'd', 'revision': 'r1', 'original': {'sha256': 'hash'}, 'chunks': []}}
        items = [{'key': {'document_id': 'd', 'revision': 'r1'}, 'text': text,
                  'sources': [{'revision': 'r1', 'locator': {'Text': {'bytes': {'start': start, 'end': end}}}}]}
                 for start, end, text in [(0, 6, 'Launch'), (8, 12, '1971')]]
        return data, docs, items

    def test_whitespace_only_gap_is_accepted_and_legacy_score_unchanged(self):
        data, docs, items = self.fixture()
        self.assertTrue(Scorer(data, docs).coverage(items, ['e'])['e']['covered'])
        self.assertFalse(LegacyScorer(data, docs).coverage(items, ['e'])['e']['covered'])

    def test_missing_digit_or_wrong_revision_receives_no_credit(self):
        data, docs, items = self.fixture()
        missing = copy.deepcopy(items); missing[1]['sources'][0]['locator']['Text']['bytes']['end'] = 11
        self.assertFalse(Scorer(data, docs).coverage(missing, ['e'])['e']['covered'])
        items[1]['key']['revision'] = 'r2'
        self.assertFalse(Scorer(data, docs).coverage(items, ['e'])['e']['covered'])


if __name__ == '__main__': unittest.main()
