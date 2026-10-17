import unittest
from .gate import paired, upper_wilson, REQUIRED_SEALED


class GateTests(unittest.TestCase):
    def rows(self,n=60):
        return [{'case_id':str(i),'family':str(i//3),'split':'sealed','arms':{
            'five':{'correct':True,'harmful':False,'wall_ms':100},
            'two':{'correct':True,'harmful':False,'wall_ms':50}}} for i in range(n)]

    def test_perfect_small_pilot_is_not_equivalence(self):
        result=paired(self.rows(),'two',resamples=1000)
        self.assertEqual(REQUIRED_SEALED,520)
        self.assertEqual(result['decision'],'retain_ranked_five')
        self.assertEqual(result['interpretation'],'inconclusive_underpowered')
        self.assertAlmostEqual(upper_wilson(0,60),.043147,places=5)

    def test_failures_stay_in_pairs_and_unknown_latency_never_helps(self):
        rows=self.rows()
        rows[0]['arms']['two']={'correct':False,'harmful':True,'wall_ms':1}
        rows[1]['arms'].pop('two')
        rows[2]['arms']['two']['wall_ms']=None
        result=paired(rows,'two',resamples=1000)
        self.assertEqual(result['questions'],60)
        self.assertEqual(result['missing_arms'],1)
        self.assertAlmostEqual(result['primary_difference'],-2/60)
        self.assertFalse(result['checks']['latency_all'])
        self.assertFalse(result['checks']['latency_paired_success'])

    def test_family_pairing_deterministic_and_duplicates_refused(self):
        rows=self.rows()
        for r in rows[:3]: r['arms']['two']['correct']=False
        a=paired(rows,'two',resamples=1000)
        self.assertEqual(a,paired(rows,'two',resamples=1000))
        self.assertEqual(a['families'],20)
        with self.assertRaisesRegex(ValueError,'duplicate'): paired(rows+rows[:1],'two')
        rows[0]['split']='development'
        with self.assertRaisesRegex(ValueError,'separate'): paired(rows,'two')


if __name__=='__main__': unittest.main()
