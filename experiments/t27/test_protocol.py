import copy
import unittest
from .run import SUITES, validate_inputs
from .summarize import compare


class ProtocolTests(unittest.TestCase):
    def test_frozen_inputs_and_denominator(self):
        validate_inputs()
        self.assertEqual(sum((16 if name == 't14' else 28)*len(spec[2])*2 for name, spec in SUITES.items()), 416)

    def row(self, identifier='a', correct=True, seconds=10, status='supported', expected='supported', proof=True):
        return {'case': identifier, 'wall_seconds': seconds, 'http_status': 200,
                'score': {'answer_correct': correct, 'actual_status': status, 'expected_status': expected,
                          'proofs': {'value': {'gold_source_overlap': proof}} if status == 'supported' else {}}}

    def test_case_and_source_losses_are_not_hidden_by_totals(self):
        old = [self.row('a'), self.row('b', correct=False)]
        new = [self.row('a', correct=False), self.row('b')]
        result = compare(old, new)
        self.assertEqual(result['correctness_regressions'], ['a'])
        candidate = [self.row(proof=False)]
        self.assertEqual(compare([self.row()], candidate)['source_support_losses'], [{'case': 'a', 'field': 'value'}])

    def test_fast_errors_cannot_improve_common_success_timing(self):
        old = [self.row('a', seconds=10), self.row('b', seconds=100), self.row('c', seconds=100)]
        new = copy.deepcopy(old)
        for row in new[1:]:
            row.update(http_status=400, wall_seconds=.01, score=None)
        result = compare(old, new)
        self.assertGreater(result['median_reduction'], .9)
        self.assertEqual(result['common_median_reduction'], 0)
        self.assertEqual(result['common_success_count'], 1)

    def test_negative_outcomes_and_missing_times(self):
        old = [self.row(status='ambiguous', expected='ambiguous')]
        new = [self.row(correct=False, expected='ambiguous', seconds=None)]
        result = compare(old, new)
        self.assertEqual(result['new_false_support'], ['a'])
        self.assertEqual(result['candidate']['missing_timings'], 1)
        self.assertIsNone(result['common_median_reduction'])
        with self.assertRaises(ValueError):
            compare(old, [])


if __name__ == '__main__':
    unittest.main()
