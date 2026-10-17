from copy import deepcopy
import hashlib
import json
import unittest

from . import table_adapter as adapter
from . import table_grounding as scoring
from .build_table_candidate import build, load_inputs, encoded
from .test_typed_facts import capture

ANNOTATIONS, SOURCES, GOLD, READINGS = load_inputs()
DOCUMENTS, SIDECARS, PROOFS, AUDIT = build()
CASES = {c['number']: c for c in GOLD['cases']}
CASE_PROOFS = {c['number']: c for c in PROOFS['cases']}


def table(n):
    name = CASES[n]['document']
    return SOURCES[name], ANNOTATIONS[name], DOCUMENTS[name], SIDECARS[name]


def field(n, row, col):
    return table(n)[3]['contexts'][str(row)][col]


def paths(n, row, col, kind):
    return [p['text'] for p in field(n, row, col)['paths'][kind]]


def supported(n, proof_index=0):
    item = capture(CASES[n])
    proof = CASE_PROOFS[n]['proof_sets'][proof_index]
    item['fields'][0].update(value_coordinate=deepcopy(proof['value']),
                             evidence_coordinates=deepcopy(proof['required']))
    return item


class TableContextTests(unittest.TestCase):
    def test_all_sources_and_cells_preserved(self):
        self.assertEqual(len(SOURCES), 32)
        self.assertEqual(len(PROOFS['cases']), 37)
        self.assertEqual(AUDIT['summary']['cells_preserved'], 1224)
        self.assertEqual(AUDIT['summary']['annotation_rules'], 275)
        for name, raw in SOURCES.items():
            with self.subTest(table=name):
                self.assertEqual(hashlib.sha256(raw).hexdigest(), ANNOTATIONS[name]['source_sha256'])
                before = json.loads(raw)['records']; after = DOCUMENTS[name]['records']
                self.assertEqual(len(before), len(after))
                for a, b in zip(before, after):
                    if 'cells' in a:
                        self.assertEqual(a['cells'], b['cells'])
                        self.assertEqual(a['row_index'], b['row_index'])
                    else:
                        self.assertEqual(a, b)

    def test_reproduction_is_deterministic(self):
        self.assertEqual(encoded(build()), encoded((DOCUMENTS, SIDECARS, PROOFS, AUDIT)))
        for item in AUDIT['tables']:
            self.assertEqual(item['v2_sha256'], hashlib.sha256(encoded(DOCUMENTS[item['document']])).hexdigest())

    def test_hash_row_scope_and_reference_fail_closed(self):
        raw, annotation, _, _ = table(12)
        with self.assertRaises(ValueError):
            adapter.adapt(raw + b' ', annotation)
        mutations = []
        a = deepcopy(annotation); del a['row_kinds']['0']; mutations.append(a)
        a = deepcopy(annotation); a['row_kinds']['00'] = a['row_kinds'].pop('0'); mutations.append(a)
        a = deepcopy(annotation); del a['row_labels']['3']; mutations.append(a)
        a = deepcopy(annotation); a['rules'][0]['rows'] = [999]; mutations.append(a)
        a = deepcopy(annotation); a['rules'][0]['rows'] = [True]; mutations.append(a)
        a = deepcopy(annotation); a['rules'][0]['refs'] = [{'row': 0, 'col': 999}]; mutations.append(a)
        a = deepcopy(annotation); a['rules'][0]['columns'] = [999]; mutations.append(a)
        for candidate in mutations:
            with self.subTest(candidate=candidate['rules'][0]['id']):
                with self.assertRaises((ValueError, IndexError)):
                    adapter.adapt(raw, candidate)

    def test_overlapping_units_and_implicit_cross_column_spans_rejected(self):
        raw, annotation, _, _ = table(12)
        bad = deepcopy(annotation)
        duplicate = deepcopy(next(r for r in bad['rules'] if r['kind'] == 'unit'))
        duplicate['id'] = 'duplicate-unit'; bad['rules'].append(duplicate)
        with self.assertRaises(ValueError):
            adapter.adapt(raw, bad)
        bad = deepcopy(annotation)
        rule = next(r for r in bad['rules'] if r['relation'] == 'from_span' and len(r['columns']) > 1)
        rule['relation'] = 'same_column'
        with self.assertRaises(ValueError):
            adapter.adapt(raw, bad)

    def test_caption_numeric_year_headers_and_paths_are_distinct(self):
        _, annotation, document, sidecar = table(12)
        self.assertEqual(annotation['row_kinds']['0'], 'caption')
        self.assertEqual(annotation['row_kinds']['2'], 'column_header')
        self.assertIn('2.1 Office Buildings', paths(12, 3, 2, 'caption'))
        self.assertIn('2018', paths(12, 3, 2, 'column_header'))
        self.assertNotIn('2019', paths(12, 3, 2, 'column_header'))
        headers = field(12, 3, 2)['paths']['column_header']
        self.assertTrue(any(h['relation'] == 'from_span' for h in headers))
        self.assertTrue(all(set(h) == {'text', 'ref', 'relation', 'annotation_rule'} for h in headers))
        self.assertEqual(document['records'][3]['structural_context']['2']['column_header'],
                         adapter.JOIN.join(h['text'] for h in headers if h['text']))

    def test_finite_group_scopes_do_not_bleed(self):
        self.assertTrue(paths(12, 5, 1, 'group_header'))
        self.assertTrue(paths(12, 9, 1, 'group_header'))
        self.assertNotEqual(paths(12, 5, 1, 'group_header'), paths(12, 9, 1, 'group_header'))
        self.assertFalse(paths(12, 10, 1, 'group_header'))
        self.assertFalse(paths(2, 6, 1, 'group_header'))  # closing balance is data, not a heading

    def test_units_are_scoped_for_amount_rate_eps_count_and_dates(self):
        self.assertNotEqual(paths(25, 2, 1, 'unit'), paths(25, 4, 1, 'unit'))
        self.assertNotEqual(paths(48, 8, 1, 'unit'), paths(48, 11, 1, 'unit'))
        self.assertEqual(paths(80, 7, 1, 'unit'), ['$'])
        self.assertNotIn('million', ' '.join(paths(80, 7, 1, 'unit')).lower())
        self.assertEqual(field(86, 2, 1)['unit_scope'], 'unspecified')  # expiry date
        self.assertNotEqual(field(86, 2, 2)['unit_scope'], 'unspecified')
        self.assertEqual(field(114, 3, 1)['unit_scope'], 'unspecified')  # note reference
        self.assertNotEqual(field(114, 3, 2)['unit_scope'], 'unspecified')
        self.assertEqual(field(105, 5, 1)['unit_scope'], 'unspecified')  # maturity date
        self.assertNotIn('million', ' '.join(paths(105, 10, 1, 'unit')).lower())

    def test_unspecified_units_and_placeholders_not_invented(self):
        self.assertEqual(field(89, 4, 1)['unit_scope'], 'unspecified')
        self.assertEqual(field(116, 3, 1)['unit_scope'], 'unspecified')
        self.assertEqual(field(55, 2, 5)['unit_scope'], 'unspecified')
        self.assertEqual(table(55)[2]['records'][2]['cells'][5], '-')
        self.assertEqual(table(48)[2]['records'][13]['cells'][0], '')

    def test_carried_row_label_is_explicit_not_blank_heuristic(self):
        carried = field(105, 6, 1)['paths']['row_label']
        self.assertEqual(carried[0]['ref'], {'row': 5, 'col': 0})
        self.assertEqual(carried[0]['relation'], 'explicit_scope')
        self.assertIn('row_label', table(105)[2]['records'][6]['structural_context']['1'])

    def test_visible_records_never_gain_hidden_sidecar_evidence(self):
        raw, annotation, document, _ = table(12)
        original = json.loads(raw)
        v1 = adapter.visible_coordinates(raw, annotation, 3, original['records'][3], 'v1')
        v2 = adapter.visible_coordinates(raw, annotation, 3, document['records'][3], 'v2')
        year = adapter.coordinate(annotation, {'row': 2, 'col': 2})
        self.assertFalse(any(scoring.covers(year, r) for r in v1))
        self.assertTrue(any(scoring.covers(year, r) for r in v2))
        bad = deepcopy(document['records'][3]); bad['cells'][1] = 'tampered'
        with self.assertRaises(ValueError):
            adapter.visible_coordinates(raw, annotation, 3, bad, 'v2')
        with self.assertRaises(ValueError):
            adapter.visible_coordinates(raw, annotation, -1, document['records'][-1], 'v2')

    def test_rendered_context_and_out_of_bounds_are_never_values(self):
        raw, annotation, _, _ = table(12)
        self.assertEqual(adapter.value_coordinate(raw, annotation, 3, '/cells/2')['col'], 2)
        for pointer in ('/structural_context/2/column_header', '/row_index', '/cells/02', '/cells/-1'):
            with self.assertRaises(ValueError):
                adapter.value_coordinate(raw, annotation, 3, pointer)
        with self.assertRaises(IndexError):
            adapter.value_coordinate(raw, annotation, 3, '/cells/999')

    def test_all_table_proofs_are_resolvable_and_source_selected(self):
        for item in PROOFS['cases']:
            raw, annotation, _, _ = table(item['number']); source = json.loads(raw)
            for proof in item['proof_sets']:
                self.assertIn(proof['value'], proof['required'])
                for coord in proof['required']:
                    self.assertEqual(coord['table_id'], annotation['table_id'])
                    self.assertEqual(coord['source_sha256'], annotation['source_sha256'])
                    adapter.resolve(source, {k: v for k, v in coord.items() if k not in ('table_id', 'source_sha256')})

    def test_systematic_audit_and_tiers(self):
        s = AUDIT['summary']
        self.assertEqual(s['multi_header_tables'], 19)
        self.assertEqual(s['tables_with_interior_headings'], 10)
        self.assertEqual(s['duplicate_exact_value_cases'], [2, 80, 92])
        self.assertEqual(s['narrative_lead_cases'], [])
        self.assertEqual(CASE_PROOFS[2]['tier'], 'primary_direct_extraction')
        self.assertEqual(CASE_PROOFS[80]['tier'], 'primary_direct_extraction')
        self.assertEqual(CASE_PROOFS[82]['tier'], 'derived_inference')
        self.assertEqual(CASE_PROOFS[92]['tier'], 'stress_adjudication')


class GroundingTests(unittest.TestCase):
    def test_supported_value_and_coordinate_proof(self):
        for n in (2, 12, 80, 82):
            result = scoring.score_case(CASES[n], supported(n), CASE_PROOFS[n])
            self.assertTrue(result['correct'])
            self.assertTrue(result['evidence_correct'])
            self.assertTrue(result['joint_correct'])

    def test_correct_answer_wrong_cell_is_separate_axis(self):
        for n, wrong in [(2, (6, 2)), (80, (8, 1))]:
            item = supported(n)
            item['fields'][0]['value_coordinate'].update(row=wrong[0], col=wrong[1])
            result = scoring.score_case(CASES[n], item, CASE_PROOFS[n])
            self.assertTrue(result['correct'])
            self.assertFalse(result['evidence_correct'])
            self.assertFalse(result['joint_correct'])
            self.assertTrue(result['correct_answer_wrong_evidence'])

    def test_missing_period_group_or_unit_fails_grounding_only(self):
        proof = CASE_PROOFS[12]['proof_sets'][0]
        for ref in proof['required']:
            item = supported(12)
            item['fields'][0]['evidence_coordinates'] = [r for r in proof['required']
                if not scoring.covers(ref, r)]
            result = scoring.score_case(CASES[12], item, CASE_PROOFS[12])
            self.assertTrue(result['correct'])
            self.assertFalse(result['evidence_correct'])

    def test_value_and_complete_proof_recall_differ(self):
        proofs = CASE_PROOFS[12]['proof_sets']; value = proofs[0]['value']
        passages = [{'visible_coordinates': [value]}, {'visible_coordinates': proofs[0]['required']}]
        self.assertTrue(scoring.recall_at_k(proofs, passages, 1)['value_cell_retrieved'])
        self.assertFalse(scoring.recall_at_k(proofs, passages, 1)['complete_proof_retrieved'])
        self.assertTrue(scoring.recall_at_k(proofs, passages, 2)['complete_proof_retrieved'])
        with self.assertRaises(ValueError):
            scoring.recall_at_k(proofs, passages, 0)

    def test_derived_comparison_requires_competitors(self):
        item = supported(82)
        proof = CASE_PROOFS[82]['proof_sets'][0]
        item['fields'][0]['evidence_coordinates'] = [proof['value']]
        result = scoring.score_case(CASES[82], item, CASE_PROOFS[82])
        self.assertTrue(result['correct'])
        self.assertFalse(result['evidence_correct'])
        self.assertTrue(scoring.score_case(CASES[82], supported(82, 1), CASE_PROOFS[82])['evidence_correct'])

    def test_wrong_source_identity_rejected(self):
        for key in ('table_id', 'source_sha256'):
            item = supported(2); item['fields'][0]['value_coordinate'][key] = 'wrong'
            self.assertFalse(scoring.score_case(CASES[2], item, CASE_PROOFS[2])['evidence_correct'])

    def test_alternative_narrative_proof_and_utf8_range(self):
        value = {'table_id': 'table', 'source_sha256': 'a' * 64,
                 'paragraph': 7, 'utf8_start': 12, 'utf8_end': 18}
        field = {'value_coordinate': value, 'evidence_coordinates': [{**value, 'utf8_start': 0, 'utf8_end': 30}]}
        proofs = deepcopy(CASE_PROOFS[2]['proof_sets']) + [{'value': value, 'required': [value]}]
        self.assertTrue(scoring.grounded(proofs, [field]))
        field['evidence_coordinates'][0]['utf8_end'] = 17
        self.assertFalse(scoring.grounded(proofs, [field]))

    def test_stress_keeps_conditional_grounding_out_of_primary(self):
        for n in (64, 92):
            for reading in CASE_PROOFS[n]['stress_readings']:
                proof = reading['proof_sets'][0]
                item = capture(CASES[n], reading['value_string'])
                item['fields'][0].update(value_coordinate=proof['value'], evidence_coordinates=proof['required'])
                result = scoring.score_case(CASES[n], item, CASE_PROOFS[n])
                self.assertIsNone(result['correct'])
                self.assertEqual(sum(r['evidence_correct'] for r in result['conditional_grounding']), 1)
                item['status'] = 'rejected'
                self.assertFalse(any(r['value_present'] for r in scoring.score_case(
                    CASES[n], item, CASE_PROOFS[n])['conditional_grounding']))

    def test_rejected_error_and_bad_type_do_not_become_correct_values(self):
        for status in ('rejected', 'error', 'insufficient_evidence'):
            item = supported(2); item['status'] = status
            self.assertFalse(scoring.score_case(CASES[2], item, CASE_PROOFS[2])['correct'])
        item = supported(2); item['fields'][0]['type'] = 'number'
        self.assertFalse(scoring.score_case(CASES[2], item, CASE_PROOFS[2])['correct'])

    def test_missing_and_malformed_grounding_does_not_crash(self):
        for value in (None, 'fake', {}, [], [None]):
            item = supported(2); item['fields'][0]['evidence_coordinates'] = value
            result = scoring.score_case(CASES[2], item, CASE_PROOFS[2])
            self.assertTrue(result['correct'])
            self.assertFalse(result['evidence_correct'])

    def test_missing_captures_pending_gold_and_stress_denominators(self):
        result = scoring.report(GOLD, {}, PROOFS)
        self.assertEqual([v['roster_n'] for v in result['views'].values()], [102, 3, 15])
        self.assertEqual([v['scorable_n'] for v in result['views'].values()], [96, 3, 0])
        self.assertEqual(result['missing_capture_count'], 120)
        self.assertFalse(result['approved_for_execution'])


if __name__ == '__main__':
    unittest.main()
