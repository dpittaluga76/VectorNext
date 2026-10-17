import json
from pathlib import Path
import tempfile
import unittest

from evals.measurement.capture_grounding import prose_coordinates
from evals.measurement.families import digest
from evals.measurement.internal_supplement import conservative_support, error_kind, oracle_reason
from evals.measurement.test_capture_grounding import prose


class SupplementTests(unittest.TestCase):
    def test_unaligned_repeat_is_unknown_not_a_retrieval_miss(self):
        document, evidence = prose('Count 23.')
        source = 'Count 23. Count 23.'
        observation = prose_coordinates(source, digest(source.encode()), 'a'*64,
                                        evidence, document, 'd', 'r')
        self.assertFalse(observation['proofs'])
        self.assertIsNone(conservative_support(False, len(observation['alignment_gaps'])))

    def test_complete_proof_survives_other_unaligned_spans(self):
        self.assertIs(conservative_support(True, 1), True)
        self.assertIs(conservative_support(False, 0), False)
        self.assertIsNone(conservative_support(None, 0))

    def test_known_contract_refusal_is_not_reported_as_infrastructure(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)
            (path/'finished.json').write_text(json.dumps({'state':'captured'}))
            job = {'result':{'error':{'message':'Benchmark plan does not satisfy the frozen string-field instruction'}}}
            self.assertEqual(error_kind(path,job), 'benchmark_string_plan_contract')
            self.assertEqual(error_kind(path,{'error':'connection lost'}), 'other_or_unobserved_error')

    def test_submission_guard_and_ingestion_failure_remain_distinct(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)
            (path/'finished.json').write_text(json.dumps({'state':'submission_failed'}))
            (path/'submission.raw.json').write_text(json.dumps({'error':{'message':'unsupported corpus aggregation'}}))
            self.assertEqual(error_kind(path,{}), 'pre_inference_aggregation_guard')
            (path/'finished.json').write_text(json.dumps({'state':'ingestion_failed'}))
            self.assertEqual(error_kind(path,{}), 'ingestion_admission_failure')

    def test_public_error_groups_do_not_emit_private_wire_metadata(self):
        value = {'reason':'answer generation did not finish normally; request_sha256=private-hash'}
        self.assertEqual(oracle_reason(value), 'generation_did_not_finish_normally')
        self.assertEqual(oracle_reason({'reason':'private candidate detail'}),
                         'other_failure_private_detail_retained')


if __name__=='__main__':unittest.main()
