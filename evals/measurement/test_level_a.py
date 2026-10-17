from copy import deepcopy
import json
from pathlib import Path
import unittest

from .activate_level_a import CANONICAL, DEFINITION, SOURCE_SHA, verify_previous
from .families import digest, encoded, handoff, load, validate_receipt
from .pilot_controls import score_control
from .table_grounding import score_case
from .typed_facts import permitted_values, validate_gold

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/reports/t39-gold-review-v1.6'
GOLD = load(OUT / 'gold.json')
CASE = next(c for c in GOLD['cases'] if c['number'] == 107)


def capture(value=CANONICAL, name='answer', proofs=None):
    return {'status': 'supported', 'fields': [{'name': name, 'type': 'string', 'value_text': value,
        'proofs': deepcopy(CASE['roles'][0]['proof_sets'][0]) if proofs is None else proofs}]}


class LevelAActivationTests(unittest.TestCase):
    def test_frozen_chain_and_single_case_change(self):
        self.assertEqual(verify_previous(), 104)
        validate_gold(GOLD)
        old = load(OUT.with_name('t39-gold-review-v1.5') / 'gold.json')
        changed = [a['number'] for a, b in zip(GOLD['cases'], old['cases']) if a != b]
        self.assertEqual(changed, [107])
        for a, b in zip(GOLD['cases'], old['cases']):
            for key in ('case_id', 'question', 'document', 'document_sha256', 'source_text_sha256',
                        'original_alternatives', 'original_expected', 'tier', 'format'):
                self.assertEqual(a[key], b[key], key)
        self.assertFalse(any(c['pending_decisions'] for c in GOLD['cases']))
        self.assertFalse(GOLD['approved_for_execution'])
        self.assertFalse(GOLD['independent_review'])

    def test_all_source_formulations_and_field_names(self):
        self.assertEqual(len(permitted_values(CASE['roles'][0])), 6)
        for value in permitted_values(CASE['roles'][0]):
            for name in ('answer', 'value', 'definition', 'offensive_language_definition'):
                result = score_case(CASE, capture(value, name), {})
                self.assertTrue(result['correct'], (name, value))
                self.assertTrue(result['evidence_correct'])

    def test_definition_disjunction_not_and_or_narrower_category(self):
        for value in (CANONICAL.replace(' or ', ' and '), 'hate speech', 'targeted offense',
                      'profanity', 'targeted or untargeted offense', *CASE['original_alternatives']):
            self.assertFalse(score_case(CASE, capture(value), {})['correct'], value)

    def test_old_intro_cannot_prove_new_definition(self):
        proof = [{'document_sha256': SOURCE_SHA, 'utf8_start': 1114, 'utf8_end': 2063}]
        result = score_case(CASE, capture(proofs=proof), {})
        self.assertTrue(result['correct'])
        self.assertFalse(result['evidence_correct'])
        self.assertTrue(result['correct_answer_wrong_evidence'])

    def test_scope_statement_alone_is_not_definition_proof(self):
        proof = [{'document_sha256': SOURCE_SHA, 'utf8_start': 6264, 'utf8_end': 6341}]
        self.assertFalse(score_case(CASE, capture(proofs=proof), {})['evidence_correct'])

    def test_no_substring_or_extra_fields_credit(self):
        self.assertFalse(score_case(CASE, capture(CANONICAL + ' or other things'), {})['correct'])
        extra = capture()
        extra['fields'].append(deepcopy(extra['fields'][0]))
        self.assertFalse(score_case(CASE, extra, {})['correct'])
        wrong_type = capture()
        wrong_type['fields'][0]['type'] = 'number'
        self.assertFalse(score_case(CASE, wrong_type, {})['correct'])

    def test_closed_book_definition_and_old_label_are_separate(self):
        raw = lambda value: json.dumps({'status': 'answer', 'answer': value})
        self.assertTrue(score_control(CASE, raw(DEFINITION))['closed_book_gold_match'])
        self.assertFalse(score_control(CASE, raw(CASE['original_alternatives'][0]))['closed_book_gold_match'])

    def test_waiver_and_source_offsets_are_explicit(self):
        a = load(OUT / 'adjudication.json')
        self.assertEqual(a['case_107_activation'], 'applied_to_candidate')
        self.assertIn('skip the two-reviewer requirement for 107', a['user_instruction'])
        self.assertFalse(a['independent_review_acceptance'])
        self.assertFalse(a['sealed_content_opened'])
        e = a['evidence'][-1]
        self.assertEqual((e['utf8_start'], e['utf8_end']), (6415, 6672))
        self.assertEqual(e['quote'], DEFINITION)
        self.assertEqual(len(e['quote'].encode()), e['utf8_end'] - e['utf8_start'])

    def test_custody_remains_unattested_and_rebound(self):
        ledger = load(OUT / 'family-ledger.json')
        packet = load(OUT / 'custodian-input.json')
        receipt = load(OUT / 'custodian-receipt-template.json')
        self.assertEqual(packet, handoff(ledger))
        self.assertEqual(ledger['inputs']['gold_sha256'], digest(encoded(GOLD)))
        self.assertEqual(packet['policy_hashes']['gold-candidate-v1.6.json'], digest(encoded(GOLD)))
        self.assertEqual(receipt['handoff_sha256'], digest(encoded(packet)))
        self.assertNotEqual(receipt['handoff_sha256'], load(OUT.with_name('t39-gold-review-v1.5') /
                                                           'custodian-receipt-template.json')['handoff_sha256'])
        with self.assertRaises(ValueError):
            validate_receipt(receipt, packet)
        pilot = load(OUT / 'pilot-audit.json')
        self.assertEqual(len(pilot['candidate_control_roster']), 101)
        self.assertFalse(any(c['pending_decisions'] for c in pilot['candidate_control_roster']))
        self.assertEqual(pilot['primary_by_format'], {'txt': 51, 'pdf': 17, 'json': 33})


if __name__ == '__main__':
    unittest.main()
