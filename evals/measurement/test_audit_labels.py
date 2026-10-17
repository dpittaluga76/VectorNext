import unittest
import json
from pathlib import Path
import tempfile

from .audit_labels import audit_cases, numbers, verified_input, sha256


def case(text, alternatives):
    return {
        'n': 1, 'id': 'synthetic', 'document_sha256': 'synthetic', 'source_text': text,
        'request': {'split': 'development', 'source': 'squad', 'document': 'synthetic.txt', 'question': 'How many?'},
        'label': {'split': 'development', 'expected': 'supported', 'alternatives': alternatives, 'support': []},
    }


class LabelAuditTests(unittest.TestCase):
    def test_qualifier_and_clipping_are_leads_not_changes(self):
        original = case('It rises to almost 2,000 m.', ['2,000 m', 'almost 2,000 m'])
        result = audit_cases([original])
        first = result['cases'][0]['alternatives'][0]
        self.assertIn('source_has_immediate_qualifier', first['flags'])
        self.assertEqual(first['immediate_source_qualifiers'], ['almost'])
        self.assertEqual(original['label']['alternatives'], ['2,000 m', 'almost 2,000 m'])
        self.assertFalse(result['approved_for_execution'])

    def test_exact_spelling_and_reference_ids(self):
        self.assertEqual(numbers('BIBREF22 INLINEFORM3 x12 9007199254740993 1,234.56789'),
                         ['9007199254740993', '1,234.56789'])
        self.assertEqual(numbers('1910–1940; £30m; 11–13th century; -0.50'),
                         ['1910', '1940', '30', '11', '13', '-0.50'])

    def test_evidence_mismatch_uses_own_annotation(self):
        item = case('Cats. Dogs.', ['Cats', 'Dogs'])
        item['request']['source'] = 'qasper'
        item['label']['support'] = [
            {'extractive_spans': ['Cats'], 'evidence': ['Dogs.']},
            {'extractive_spans': ['Dogs'], 'evidence': ['Cats.']},
        ]
        result = audit_cases([item])
        self.assertTrue(all('not_literal_in_own_annotated_evidence' in a['flags']
                            for a in result['cases'][0]['alternatives']))

    def test_sealed_cases_are_refused(self):
        item = case('one', ['one'])
        item['request']['split'] = 'sealed'
        with self.assertRaisesRegex(ValueError, 'development'):
            audit_cases([item])

    def test_sealed_member_path_refused_before_member_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit = root / 'audit.json'
            audit.write_text(json.dumps({
                'opened_proposal_split': 'development',
                'verified_development_members': [{'path': 'sealed/labels.json', 'sha256': 'unused'}],
            }), encoding='utf-8')
            # Neither manifest nor sealed member exists: path validation must run first.
            with self.assertRaisesRegex(ValueError, 'Only development member paths'):
                verified_input(audit, root)

    def test_changed_source_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'development').mkdir()
            (root / 'manifest.json').write_text('{}', encoding='utf-8')
            source = root / 'development/source.txt'
            source.write_text('original', encoding='utf-8')
            audit = root / 'audit.json'
            audit.write_text(json.dumps({
                'opened_proposal_split': 'development',
                'manifest_sha256': sha256(root / 'manifest.json'),
                'verified_development_members': [{'path': 'development/source.txt', 'sha256': sha256(source)}],
            }), encoding='utf-8')
            self.assertEqual(verified_input(audit, root)[1], 1)
            source.write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Development member changed'):
                verified_input(audit, root)


if __name__ == '__main__':
    unittest.main()
