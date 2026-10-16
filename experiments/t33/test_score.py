import copy
import json
import unittest
from .score import case_score, pdf_exception


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.docs={'doc':{'document_id':'doc','revision':'r','chunks':[{'id':'c','evidence':'There are 12 piers.'}]}}
        self.report={'request':{'fields':{'piers':{'kind':'integer'}}},
            'answer':{'status':'supported','fields':{'piers':{'value':12,'evidence_id':'E1'}}},
            'evidence':[{'id':'E1','key':{'document_id':'doc','revision':'r','chunk_id':'c'},'text':'There are 12 piers.'}],
            'validation':{'mechanical_support':'passed'},'planning':{'plan':{'status':'ready'}}}
        self.gold={'status':'supported','value':12,'kind':'integer','facts':[{'document':'doc','text':'12 piers'}]}

    def view(self):
        return {'outcome':'supported','fields':[{'name':'piers','kind':'integer','value_text':'12'}],
                'raw_report':json.dumps(self.report)}

    def score(self,view,code=200):
        return case_score(code,json.dumps(view).encode(),self.gold,self.docs,True)['correct']

    def test_browser_requires_plan_value_type_and_exact_projection(self):
        self.assertTrue(self.score(self.view()))
        for mutate in ('projection','type','plan','extra','missing_citation'):
            report=copy.deepcopy(self.report);view=self.view()
            if mutate=='projection':view['fields'][0]['value_text']='13'
            if mutate=='type':report['request']['fields']['piers']['kind']='number'
            if mutate=='plan':report['planning']['plan']['status']='declined'
            if mutate=='extra':report['answer']['fields']['extra']={'value':12,'evidence_id':'E1'}
            if mutate=='missing_citation':report['answer']['fields']['piers']['evidence_id']='E2'
            view['raw_report']=json.dumps(report)
            self.assertFalse(self.score(view),mutate)
        self.assertFalse(self.score(self.view(),503))

    def test_exact_large_integer_and_boolean_are_distinct(self):
        label={'status':'supported','values':{'piers':9007199254740993},'facts':[]}
        for value,correct in [(9007199254740993,True),(9007199254740992,False),(True,False)]:
            report=copy.deepcopy(self.report);report['answer']['fields']['piers']['value']=value
            self.assertEqual(case_score(200,json.dumps(report).encode(),label,self.docs)['correct'],correct)

    def test_number_scale_keeps_exact_report_projection(self):
        self.gold['kind']='number'
        self.report['request']['fields']['piers']['kind']='number'
        self.report['answer']['fields']['piers']['value']=12.0
        view=self.view();view['fields'][0].update(kind='number',value_text='12.0')
        self.assertTrue(self.score(view))
        view['fields'][0]['value_text']='12'
        self.assertFalse(self.score(view))

    def test_blocked_and_negative_errors_never_count_as_success(self):
        label={'status':'insufficient_evidence','values':{},'facts':[]}
        self.assertFalse(case_score(0,b'',label,self.docs)['correct'])
        self.assertFalse(pdf_exception(200,b'{}',self.docs))


if __name__=='__main__':unittest.main()
