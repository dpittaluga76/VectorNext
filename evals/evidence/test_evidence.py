import copy
import unittest
from .score import catalog, covered, score_case


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fact={'supports':[{'document_id':'a','source_sha256':'hash','quote':'exact value 42'}]}
        self.key={'document_id':'a','revision':'rev','chunk_id':'chunk'}
        self.chunks={('a','rev','chunk'):{'source_sha256':'hash','evidence':'The exact value\n42 is specified.'}}

    def test_literal_whitespace_and_alternative_support(self):
        self.assertTrue(covered(self.fact,[self.key],self.chunks))
        fact=copy.deepcopy(self.fact)
        fact['supports'].insert(0,{'document_id':'b','source_sha256':'other','quote':'unavailable'})
        self.assertTrue(covered(fact,[self.key],self.chunks))

    def test_source_revision_and_original_evidence_only(self):
        self.chunks[('a','rev','chunk')]['source_sha256']='wrong'
        self.assertFalse(covered(self.fact,[self.key],self.chunks))
        self.chunks[('a','rev','chunk')]={'source_sha256':'hash','evidence':'42','generated_context':'exact value 42'}
        self.assertFalse(covered(self.fact,[self.key],self.chunks))
        with self.assertRaises(ValueError):covered(self.fact,[dict(self.key,revision='other')],self.chunks)

    def test_failure_and_missing_response_keep_denominator(self):
        case={'id':'S','group':'single','facts':['f']}
        for response in [None,{'status':'error','primary':[self.key]}]:
            result=score_case(case,response,{'f':self.fact},self.chunks)
            self.assertTrue(result['error'])
            self.assertEqual(result['primary']['recall'],0)
            self.assertFalse(result['primary']['complete'])

    def test_missing_evidence_is_not_successful_abstention(self):
        result=score_case({'id':'N','group':'missing','facts':[]},{'status':'ok','primary':[self.key]}, {},self.chunks)
        self.assertIsNone(result['primary']['recall'])
        self.assertIsNone(result['primary']['complete'])
        self.assertEqual(result['primary']['hits'],1)

    def test_partial_fact_coverage_and_catalog(self):
        docs=[{'document_id':'a','revision':'rev','original':{'sha256':'hash'},'chunks':[{'id':'chunk','evidence':'exact value 42'}]}]
        chunks=catalog(docs)
        result=score_case({'id':'M','group':'multi','facts':['f','g']}, {'status':'ok','primary':[self.key]},
            {'f':self.fact,'g':{'supports':[{'document_id':'a','source_sha256':'hash','quote':'missing quote'}]}},chunks)
        self.assertEqual(result['primary']['recall'],.5)
        self.assertFalse(result['primary']['complete'])


if __name__ == '__main__':unittest.main()
