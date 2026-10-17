import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from .families import encoded, load, save
from .internal_evaluate import range_covered, rpc_attempt, select_evidence, submit
from .internal_results import original_correct, cluster_interval
from .test_capture_projection import fixture


class InternalExecutionTests(unittest.TestCase):
    def test_uncertain_direct_call_is_not_replayed(self):
        with TemporaryDirectory() as folder:
            dest=Path(folder)/'attempt';dest.mkdir();save(dest/'started.json',{'attempted':True})
            with patch('evals.measurement.internal_evaluate.wire') as wire:
                result=rpc_attempt(dest,'nuextract','closed_book',{'question':'Q'})
            self.assertEqual(result['state'],'interrupted_uncertain');wire.assert_not_called()

    def test_rpc_keeps_request_bytes_and_one_failed_attempt(self):
        with TemporaryDirectory() as folder:
            dest=Path(folder)/'attempt';calls=[]
            def wire(url,path,raw,timeout):
                self.assertNotIn(b'\n',raw)
                request=json.loads(raw);calls.append(path)
                if path=='/generation/acquire':return 200,encoded(request)
                if path=='/generation/release':return 200,b'{}'
                return 500,b'{"error":"backend failed"}'
            with patch('evals.measurement.internal_evaluate.wire',side_effect=wire):
                a=rpc_attempt(dest,'nuextract','closed_book',{'question':'Original Q'})
                b=rpc_attempt(dest,'nuextract','closed_book',{'question':'Original Q'})
            self.assertEqual(a,b);self.assertEqual(calls.count('/rpc/interactive'),1)
            self.assertEqual(load(dest/'closed_book.request.json')['input'],{'question':'Original Q'})
            self.assertEqual(load(dest/'acquire.request.json')['priority'],'interactive')

    def test_oracle_budget_failure_never_generates(self):
        with TemporaryDirectory() as folder:
            calls=[]
            def wire(url,path,raw,timeout):
                request=json.loads(raw);calls.append(request.get('op'))
                if path=='/generation/acquire':return 200,encoded(request)
                if path=='/generation/release':return 200,b'{}'
                return 200,b'{"result":3329}'
            with patch('evals.measurement.internal_evaluate.wire',side_effect=wire):
                result=rpc_attempt(Path(folder)/'attempt','gemma','answer',{'question':'Q'})
            self.assertEqual(result['state'],'failed');self.assertNotIn('answer',calls)

    def test_range_coverage_requires_no_gap_and_matching_source(self):
        need={'document_sha256':'a','utf8_start':3,'utf8_end':12}
        refs=[{'document_sha256':'a','utf8_start':0,'utf8_end':7},
              {'document_sha256':'a','utf8_start':7,'utf8_end':15}]
        self.assertTrue(range_covered(need,refs))
        refs[1]['utf8_start']=8;self.assertFalse(range_covered(need,refs))
        refs[1]['utf8_start']=7;refs[1]['document_sha256']='b';self.assertFalse(range_covered(need,refs))

    def test_oracle_selection_is_source_only_and_minimal(self):
        need={'document_sha256':'a','utf8_start':3,'utf8_end':12}
        case={'tier':'primary_direct_extraction','expected':'supported','format':'txt',
              'roles':[{'proof_sets':[[need]]}]}
        refs=[[{'document_sha256':'a','utf8_start':0,'utf8_end':7}],
              [{'document_sha256':'a','utf8_start':7,'utf8_end':15}],
              [{'document_sha256':'a','utf8_start':0,'utf8_end':15}]]
        selected,reason=select_evidence(case,['a','b','c'],refs,{})
        self.assertEqual(selected,['c']);self.assertIsNone(reason)
        case['expected']='insufficient_evidence'
        self.assertEqual(select_evidence(case,['a','b','c'],refs,{})[0],['a','b','c'])
        case['tier']='stress_adjudication';self.assertIsNone(select_evidence(case,[],[],{})[0])

    def test_original_label_view_does_not_accept_containment_or_numeric_coercion(self):
        case={'original_expected':'supported','original_alternatives':['22,880']}
        capture={'status':'supported','fields':[{'type':'string','value_text':'22,880'}]}
        self.assertTrue(original_correct(case,capture))
        capture['fields'][0]['value_text']='22,880 or 20,000';self.assertFalse(original_correct(case,capture))
        capture['fields'][0]={'type':'integer','value_text':'22,880'};self.assertFalse(original_correct(case,capture))

    def test_family_interval_keeps_cluster_sizes(self):
        result=cluster_interval([{'family':'a','correct':True},{'family':'a','correct':False},
                                 {'family':'b','correct':True}])
        self.assertEqual(result['families'],2);self.assertEqual(result['cluster_sizes'],{2:1,1:1})

    def test_durable_job_lost_submission_reconciles_without_second_post(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);save(root/'execution-freeze.json',{'test':True})
            job,ctx=fixture();case={'case_id':'synthetic','question':'How many?','document':'d'}
            calls=[]
            def wire(url,path,raw=None,timeout=30):
                calls.append(path)
                if path=='/v1/answer-jobs':raise TimeoutError('lost response')
                if path.endswith('/clear'):
                    self.assertTrue((root/'answers/development/v2/five/synthetic/finished.json').exists())
                    self.assertTrue((root/'answers/development/v2/five/synthetic/job.json').exists())
                    return 200,b'{}'
                job['request_id']=path.rsplit('/',1)[1]
                return 200,encoded(job)
            with patch('evals.measurement.internal_evaluate.verified',return_value=({},root)),\
                 patch('evals.measurement.internal_evaluate.context',return_value=ctx),\
                 patch('evals.measurement.internal_evaluate.wire',side_effect=wire):
                self.assertEqual(submit(root,case,'development','five')['state'],'captured')
                self.assertEqual(submit(root,case,'development','five')['state'],'captured')
            self.assertEqual(calls.count('/v1/answer-jobs'),1)


if __name__=='__main__':unittest.main()
