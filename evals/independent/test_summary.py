"""Protect paired comparison denominators and citation-vs-format distinctions."""
import unittest
from .summarize import cited_outcome, complete_context, exact_outcome, paired, planned_rows


def row(id,correct=True,context=True,cited=True,seconds=10):
    return {'case':id,'http_status':200,'wall_seconds':seconds,'score':{
        'answer_correct':correct,'expected_status':'supported','template_correct':None,
        'proofs':{'field':{'gold_source_overlap':cited}},'stages':{'context':{'complete':context}}}}


class SummaryTests(unittest.TestCase):
    def test_missing_cases_remain_in_denominator(self):
        rows=planned_rows({'a':{},'b':{}},[row('a')])
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(map(exact_outcome,rows)),1)
        self.assertIsNone(rows[1]['wall_seconds'])

    def test_duplicate_capture_rejected(self):
        with self.assertRaises(ValueError):planned_rows({'a':{}},[row('a'),row('a')])

    def test_exact_answer_is_not_automatically_cited(self):
        r=row('a',cited=False)
        self.assertTrue(exact_outcome(r));self.assertFalse(cited_outcome(r))

    def test_failed_source_is_not_counted_correct(self):
        r=row('a');r['unavailable_source_documents']=['lost.pdf']
        self.assertFalse(exact_outcome(r));self.assertFalse(complete_context(r))

    def test_incorrect_template_is_failure(self):
        r=row('a');r['score']['template_correct']=False
        self.assertFalse(exact_outcome(r))

    def test_fast_abstention_is_not_matched_success(self):
        five={'cases':[row('a'),row('b')]}
        two={'cases':[row('a',seconds=8),row('b',correct=False,context=False,cited=False,seconds=1)]}
        p=paired(five,two)
        self.assertEqual(p['five_only_exact'],['b']);self.assertEqual(p['two_lost_context'],['b'])
        self.assertEqual(p['matched_supported_cited_cases'],['a'])
        self.assertEqual(p['all_two_seconds']['median'],4.5)
        self.assertEqual(p['matched_supported_cited_two_seconds']['median'],8)


if __name__=='__main__':unittest.main()
