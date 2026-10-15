"""Independent small checks; never create or rewrite a measured corpus."""
import unittest
import numpy as np
from .run import reference, score, eligible, vector_literal, row_index, key

class BenchmarkTests(unittest.TestCase):
    def test_oracle_matches_hand_computed_cosines(self):
        vectors=np.array([[1,0],[0,1],[-1,0],[3,4]],dtype=np.float32)
        result=reference(vectors,[1,0],'all',400)
        self.assertEqual([h['id'] for h in result['hits']],['d00000/c00','d00000/c03','d00000/c01','d00000/c02'])
        self.assertEqual([h['score'] for h in result['hits']],[1,.6,0,-1])
    def test_float32_literals_preserve_every_coordinate(self):
        rng=np.random.default_rng(43)
        values=rng.normal(size=384).astype(np.float32)
        values[:3]=[np.finfo(np.float32).tiny,np.finfo(np.float32).max,-0.0]
        recovered=np.fromstring(vector_literal(values)[1:-1],sep=',',dtype=np.float32)
        self.assertEqual(values.tobytes(),recovered.tobytes())
    def test_filters_have_fixed_selectivity_and_exclude_sentinel(self):
        for count in (400,1600):
            self.assertEqual(sum(eligible(i,'scope5',count) for i in range(count*32)),count*32//20)
            self.assertEqual(sum(eligible(i,'attribute1',count) for i in range(count*32)),count*32//100)
            self.assertFalse(eligible(count*32,'attribute1',count))
            self.assertFalse(eligible(0,'empty',count))
    def test_ties_allow_alternative_boundary_ids_but_report_strict_recall(self):
        vectors=np.tile([1.,0.],(12,1)).astype(np.float32)
        expected=reference(vectors,[1,0],'all',400)
        hits=[{'id':key(i,400),'score':1.} for i in range(2,12)]
        result=score(hits,expected,[1,0],vectors,'all',400)
        self.assertTrue(result['correct'])
        self.assertEqual(result['recall10'],.8)
    def test_short_duplicate_wrong_score_and_ineligible_results_fail(self):
        vectors=np.tile([1.,0.],(32,1)).astype(np.float32)
        expected=reference(vectors,[1,0],'all',400)
        hits=expected['hits']
        for invalid in [hits[:-1],hits[:-1]+[hits[0]],[{**h,'score':.2} for h in hits],hits[:-1]+[{'id':'d99999/c00','score':1}]]:
            self.assertFalse(score(invalid,expected,[1,0],vectors,'all',400)['correct'])
    def test_boundary_ties_do_not_allow_omitting_a_strictly_better_hit(self):
        vectors=np.tile([0.,1.],(12,1)).astype(np.float32)
        vectors[0]=[1,0]
        expected=reference(vectors,[1,0],'all',400)
        hits=[{'id':key(i,400),'score':0.} for i in range(1,11)]
        self.assertFalse(score(hits,expected,[1,0],vectors,'all',400)['correct'])
        reversed_hits=list(reversed(expected['hits']))
        self.assertFalse(score(reversed_hits,expected,[1,0],vectors,'all',400)['correct'])
    def test_empty_failure_is_not_a_success_and_errors_score_zero(self):
        vectors=np.array([[1.,0.]],dtype=np.float32)
        empty=reference(vectors,[1,0],'empty',400)
        self.assertTrue(score([],empty,[1,0],vectors,'empty',400)['correct'])
        self.assertFalse(score([],empty,[1,0],vectors,'empty',400,error='offline')['correct'])
        nonempty=reference(vectors,[1,0],'all',400)
        self.assertEqual(score([],nonempty,[1,0],vectors,'all',400,error='offline')['recall10'],0)
    def test_ids_round_trip_with_post_checkpoint_sentinel(self):
        for index in [0,31,32,12799,12800,12831]:
            self.assertEqual(row_index(key(index,400),400),index)

if __name__=='__main__': unittest.main()
