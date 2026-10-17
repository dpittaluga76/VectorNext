from copy import deepcopy
import itertools
import json
from pathlib import Path
import unittest

from .families import digest, encoded, handoff, load, validate_receipt
from .pilot_controls import score_control
from .table_grounding import score_case
from .typed_facts import permitted_values, validate_gold

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/reports/t39-gold-review-v1.5'
GOLD = load(OUT / 'gold.json')
CASES = {c['number']: c for c in GOLD['cases']}
OLD = {c['number']: c for c in load(ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json')['cases']}


def capture(n, value=None, proofs=None):
    r = CASES[n]['roles'][0]
    return {'status': 'supported', 'fields': [{'name': r['id'], 'type': 'string',
            'value_text': r['value_string'] if value is None else value,
            'proofs': deepcopy(r['proof_sets'][0]) if proofs is None else proofs}]}


class GoldReviewTests(unittest.TestCase):
    def test_only_six_cases_changed_and_originals_retained(self):
        validate_gold(GOLD)
        self.assertEqual([n for n in CASES if CASES[n] != OLD[n]], [10, 34, 47, 53, 71, 107])
        for n, c in CASES.items():
            for k in ('case_id', 'question', 'document', 'document_sha256', 'source_text_sha256',
                      'original_expected', 'original_alternatives', 'format'):
                self.assertEqual(c[k], OLD[n][k], (n, k))
        self.assertFalse(GOLD['approved_for_execution'])
        self.assertFalse(GOLD['independent_review'])

    def test_all_new_declared_values_pass(self):
        for n in (10, 34, 47, 53):
            for value in permitted_values(CASES[n]['roles'][0]):
                result = score_case(CASES[n], capture(n, value), {})
                self.assertTrue(result['correct'], (n, value))
                self.assertTrue(result['evidence_correct'], (n, value))

    def test_all_destination_orders_and_natural_final_and(self):
        names = ['Bukhara', 'Besh Baliq', 'Almaliq', 'Samarqand']
        for order in itertools.permutations(names):
            for value in (', '.join(order), ', '.join(order[:-1]) + ' and ' + order[-1],
                          ', '.join(order[:-1]) + ', and ' + order[-1]):
                self.assertTrue(score_case(CASES[10], capture(10, value), {})['correct'])

    def test_subsets_duplicates_and_extra_destinations_fail(self):
        for value in ('Bukhara', 'Besh Baliq, Almaliq, and Samarqand',
                      'Bukhara, Bukhara, Almaliq, Samarqand',
                      'Bukhara, Besh Baliq, Almaliq, Samarqand, Qocho'):
            self.assertFalse(score_case(CASES[10], capture(10, value), {})['correct'])

    def test_complete_set_with_only_one_sentence_has_wrong_grounding(self):
        one = [CASES[10]['roles'][0]['proof_sets'][0][1]]
        result = score_case(CASES[10], capture(10, proofs=one), {})
        self.assertTrue(result['correct'])  # D5 value primary remains unchanged.
        self.assertFalse(result['evidence_correct'])
        self.assertTrue(result['correct_answer_wrong_evidence'])

    def test_entailment_and_unqualified_yes_are_not_gold(self):
        for value in ('entailment', 'YES', 'always YES', 'AllenNlp'):
            self.assertFalse(score_case(CASES[34], capture(34, value), {})['correct'])
        self.assertTrue(score_case(CASES[34], capture(34, OLD[34]['roles'][0]['value_string']), {})['correct'])

    def test_method_only_answer_and_method_only_proof_are_distinct_failures(self):
        value = 'We introduce sparse attention into the Transformer architecture'
        self.assertFalse(score_case(CASES[47], capture(47, value), {})['correct'])
        proof = [{'document_sha256': CASES[47]['document_sha256'], 'utf8_start': 3219, 'utf8_end': 3358}]
        r = score_case(CASES[47], capture(47, proofs=proof), {})
        self.assertTrue(r['correct'])
        self.assertFalse(r['evidence_correct'])

    def test_car_model_not_manufacturer_example_or_model_year(self):
        for value in ('car', 'the car', 'manufacturer', 'Acura', 'Acura ILX', '2013 Acura ILX'):
            self.assertFalse(score_case(CASES[53], capture(53, value), {})['correct'])

    def test_stress_case_preserves_original_supported_label(self):
        self.assertEqual(CASES[71]['expected'], 'supported')
        self.assertEqual(CASES[71]['original_expected'], 'supported')
        self.assertEqual(CASES[71]['roles'], OLD[71]['roles'])
        r = score_case(CASES[71], capture(71), {})
        self.assertIsNone(r['correct'])
        self.assertEqual(r['outcome'], 'stress_not_accuracy_scored')

    def test_107_replacement_is_proposed_not_activated(self):
        self.assertEqual(CASES[107]['roles'], OLD[107]['roles'])
        self.assertEqual([n for n, c in CASES.items() if c['pending_decisions']], [107])
        self.assertEqual(score_case(CASES[107], capture(107), {})['outcome'], 'pending_gold_not_scored')
        a = load(OUT / 'adjudication.json')
        self.assertIn('We label a post', a['proposed_107_definition'])
        self.assertFalse(a['independent_review_acceptance'])

    def test_new_rosters_counts_and_controls_agree(self):
        tiers = load(OUT / 'tiers.json')
        self.assertEqual(tiers['counts'], {'primary_direct_extraction': 101, 'derived_inference': 3,
                                          'stress_adjudication': 16})
        pilot = load(OUT / 'pilot-audit.json')
        self.assertEqual(pilot['primary_by_format'], {'txt': 51, 'pdf': 17, 'json': 33})
        self.assertEqual(len(pilot['candidate_control_roster']), 101)
        self.assertNotIn(71, [r['number'] for r in pilot['candidate_control_roster']])
        self.assertEqual([r['number'] for r in pilot['candidate_control_roster'] if r['pending_decisions']], [107])
        self.assertTrue(all(not pairs for pairs in pilot['primary_pairs'].values()))

    def test_closed_book_uses_complete_set_and_pending_condition(self):
        raw = lambda value: json.dumps({'status': 'answer', 'answer': value})
        self.assertFalse(score_control(CASES[10], raw('Bukhara'))['closed_book_gold_match'])
        self.assertTrue(score_control(CASES[10], raw(CASES[10]['roles'][0]['value_string']))['closed_book_gold_match'])
        self.assertEqual(score_control(CASES[107], raw('Anything'))['reason'], 'unresolved_gold')

    def test_custodian_packet_rebound_and_no_fabricated_receipt(self):
        ledger = load(OUT / 'family-ledger.json')
        packet = load(OUT / 'custodian-input.json')
        receipt = load(OUT / 'custodian-receipt-template.json')
        self.assertEqual(packet, handoff(ledger))
        self.assertEqual(packet['ledger_sha256'], digest(encoded(ledger)))
        self.assertEqual(packet['policy_hashes']['gold-candidate-v1.5.json'], digest((OUT / 'gold.json').read_bytes()))
        self.assertEqual(ledger['inputs']['gold_sha256'], digest((OUT / 'gold.json').read_bytes()))
        self.assertEqual(ledger['inputs']['builder_sha256'], digest((ROOT / 'evals/measurement/build_gold_review.py').read_bytes()))
        self.assertEqual(receipt['handoff_sha256'], digest(encoded(packet)))
        self.assertNotEqual(receipt['handoff_sha256'], load(ROOT / 'docs/reviews/t39-d6-custodian-receipt-template-v1.3.json')['handoff_sha256'])
        with self.assertRaises(ValueError):
            validate_receipt(receipt, packet)
        self.assertEqual(ledger['summary']['primary_clusters']['established_cases'], 97)
        self.assertEqual(ledger['summary']['primary_clusters']['families'], 57)
        self.assertEqual(ledger['summary']['cross_split_verified_cases'], 0)


if __name__ == '__main__':
    unittest.main()
