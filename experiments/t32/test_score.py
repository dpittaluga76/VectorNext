import copy
import json
import tempfile
import unittest
from pathlib import Path
from .run import validate
from .score import exact_load, score


class Scorer(unittest.TestCase):
    def setUp(self):
        self.key={'document_id':'d','revision':'r','chunk_id':'c'}
        self.docs={'d':{'document_id':'d','revision':'r','chunks':[{'id':'c','evidence':'count 9007199254740993'}]}}
        self.gold=exact_load('{"status":"supported","values":{"n":9007199254740993},"facts":[{"document":"d","text":"9007199254740993"}]}')
        self.report={'answer':{'status':'supported','fields':{'n':{'value':9007199254740993,'evidence_id':'E1'}}},
            'evidence':[{'id':'E1','key':self.key,'text':'count 9007199254740993'}],
            'ranked':[{'key':self.key}], 'validation':{'mechanical_support':'passed'}}

    def check(self,code=200):return score(code,json.dumps(self.report).encode(),self.gold,self.docs)

    def test_exact_integer_and_revision_citations(self):
        self.assertTrue(self.check()['correct'])
        self.report['answer']['fields']['n']['value']=9007199254740992
        self.assertFalse(self.check()['correct'])
        self.report['answer']['fields']['n']['value']=9007199254740993
        self.report['answer']['fields']['n']['evidence_id']='E2'
        self.assertFalse(self.check()['correct'])
        self.report['ranked'][0]['key']['revision']='wrong'
        with self.assertRaises(KeyError):self.check()

    def test_negative_zero_and_failed_response(self):
        self.gold={'status':'insufficient_evidence','values':{},'facts':[]}
        self.report['answer']={'status':'insufficient_evidence','fields':{}}
        self.assertTrue(self.check()['correct'])
        self.report['answer']={'status':'supported','fields':{'n':{'value':0,'evidence_id':'E1'}}}
        self.assertFalse(self.check()['correct'])
        self.assertFalse(score(0,b'',self.gold,self.docs)['correct'])

    def test_frozen_bound_and_separate_stages(self):
        self.assertEqual(len(validate()),6)
        result=self.check()
        self.assertFalse(result['coverage']['raw']['complete'])
        self.assertTrue(result['coverage']['ranked_five']['complete'])
        self.assertTrue(result['coverage']['assembled']['complete'])


if __name__=='__main__':unittest.main()
