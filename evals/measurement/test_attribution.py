import unittest
from .attribution import attribute


class AttributionTests(unittest.TestCase):
    def test_correct_value_is_not_automatically_false_reject(self):
        row={'case_id':'test','validator':'rejected','candidate_correct':True}
        self.assertEqual(attribute(row)['flags'],['gold_matching_rejection_unadjudicated'])
        row['proof_review']='invalid_under_contract'
        self.assertEqual(attribute(row)['flags'],['correct_value_invalid_proof'])
        row['proof_review']='valid_under_contract'
        self.assertEqual(attribute(row)['flags'],['validator_false_reject'])

    def test_multiple_causes_and_oracle_recovery_are_not_unique_causality(self):
        result=attribute({'case_id':'test','plan_correct':False,'candidate_support':True,
            'selected_support':False,'baseline_correct':False,'oracle_evidence_correct':True})
        self.assertEqual(result['flags'],['planning_failure','selection_lost_evidence','recovered_with_oracle_evidence'])
        self.assertFalse(result['unique_root_cause_claimed'])
        self.assertIn('assessment',result['unobserved'])

    def test_semantic_wrong_is_separate_from_mechanical_bug(self):
        result=attribute({'case_id':'test','validator':'accepted','candidate_correct':False,
                          'proof_review':'valid_under_contract'})
        self.assertEqual(result['flags'],['wrong_answer_accepted','semantic_error_despite_mechanical_support'])
