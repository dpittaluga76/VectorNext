import copy
import json
import unittest
from experiments.t36.test_score import ScoreTests
from .score import score, PDF_SHA, AGGREGATE_ERROR
from .run import generation_times


class HybridScoreTests(unittest.TestCase):
    def test_aggregate_is_exact_api_guard_without_model_credit(self):
        label={'plan':'unsupported','error_contains':'unsupported'}
        body={'error':{'code':'invalid_request','message':AGGREGATE_ERROR}}
        self.assertTrue(score('aggregate_sum',400,json.dumps(body),label,{})['correct'])
        self.assertFalse(score('aggregate_sum',400,json.dumps(body),label,{})['planning_correct'])
        body['error']['message']+=' extra'
        self.assertFalse(score('aggregate_sum',400,json.dumps(body),label,{})['correct'])

    def test_verified_heading_correction_keeps_exact_provenance_guards(self):
        case=ScoreTests();case.setUp()
        doc=case.docs.pop('doc');case.docs['vela']=doc
        doc['original']={'sha256':PDF_SHA}
        doc['blocks']=[{'kind':'Heading','text':'Vela-X service certificate','sources':[{'revision':'r','locator':{'Pdf':{'page':1}}}]}]
        doc['chunks'][0]['spans']=[]
        evidence=case.report['evidence'][0]
        evidence['key']['document_id']='vela';evidence['spans']=[]
        evidence['text']='Vela-X service certificate\n\n'+evidence['text']
        case.gold['fields'][0]['facts'][0]['document']='vela'
        raw=json.dumps({**case.view,'raw_report':json.dumps(case.report)})
        self.assertTrue(score('pdf_pressure',200,raw,case.gold,case.docs)['correct'])
        for mutation in ('hash','page','revision','text','spans'):
            docs=copy.deepcopy(case.docs)
            if mutation=='hash': docs['vela']['original']['sha256']='wrong'
            if mutation=='page': docs['vela']['blocks'][0]['sources'][0]['locator']['Pdf']['page']=2
            if mutation=='revision': docs['vela']['revision']='other'
            if mutation=='text': docs['vela']['chunks'][0]['evidence']='Invented amount is 18.'
            if mutation=='spans': docs['vela']['chunks'][0]['spans']=[{}]
            self.assertFalse(score('pdf_pressure',200,raw,case.gold,docs)['correct'],mutation)

    def test_duplicate_audit_projection_does_not_double_generation_time(self):
        audit={'request_sha256':'x','inference_seconds':2}
        self.assertEqual(list(generation_times({'report':audit,'response_text':json.dumps(audit)})),[2])
