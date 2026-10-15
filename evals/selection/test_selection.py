import copy
import unittest
from .score import check_comparison


class ComparisonTests(unittest.TestCase):
    def record(self):
        key={'document_id':'a','revision':'r1','chunk_id':'1'}
        return {'id':'q','arm':'ranked','status':'ok','raw':[key],'selected':[key],'primary':[key],
                'rerank':{'scores':[1.]},'facet_audit':[],'selection':{'strategy':'ranked'}}

    def test_identical_shortlists_and_repeats(self):
        a=self.record();b=copy.deepcopy(a);b['arm']='facets';b['selection']={'strategy':'facets'}
        counts=check_comparison([('a',[a]),('b',[b]),('b2',[b]),('a2',[a])])
        self.assertEqual(counts,{'shortlist_matches':3,'repeat_matches':2,'unavailable':[]})

    def test_changed_shortlist_or_general_scores_fail(self):
        for change in ('selected','rerank'):
            a=self.record();b=copy.deepcopy(a)
            if change=='selected':b['selected'][0]['revision']='other';b['primary']=copy.deepcopy(b['selected'])
            else:b['rerank']['scores']=[2.]
            with self.assertRaises(AssertionError):check_comparison([('a',[a]),('b',[b])])

    def test_outside_primary_and_duplicates_fail(self):
        for bad in ('outside','duplicate'):
            a=self.record()
            if bad=='outside':a['primary'][0]=dict(a['primary'][0],chunk_id='2')
            else:a['primary']*=2
            with self.assertRaises(AssertionError):check_comparison([('a',[a])])

    def test_failed_requests_are_reported_not_compared(self):
        counts=check_comparison([('a',[{'id':'q','status':'error','arm':'ranked'}])])
        self.assertEqual(counts['unavailable'],[['a','q']])


if __name__=='__main__':unittest.main()
