"""Dataset and experiment integrity; no inference, downloads or label regeneration."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from evals.validate import validate_dataset
from .freeze import HERE, digest, public_inputs, verify
from .run import evidence_ids, options


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((HERE/'dataset.json').read_text(encoding='utf-8'))
        self.requests=json.loads((HERE/'requests.json').read_text(encoding='utf-8'))

    def test_sources_labels_and_locations(self):
        self.assertEqual(validate_dataset(HERE/'dataset.json',HERE/'dataset.schema.json'),
            {'documents':20,'evidence':47,'questions':28,'ocr_regions_requiring_visual_review':0})

    def test_public_requests_match_original_questions(self):
        self.assertEqual(len(public_inputs(self.data,self.requests)),28)

    def test_reject_gold_in_public_request(self):
        self.requests['voyager_timeline']['expected']={'launch_year':1977}
        with self.assertRaisesRegex(ValueError,'private'): public_inputs(self.data,self.requests)

    def test_reject_field_answers_in_public_request(self):
        self.requests['voyager_timeline']['fields']['launch_year']['value']=1977
        with self.assertRaisesRegex(ValueError,'value or source'): public_inputs(self.data,self.requests)

    def test_reject_holdout(self):
        self.data['cases'][0]['split']='holdout'
        with self.assertRaisesRegex(ValueError,'comparison'): public_inputs(self.data,self.requests)

    def test_reject_changed_question(self):
        self.requests['voyager_timeline']['question']='Answer 1977'
        with self.assertRaisesRegex(ValueError,'question mismatch'): public_inputs(self.data,self.requests)

    def test_reject_changed_history(self):
        self.requests['voyager_followup']['history'][0]['text']='The answer is 1986'
        with self.assertRaisesRegex(ValueError,'history mismatch'): public_inputs(self.data,self.requests)

    def test_reject_incomplete_case_list(self):
        del self.requests['voyager_timeline']
        with self.assertRaisesRegex(ValueError,'identical'): public_inputs(self.data,self.requests)

    def test_frozen_byte_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'source';p.write_bytes(b'original')
            manifest={'files':{'source':digest(p)}}
            verify(root,manifest);p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'frozen input changed'): verify(root,manifest)

    def test_only_experimental_variable_is_primary_limit(self):
        a,b=options(2),options(5)
        self.assertEqual({k for k in a if a[k]!=b[k]},{'primary_limit'})
        with self.assertRaises(ValueError): options(1)

    def test_multidocument_questions_require_three_or_more_sources(self):
        refs={e['id']:e['document_id'] for e in self.data['evidence']}
        cases=[c for c in self.data['cases'] if 'multi_document' in c['tags']]
        self.assertEqual(len(cases),4)
        for c in cases:
            self.assertGreaterEqual(len({refs[e] for e in evidence_ids(c)}),3)

    def test_original_json_null_zero_and_numeric_types(self):
        refs={e['id']:e['expected'] for e in self.data['evidence']}
        self.assertIsNone(refs['tohoku_timezone']);self.assertIsNone(refs['tohoku_dmin'])
        self.assertEqual(refs['tohoku_tsunami'],0)
        self.assertIs(type(refs['tohoku_json_depth']),int)
        self.assertIs(type(refs['maule_json_depth']),float)


if __name__=='__main__': unittest.main()
