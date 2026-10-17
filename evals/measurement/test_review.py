import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from .review import checked_file,verify


class ReviewTests(unittest.TestCase):
    def package(self,root):
        cases=[]
        for i in range(180):
            split='sealed' if i>=120 else 'development'
            r={'case_id':str(i),'family':str(i),'split':split,'format':['txt','pdf','json'][i%3],
               'structure':'table' if i%3==2 else 'prose','capability':'direct_extraction',
               'accepted':True,'expected':'insufficient_evidence' if i%4==0 else 'supported',
               'exact_values_reviewed':True,'support_reviewed':True,'scope_reviewed':True,'pdf_visually_reviewed':True,
               'gold_fields':{'answer':{'kind':'string'}},'answer_variants':[{'answer':{'kind':'string','value_text':'test'}}],
               'support_sets':[['synthetic-independent-fixture-only']]}
            cases.append(r)
        files={}
        for split in ('development','sealed'):
            (root/split).mkdir()
            raw=json.dumps([r for r in cases if r['split']==split]).encode()
            (root/split/'requests.json').write_bytes(raw)
            files[split+'/requests.json']=hashlib.sha256(raw).hexdigest()
        raw=json.dumps({'files':files}).encode();(root/'manifest.json').write_bytes(raw)
        review={'approved':True,'independent_of_implementation':True,'reviewer':'unit fixture',
                'custodian':'unit fixture','date':'unit fixture','custody_transferred':True,
                'package_manifest_sha256':hashlib.sha256(raw).hexdigest(),'cases':cases}
        (root/'review.json').write_text(json.dumps(review),encoding='utf-8')
        return review

    def test_review_is_required_and_bound_to_unchanged_package(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);review=self.package(root)
            self.assertEqual(verify(root,root/'review.json')['questions'],180)
            review['approved']=False
            (root/'review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'pending'): verify(root,root/'review.json')
            review['approved']=True
            (root/'review.json').write_text(json.dumps(review),encoding='utf-8')
            (root/'development/requests.json').write_text('[]',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'changed'): verify(root,root/'review.json')

    def test_missing_adjudication_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);review=self.package(root)
            review['cases'][0]['gold_fields']=None
            (root/'review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'field definitions'): verify(root,root/'review.json')
            for path in ('../secret','C:/secret','/secret','a\\b'):
                with self.assertRaises(ValueError): checked_file(root,path)

    def test_counts_cannot_be_met_by_invented_or_omitted_case_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);review=self.package(root)
            review['cases'][0]['case_id']='invented'
            (root/'review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'every public case'): verify(root,root/'review.json')
