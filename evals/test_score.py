import json
from pathlib import Path
import tempfile
import unittest
from .requests import public_request
from .score import Scorer, ancestor, exact, interval_covered, leaves
from .summarize import resources, summarize


class Scores(unittest.TestCase):
    def test_types_and_pointer_boundaries(self):
        self.assertFalse(exact(False,0)); self.assertFalse(exact(1,1.0)); self.assertFalse(exact('007',7))
        self.assertTrue(ancestor('/a~1b','/a~1b/~0x'))
        self.assertFalse(ancestor('/a','/ab'))
        self.assertEqual(leaves({'a/b':{'~x':None}},''),['/a~1b/~0x'])

    def test_span_union_requires_every_byte(self):
        self.assertTrue(interval_covered(2,9,[(6,10),(0,6)]))
        self.assertFalse(interval_covered(2,9,[(0,5),(6,10)]))

    def scorer(self,locator,expected):
        return Scorer({'documents':[{'id':'d','sha256':'source'}],'evidence':[
            {'id':'e','document_id':'d','locator':locator,'expected':expected}]},
            {'d':{'document_id':'d','revision':'r','original':{'sha256':'source'},'chunks':[],'blocks':[]}})

    def test_pdf_needs_geometry_complete_text_and_correct_revision(self):
        s=self.scorer({'kind':'pdf','page':1,'bbox':[0,0,500,30]},'J2 needs 6 N m')
        item={'key':{'document_id':'d','revision':'r'},'text':'J2 needs 6 N m','sources':[
            {'revision':'r','locator':{'Pdf':{'page':1,'bbox':[0,2,130,20]}}}]}
        self.assertTrue(s.coverage([item],['e'])['e']['covered'])
        item['text']='J2 needs 8 N m'
        score=s.coverage([item],['e'])['e']; self.assertTrue(score['location']); self.assertFalse(score['covered'])
        item['text']='J2 needs 6 N m'; item['sources'][0]['locator']['Pdf']['page']=2
        self.assertFalse(s.coverage([item],['e'])['e']['covered'])
        item['sources'][0]['locator']['Pdf']['page']=1; item['key']['revision']='stale'
        self.assertFalse(s.coverage([item],['e'])['e']['covered'])

    def test_json_collective_leaves_and_parent_sources(self):
        s=self.scorer({'kind':'json','pointer':'/records/0'},{'goals':0,'assists':None})
        def item(pointer): return {'key':{'document_id':'d','revision':'r'},'text':'{}','sources':[{'revision':'r','locator':{'Json':{'pointer':pointer}}}]}
        self.assertFalse(s.coverage([item('/records/0/goals')],['e'])['e']['covered'])
        self.assertTrue(s.coverage([item('/records/0/goals'),item('/records/0/assists')],['e'])['e']['covered'])
        self.assertTrue(s.coverage([item('/records/0')],['e'])['e']['covered'])
        self.assertFalse(s.coverage([item('/records/01')],['e'])['e']['covered'])

    def test_no_gold_outcomes_in_request_and_holdout_refused(self):
        case={'id':'q_zero','split':'dev','question':'A public question','expected':{'fields':{'goals':999}}}
        original=public_request(case)
        case['expected']={'status':'ambiguous','fields':{'anything':'hidden'},'support_sets':[['leak']]}
        self.assertEqual(public_request(case),original)
        self.assertEqual(set(original),{'question','fields'})
        case['split']='holdout'
        with self.assertRaises(ValueError): public_request(case)

    def test_complete_support_and_missing_evidence_denominators(self):
        s=self.scorer({'kind':'text','byte_start':0,'byte_end':6},'abcdef')
        def item(a,b): return {'key':{'document_id':'d','revision':'r'},'text':'abcdef'[a:b],
            'sources':[{'revision':'r','locator':{'Text':{'bytes':{'start':a,'end':b}}}}]}
        self.assertEqual(s.stage([item(0,3),item(3,6)],[['e']])['first_complete_rank'],2)
        self.assertEqual(s.stage([item(0,3)],[['e']])['recall'],0)
        self.assertIsNone(s.stage([],[])['recall'])

    def test_http_failure_stays_in_accuracy_and_recall_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'queries-progress.json').write_text(json.dumps([
                {'case':'q_zero','cache':'cold-cache','http_status':503,'wall_seconds':1,'score':None}]),encoding='utf-8')
            result=summarize(root)['passes']['cold-cache']
            self.assertEqual((result['n'],result['http_success'],result['fields_total']), (1,0,1))
            self.assertEqual(result['status_confusion'],{'supported -> http_error':1})
            self.assertEqual(result['stages']['context']['supported_n'],1)
            self.assertEqual(result['stages']['context']['mean_recall'],0)

    def test_missing_memory_samples_are_not_zero_peaks(self):
        result=resources([{'monotonic_ns':0,'llm':{'error':'stopped'}}])
        self.assertIsNone(result['device_mib_max'])
        self.assertIsNone(result['llm']['current_bytes'])
        self.assertEqual(result['llm']['samples'],0)

    def test_only_source_backed_labels_restore_table_header_coverage(self):
        s=self.scorer({'kind':'pdf','page':1,'bbox':[0,0,100,20]},'Flow (L/min)')
        key={'document_id':'d','revision':'r','chunk_id':'c'}
        source={'revision':'r','locator':{'Pdf':{'page':1,'bbox':[0,0,100,20]}}}
        context={'value':'Flow (L/min)','derivation':{'Deterministic':{'version':'fixture'}},'sources':[source]}
        s.chunks[('d','r','c')]={'evidence':'H2 | 12','sources':[],'spans':[], 'attributes':{'pdf_context':context}}
        self.assertFalse(s.coverage([s.chunk_item(key)],['e'])['e']['covered'])
        self.assertTrue(s.coverage([s.source_label_item(key)],['e'])['e']['covered'])
        context['derivation']={'Generated':{}}
        self.assertFalse(s.coverage([s.source_label_item(key)],['e'])['e']['covered'])


if __name__=='__main__': unittest.main()
