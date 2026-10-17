import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from .metrics import aggregate, exact_load, latency, outcome, wilson
from .rescore import Reader, normalize_record


class MeasurementTests(unittest.TestCase):
    def test_intervals_and_cluster_guard(self):
        self.assertIsNone(wilson(0,0))
        lo, hi = wilson(8,16)
        self.assertAlmostEqual(lo, .2799956, places=6)
        self.assertAlmostEqual(hi, .7200044, places=6)
        self.assertLess(wilson(0,16)[1], .2)
        row = {'case':'one','outcome':'answered_correct','latency':{'wall_ms':None}}
        with self.assertRaisesRegex(ValueError, 'duplicate'): aggregate([row,row])

    def test_distinct_outcomes_and_errors(self):
        self.assertEqual(outcome('supported','supported',True), 'answered_correct')
        self.assertEqual(outcome('insufficient_evidence','supported',False), 'answered_wrong')
        self.assertEqual(outcome('ambiguous','insufficient_evidence',False), 'abstained_wrong')
        self.assertEqual(outcome('supported',None,False,error=True), 'system_error')
        self.assertEqual(outcome('supported',None,False,error=True,rejected=True), 'abstained_missed')
        self.assertEqual(outcome('insufficient_evidence','insufficient_evidence',True), 'abstained_correct')

    def test_exact_rejected_draft_is_only_diagnostic_and_hashes_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'capture.json'
            raw='{"error":{"code":"answer_rejected","diagnostics":{"unvalidated_draft":{"fields":{"n":{"value":9007199254740993.00000000000001}}}}}}'
            path.write_text(raw)
            reader=Reader(root)
            label={'expected':{'status':'supported','fields':{'n':Decimal('9007199254740993.00000000000001')}}}
            row=normalize_record(reader,'group','case',path,{'http_status':400},label,lambda *args:{'correct':False})
            self.assertTrue(row['rejected_gold_values'])
            self.assertEqual(row['validator_false_reject'],'not_adjudicated')
            self.assertEqual(row['outcome'],'abstained_missed')
            reader.verify()
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'changed'):reader.verify()

    def test_unknown_and_failed_latency_not_zero_or_double_counted(self):
        report={'audit':{'schema_validation':'passed','elapsed_seconds':3,'input_tokens':10,
                        'assessment_audit':{'elapsed_seconds':2,'inference_seconds':1.5}},
                'timings_ms':{'answer_model_calls':5100}}
        measured=latency(report,7)
        self.assertEqual(len(measured['final']['calls']),2)
        self.assertIsNone(measured['final']['calls'][0]['input_tokens'])
        self.assertEqual(measured['final']['stages_ms']['answer_model_calls'],5100)
        call={'stage':'extraction','state':'failed','elapsed_ms':900,'stages_ms':{'inference':800},'input_tokens':10,'output_tokens':None}
        job={'attempts':[{'model':'nuextract','response_text':json.dumps(report),'identity':None,'activation_ms':0,
                         'operations':[{'operation':'answer','model_measurement':{'version':1,'calls':[call]}}]}]}
        measured=latency(report,job=job)
        self.assertEqual(measured['attempts'][0]['calls'],[call])
        self.assertIsNone(measured['attempts'][0]['activation_ms'])

    def test_missing_and_malformed_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reader=Reader(root); path=root/'missing.json'
            row=normalize_record(reader,'g','c',path,{}, {'status':'supported'},lambda *a:None)
            self.assertEqual(row['outcome'],'unscorable')
            path.write_text('not JSON')
            row=normalize_record(reader,'g','c',path,{'http_status':200}, {'status':'supported'},lambda *a:None)
            self.assertIn('JSONDecodeError',row['unscorable_reason'])
        self.assertNotEqual(exact_load('9007199254740993.00000000000001'), Decimal('9007199254740993'))


if __name__ == '__main__': unittest.main()
