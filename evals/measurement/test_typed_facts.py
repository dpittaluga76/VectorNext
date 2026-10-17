from copy import deepcopy
import json
from pathlib import Path
import unittest

from .build_typed_candidate import base_role
from .format_contract import INSTRUCTION, messages_for_stage, require_string_fields
from .typed_facts import (digest, floor, oracle_fields, permitted_values, report,
                         role_result, score_case, validate_gold, verify_paired_format)

ROOT = Path(__file__).resolve().parents[2]
GOLD = json.loads((ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json').read_text(encoding='utf-8'))
CASES = {c['number']: c for c in GOLD['cases']}


def capture(case, value=None, *, name=None, kind='string', proofs=None):
    role = case['roles'][0]
    return {'status': 'supported', 'fields': [{'name': name or role['id'], 'type': kind,
        'value_text': role['value_string'] if value is None else value,
        'proofs': deepcopy(role['proof_sets'][0]) if proofs is None else proofs}]}


def synthetic(value):
    role = base_role('answer', value)
    role['proof_sets'] = [[{'document_sha256': '0' * 64, 'pointer': '/records/0/cells/1'}]]
    return {'number': 1, 'case_id': 'synthetic', 'tier': 'primary_direct_extraction',
            'pending_decisions': [], 'expected': 'supported', 'roles': [role],
            'allowed_field_mappings': [{'answer': 'answer'}]}


class TypedFactsTests(unittest.TestCase):
    def test_candidate_is_not_execution_approved_and_all_views_preserved(self):
        validate_gold(GOLD)
        self.assertFalse(GOLD['approved_for_execution'])
        self.assertFalse(GOLD['sealed_content_opened'])
        self.assertEqual(GOLD['verified_development_members'], 116)
        self.assertEqual(sum(c['format'] == 'json' for c in GOLD['cases']), 37)
        self.assertEqual([n for n, c in CASES.items() if c['pending_decisions']], [10, 34, 47, 53, 71, 107])
        output = report(GOLD, {})
        self.assertEqual([output['views'][tier]['roster_n'] for tier in (
            'primary_direct_extraction', 'derived_inference', 'stress_adjudication')], [102, 3, 15])
        self.assertEqual(output['missing_capture_count'], 120)
        self.assertIsNone(output['sensitivity_review']['additional_correct_count'])

    def test_every_allowed_value_and_layout_passes_value_and_proof_checks(self):
        count = 0
        for case in GOLD['cases']:
            for role in case['roles']:
                for value in permitted_values(role):
                    with self.subTest(case=case['number'], value=value):
                        fields = capture(case, value)['fields']
                        result = role_result(role, fields)
                        self.assertTrue(result['value_ok'])
                        self.assertTrue(result['proof_ok'])
                        if not case['pending_decisions'] and case['tier'] != 'stress_adjudication':
                            self.assertTrue(score_case(case, {'status': 'supported', 'fields': fields})['correct'])
                        count += 1
            for layout in case['allowed_field_mappings']:
                if len(layout) != 1 or case['pending_decisions'] or case['tier'] == 'stress_adjudication':
                    continue
                self.assertTrue(score_case(case, capture(case, name=next(iter(layout))))['correct'])
        self.assertGreater(count, 200)

    def test_floor_is_small_and_preserves_real_source_distinctions(self):
        self.assertEqual(floor(' \tCafe\u0301\u00a0\r\n x '), 'Café x')
        for a, b in [('-12', '−12'), ('(12)', '12'), ('-', '—'), ('', '-'),
                     ('“word”', '"word"'), ('12', '１２'), ('A', 'a')]:
            self.assertNotEqual(floor(a), floor(b))
        for value in ('(12)', '-', '—', ''):
            case = synthetic(value)
            self.assertTrue(score_case(case, capture(case, value))['correct'])
            self.assertFalse(score_case(case, capture(case, '0'))['correct'])

    def test_numeric_types_never_pass_as_source_strings(self):
        for value in [1264, 1264.0, None, True, ['1264']]:
            item = capture(CASES[2])
            item['fields'][0]['value_text'] = value
            self.assertFalse(score_case(CASES[2], item)['correct'])
        self.assertFalse(score_case(CASES[2], capture(CASES[2], kind='number'))['correct'])
        case = synthetic('9007199254740993123456789.1234567890123456789')
        wire = json.loads(json.dumps(capture(case)))
        self.assertTrue(score_case(case, wire)['correct'])

    def test_wrong_equal_valued_table_cell_and_revision_fail(self):
        for n, wrong in [(2, '/records/6/cells/2'), (80, '/records/8/cells/1')]:
            case = CASES[n]
            item = capture(case)
            item['fields'][0]['proofs'][0]['pointer'] = wrong
            self.assertFalse(score_case(case, item)['correct'])
            item = capture(case)
            item['fields'][0]['proofs'][0]['document_sha256'] = 'f' * 64
            self.assertFalse(score_case(case, item)['correct'])
        # Stress 092 is not accuracy scored, but its candidate gross proof excludes net.
        item = capture(CASES[92])
        item['fields'][0]['proofs'][0]['pointer'] = '/records/7/cells/2'
        self.assertFalse(role_result(CASES[92]['roles'][0], item['fields'])['proof_ok'])

    def test_precise_count_and_feature_require_their_specific_evidence(self):
        for n, file, index in [(81, 't39-d2-adjudication-v1.1.json', 1),
                               (74, 't39-d1-adjudication-v1.1.json', 1)]:
            amendment = json.loads((ROOT / 'docs/reports' / file).read_text(encoding='utf-8'))
            row = next(c for c in amendment['cases'] if c['number'] == n)
            quote = row['evidence'][index]
            wrong = {'document_sha256': CASES[n]['document_sha256'],
                     'utf8_start': quote['utf8_byte_start'], 'utf8_end': quote['utf8_byte_end']}
            self.assertFalse(score_case(CASES[n], capture(CASES[n], proofs=[wrong]))['correct'])

    def test_scale_conversion_requires_scale_proof_and_never_primary_credit(self):
        case = CASES[2]; role = case['roles'][0]
        self.assertTrue(score_case(case, capture(case, '$1,264 thousand'))['correct'])
        for value in role['derived_alternatives']:
            result = score_case(case, capture(case, value))
            self.assertFalse(result['correct'])
            self.assertFalse(result['scale_conversion_correct'])
            result = score_case(case, capture(case, value, proofs=role['derived_proof_sets'][0]))
            self.assertTrue(result['scale_conversion_correct'])
            self.assertFalse(result['correct'])
        result = score_case(case, capture(case, 'about $1.26 million'))
        self.assertFalse(result['correct'])
        self.assertFalse(result['scale_conversion_correct'])
        self.assertTrue(result['roles']['opening_balance']['imprecise'])

    def test_unit_headers_do_not_leak_and_annotation_is_not_source(self):
        for n in (25, 28, 48, 49, 87, 108, 119):
            self.assertFalse(CASES[n]['roles'][0]['derived_alternatives'])
        self.assertEqual(CASES[29]['roles'][0]['scale']['stated'], 'thousand')
        self.assertEqual(CASES[29]['roles'][0]['scale']['upstream_annotation'], '')
        for n in (89, 90, 116):
            self.assertEqual(CASES[n]['roles'][0]['scale']['stated'], 'unspecified')
            self.assertFalse(CASES[n]['roles'][0]['derived_alternatives'])

    def test_tex_count_alias_only_for_its_source_case(self):
        self.assertTrue(score_case(CASES[54], capture(CASES[54], '$3,209$'))['correct'])
        self.assertTrue(score_case(CASES[54], capture(CASES[54], '3,209 reviews'))['correct'])
        self.assertFalse(score_case(CASES[54], capture(CASES[54], '$3,209'))['correct'])

    def test_tex_wrapped_currency_is_not_currency(self):
        self.assertFalse(score_case(CASES[2], capture(CASES[2], '$1,264$'))['correct'])
        self.assertFalse(score_case(synthetic('$12'), capture(synthetic('$12'), '$12$'))['correct'])

    def test_two_codes_order_separator_and_two_fields(self):
        case = CASES[43]
        for value in ('Taihō Code,Yōrō Code', 'Yōrō Code / Taihō Code',
                      'Taihō Code and Yōrō Code', 'Yōrō Code (718), Taihō Code (701)'):
            self.assertTrue(score_case(case, capture(case, value))['correct'])
        for a, b in [('Taihō Code', 'Yōrō Code'), ('Yōrō Code', 'Taihō Code')]:
            item = capture(case, a, name='first_code')
            second = deepcopy(item['fields'][0]); second.update(name='second_code', value_text=b)
            item['fields'].append(second)
            self.assertTrue(score_case(case, item)['correct'])
        for value in ('Taihō Code', 'Taihō Code, Taihō Code', 'Taihō Code, Yōrō Code, Civil Code',
                      'Either Taihō Code or Yōrō Code', 'Taihō Code; Yōrō Code'):
            self.assertFalse(score_case(case, capture(case, value))['correct'])
        partial = score_case(case, capture(case, 'Taihō Code'))
        self.assertEqual(partial['roles']['codes']['members'], {'first_code': True, 'second_code': False})
        swapped = capture(case, 'Taihō Code', name='first_code', proofs=case['roles'][0]['members'][1]['proof_sets'][0])
        swapped['fields'] += capture(case, 'Yōrō Code', name='second_code', proofs=case['roles'][0]['members'][0]['proof_sets'][0])['fields']
        self.assertFalse(score_case(case, swapped)['correct'])

    def test_qualifiers_and_stress_values_are_not_reinterpreted(self):
        for n, bad in [(81, '20,000'), (97, '2,000 m'), (72, 'sending an email')]:
            self.assertFalse(score_case(CASES[n], capture(CASES[n], bad))['correct'])
        for n in (81, 97):
            for value in CASES[n]['roles'][0]['imprecise_alternatives']:
                result = score_case(CASES[n], capture(CASES[n], value))
                self.assertFalse(result['correct'])
        self.assertEqual(CASES[64]['roles'][0]['value_string'], '0.6')
        self.assertNotIn('0.8', permitted_values(CASES[64]['roles'][0]))
        self.assertFalse(role_result(CASES[15]['roles'][0], capture(CASES[15], '30%')['fields'])['value_ok'])
        self.assertIsNone(score_case(CASES[64], capture(CASES[64]))['correct'])
        self.assertIsNone(score_case(CASES[107], capture(CASES[107]))['correct'])

    def test_format_diagnostics_never_change_score_or_sensitivity(self):
        result = score_case(CASES[2], capture(CASES[2], '1264'))
        self.assertFalse(result['correct'])
        self.assertEqual(result['roles']['opening_balance']['diagnostic'], 'format_like_nonmatch')
        self.assertEqual(result['review_queue'][0]['reason'], 'unlisted_value')
        result = score_case(CASES[2], capture(CASES[2], name='unfrozen_name'))
        self.assertFalse(result['correct'])
        self.assertEqual(result['review_queue'][0]['reason'], 'unlisted_field_mapping')

    def test_extra_fields_duplicates_rejected_drafts_and_malformed_proofs(self):
        for item in [capture(CASES[2]), capture(CASES[2])]:
            item['fields'].append(deepcopy(item['fields'][0]))
            self.assertFalse(score_case(CASES[2], item)['correct'])
        self.assertFalse(score_case(CASES[2], {'status': 'rejected', 'fields': []})['correct'])
        item = capture(CASES[2]); item['fields'][0]['proofs'] = ['unresolved']
        self.assertEqual(score_case(CASES[2], item)['outcome'], 'malformed_capture')

    def test_oracle_payload_contains_no_gold_values_or_alternatives(self):
        payload = oracle_fields(CASES[2])
        self.assertEqual(set(payload['fields'][0]), {'name', 'kind', 'required', 'locations'})
        self.assertNotIn('$1,264', json.dumps(payload))
        self.assertNotIn('Taih', json.dumps(oracle_fields(CASES[43])))
        with self.assertRaises(ValueError): oracle_fields(CASES[107])
        with self.assertRaises(ValueError): oracle_fields(CASES[64])

    def test_oracle_pair_must_keep_identical_evidence_and_format(self):
        instruction = digest(INSTRUCTION)
        audit = {k: 'f' * 64 for k in ['question_sha256', 'scorer_sha256', 'gold_sha256',
                  'model_identity_sha256', 'retrieval_settings_sha256', 'assembled_evidence_sha256']}
        audit.update(instruction_sha256=instruction, format_applied_stages=['planning', 'assessment', 'extraction'])
        self.assertEqual(verify_paired_format(audit, audit, instruction), 'field_planning_ablation')
        changed = {**audit, 'assembled_evidence_sha256': 'e' * 64}
        with self.assertRaisesRegex(ValueError, 'evidence'): verify_paired_format(audit, changed, instruction)
        self.assertIn('not_planning_cost', verify_paired_format(audit, changed, instruction, same_evidence=False))
        changed = {**audit, 'format_applied_stages': ['extraction']}
        with self.assertRaisesRegex(ValueError, 'all stages'): verify_paired_format(audit, changed, instruction)

    def test_format_adapter_preserves_original_question_and_never_coerces_plan(self):
        original = [{'role': 'system', 'content': 'existing protocol'}, {'role': 'user', 'content': 'How much?'}]
        for stage in ('planning', 'assessment', 'extraction'):
            changed, audit = messages_for_stage(original, stage)
            self.assertEqual(original[1:], changed[1:])
            self.assertEqual(original[0]['content'], 'existing protocol')
            self.assertEqual(audit['instruction_sha256'], digest(INSTRUCTION))
            with self.assertRaises(ValueError): messages_for_stage(changed, stage)
        with self.assertRaises(ValueError): require_string_fields([{'name': 'amount', 'kind': 'number'}])
        self.assertEqual(require_string_fields([{'name': 'amount', 'kind': 'string'}]), [{'name': 'amount', 'kind': 'string'}])


if __name__ == '__main__':
    unittest.main()
