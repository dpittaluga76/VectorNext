import copy
import json
import unittest
from decimal import Decimal
from .score import score, match_fields, typed_equal


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'name':'berths','kind':'integer','nullable':False,'description':'Reported berth count'}
        self.docs = {'doc':{'revision':'r','chunks':[{'id':'c','evidence':'The berth count is 18.'}]}}
        self.report = {'request':{'fields':{'berths':{k:v for k,v in self.spec.items() if k!='name'}}},
            'planning':{'plan':{'status':'ready','fields':[self.spec]}},
            'answer':{'status':'supported','fields':{'berths':{'value':18,'evidence_id':'E1'}}},
            'evidence':[{'id':'E1','key':{'document_id':'doc','revision':'r','chunk_id':'c'},'text':'The berth count is 18.'}],
            'validation':{'mechanical_support':'passed'}}
        self.view = {'outcome':'supported','fields':[{'name':'berths','kind':'integer','value_text':'18'}]}
        self.gold = {'plan':'ready','outcome':'supported','fields':[{'kind':'integer','nullable':False,'value':18,
                        'meaning':'berth','facts':[{'document':'doc','text':'berth count is 18'}]}]}

    def evaluate(self, code=200):
        view = dict(self.view, raw_report=json.dumps(self.report))
        return score(code,json.dumps(view).encode(),self.gold,self.docs)

    def test_positive_requires_cardinality_types_nullability_and_meaning(self):
        self.assertTrue(self.evaluate()['correct'])
        for mutation in ('extra','missing','kind','nullable','meaning','request_kind'):
            with self.subTest(mutation=mutation):
                self.setUp()
                fields = self.report['planning']['plan']['fields']
                if mutation == 'extra': fields.append(dict(self.spec,name='year'))
                if mutation == 'missing': fields.clear()
                if mutation == 'kind': fields[0]['kind']='number'
                if mutation == 'nullable': fields[0]['nullable']=True
                if mutation == 'meaning': fields[0].update(name='piers',description='Reported pier count')
                if mutation == 'request_kind': self.report['request']['fields']['berths']['kind']='number'
                self.assertFalse(self.evaluate()['correct'])

    def test_multi_field_bijection_preserves_explicit_year_and_name(self):
        expected = [{'kind':'string','meaning':'name'},{'kind':'integer','meaning':'year'},{'kind':'integer','meaning':'berth'}]
        fields = [dict(self.spec),dict(self.spec,name='year',description='Inspection year'),
                  dict(self.spec,name='depot_name',kind='string',description='Depot name')]
        self.assertEqual(match_fields({'status':'ready','fields':fields},expected),['depot_name','year','berths'])
        fields[0]['name']='year'
        self.assertIsNone(match_fields({'status':'ready','fields':fields},expected))

    def test_exact_values_and_ui_projection(self):
        for value, text, expected in [(18,'18',True),(17,'17',False),(True,'true',False),(18,'18.0',False)]:
            self.report['answer']['fields']['berths']['value']=value
            self.view['fields'][0]['value_text']=text
            self.assertEqual(self.evaluate()['correct'],expected)
        self.gold['fields'][0].update(value=9007199254741237,facts=[])
        self.report['answer']['fields']['berths']['value']=9007199254741237
        self.view['fields'][0]['value_text']='9007199254741237'
        self.assertTrue(self.evaluate()['correct'])
        self.view['fields'][0]['value_text']='9007199254741236'
        self.assertFalse(self.evaluate()['correct'])
        self.assertTrue(typed_equal(Decimal('6.25'),Decimal('6.25'),'number'))
        self.assertFalse(typed_equal(True,1,'number'))
        self.assertFalse(typed_equal(Decimal('18'),18,'integer'))

    def test_source_revision_chunk_text_and_mechanical_validation(self):
        for mutation in ('revision','chunk','text','proof','validation'):
            self.setUp()
            e = self.report['evidence'][0]
            if mutation == 'revision': e['key']['revision']='old'
            if mutation == 'chunk': e['key']['chunk_id']='missing'
            if mutation == 'text': e['text']='Invented berth count is 18.'
            if mutation == 'proof': self.report['answer']['fields']['berths']['evidence_id']='missing'
            if mutation == 'validation': self.report['validation']['mechanical_support']='failed'
            self.assertFalse(self.evaluate()['correct'],mutation)

    def test_unknown_does_not_become_zero_or_supported_null(self):
        self.gold.update(outcome='insufficient_evidence')
        self.report['answer']={'status':'insufficient_evidence','fields':{}}
        self.view.update(outcome='insufficient_evidence',fields=[])
        self.assertTrue(self.evaluate()['correct'])
        for value in (0,None):
            self.report['answer']['fields']={'berths':{'value':value,'evidence_id':'E1'}}
            self.assertFalse(self.evaluate()['correct'])

    def test_declines_require_the_expected_reason_and_code(self):
        label={'plan':'needs_clarification','error_contains':'question needs clarification:'}
        raw=json.dumps({'error':{'code':'invalid_request','message':'question needs clarification: name a subject'}}).encode()
        self.assertTrue(score(400,raw,label,self.docs)['correct'])
        wrapped=json.dumps({'error':{'code':'invalid_request','message':'invalid record: question needs clarification: name a subject'}}).encode()
        self.assertTrue(score(400,wrapped,label,self.docs)['correct'])
        for code, body in ((503,raw),(0,b''),(400,b'{"error":{"message":"bad plan"}}'),(400,b'{}')):
            self.assertFalse(score(code,body,label,self.docs)['correct'])
        self.assertFalse(score(400,raw,dict(label,error_contains='automatic planning does not support'),self.docs)['correct'])

    def test_malformed_missing_and_transport_failures_are_not_successes(self):
        for code, raw in ((200,b'{}'),(200,b'not-json'),(503,b'{}'),(0,b'')):
            self.assertFalse(score(code,raw,self.gold,self.docs)['correct'])


if __name__ == '__main__': unittest.main()
