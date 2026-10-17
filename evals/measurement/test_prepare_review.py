import unittest
from .prepare_review import proposals,select


class ProposalTests(unittest.TestCase):
    def test_source_questions_and_answers_are_preserved_and_spans_checked(self):
        sources={'squad-dev.json':{'data':[{'title':'Synthetic source','paragraphs':[{
            'context':'Count is eight.','qas':[{'id':'q','question':'What is the count?',
            'is_impossible':False,'answers':[{'answer_start':9,'text':'eight'}]}]}]}]},
            'qasper-dev.json':{},'tatqa-dev.json':[]}
        row=proposals(sources)[0]
        self.assertEqual(row['question'],'What is the count?')
        self.assertEqual(row['alternatives'],['eight'])
        sources['squad-dev.json']['data'][0]['paragraphs'][0]['qas'][0]['answers'][0]['answer_start']=0
        with self.assertRaisesRegex(ValueError,'span mismatch'): proposals(sources)

    def test_disagreement_and_arithmetic_are_not_silently_labelled_supported(self):
        sources={'squad-dev.json':{'data':[]},'tatqa-dev.json':[{
            'table':{'uid':'t','table':[['count'],['8']]},'paragraphs':[],
            'questions':[{'uid':'q','question':'How many?','answer_type':'arithmetic',
                'answer_from':'table','req_comparison':False,'answer':['8'],'scale':''}]}],
            'qasper-dev.json':{'paper':{'title':'Title','abstract':'Eight.', 'full_text':[], 'figures_and_tables':[],
                'qas':[{'question_id':'q','question':'How many?','answers':[
                    {'answer':{'unanswerable':True,'extractive_spans':[],'evidence':[]}},
                    {'answer':{'unanswerable':False,'extractive_spans':['Eight'],'evidence':['Eight.']}}]}]}}}
        self.assertEqual(proposals(sources),[])

    def test_selection_is_family_disjoint_and_keeps_negative_quota(self):
        rows=[]
        for source in ('squad','qasper','tatqa'):
            for outcome in ('supported','insufficient_evidence'):
                for i in range(100):
                    rows.append({'id':f'{source}-{outcome}-{i}','source':source,'expected':outcome,
                        'family':f'{source}:{i}','document_id':f'{source}-{i}',
                        'format':'json' if source=='tatqa' else 'txt','transformation':'synthetic fixture'})
        selected=select(rows)
        self.assertEqual(selected,select(list(reversed(rows))))
        self.assertEqual(len(selected),180)
        self.assertEqual(sum(r['expected']!='supported' for r in selected),50)
        dev={r['family'] for r in selected if r['split']=='development'}
        sealed={r['family'] for r in selected if r['split']=='sealed'}
        self.assertFalse(dev&sealed)
        self.assertGreaterEqual(len(sealed),20)
