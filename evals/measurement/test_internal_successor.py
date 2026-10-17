from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from .build_typed_candidate import base_role
from .families import PRIMARY, digest
from .internal_successor import assemble_split, safe_file


def fixture():
    raw = b'The sample count is 23.'
    role = base_role('answer', '23')
    role['proof_sets'] = [[{'document_sha256': digest(raw), 'utf8_start': 0, 'utf8_end': len(raw)}]]
    case = dict(case_id='example', number=1, document='sample.txt', format='txt',
        question='What is the sample count?', document_sha256=digest(raw), source_text_sha256=digest(raw),
        tier=PRIMARY, pending_decisions=[], expected='supported', original_expected='supported',
        original_alternatives=['23'], roles=[role], allowed_field_mappings=[{'answer':'answer'}])
    request = {k:case[k] for k in ('case_id','document','format','question')}
    request.update(split='development', history=[], prose=False)
    family = {**case, 'family_key':'synthetic:one'}
    return dict(name='development', requests=[request], gold={'cases':[case]}, families=[family],
        sources={'sample.txt':raw}, source_texts={'example':raw.decode()},
        annotations={}, proofs=[], excluded=set())


class InternalSuccessorTests(unittest.TestCase):
    def test_question_and_control_payloads_have_no_gold_fields(self):
        args=fixture(); files,counts=assemble_split(**args)
        self.assertEqual(counts['primary'],1)
        controls=json.loads(files['development/controls.json'])
        self.assertEqual(controls,[{'case_id':'example','question':'What is the sample count?'}])
        questions=json.loads(files['development/questions.json'])
        self.assertNotIn('23',json.dumps(questions))
        self.assertNotIn('roles',questions[0])
        self.assertEqual(files['development/v1/documents/sample.txt'],args['sources']['sample.txt'])
        self.assertEqual(files['development/v2/documents/sample.txt'],args['sources']['sample.txt'])

    def test_exclusions_remove_whole_cases_without_editing_gold(self):
        args=fixture(); before=deepcopy(args['gold']);args['excluded']={'example'}
        files,counts=assemble_split(**args)
        self.assertEqual(counts['cases'],0);self.assertEqual(counts['documents'],0)
        self.assertEqual(args['gold'],before)
        self.assertEqual(json.loads(files['development/exclusions.json']),['example'])
        self.assertFalse(json.loads(files['development/gold.json'])['approved_for_execution'])

    def test_derived_case_preserved_but_not_in_control_primary(self):
        args=fixture()
        for row in [args['gold']['cases'][0],args['families'][0]]:row['tier']='derived_inference'
        files,counts=assemble_split(**args)
        self.assertEqual(counts['cases'],1);self.assertEqual(counts['primary'],0)
        self.assertEqual(json.loads(files['development/controls.json']),[])

    def test_exposed_split_requires_original_candidate_membership(self):
        args=fixture();args['name']='exposed_candidates'
        with self.assertRaises(ValueError):assemble_split(**args)
        args['requests'][0]['split']='sealed'
        files,_=assemble_split(**args)
        self.assertIn('exposed_candidates/gold.json',files)
        self.assertFalse(any(k.startswith('sealed/') for k in files))

    def test_source_question_roster_pending_and_history_mutations_rejected(self):
        mutations=[lambda a:a['sources'].update({'sample.txt':b'changed'}),
            lambda a:a['requests'][0].update(question='other'),
            lambda a:a['gold']['cases'][0].update(pending_decisions=['unknown']),
            lambda a:a['source_texts'].update(example='modified review text'),
            lambda a:a['requests'][0].update(history=[{'role':'assistant','text':'23'}]),
            lambda a:a['requests'].append(deepcopy(a['requests'][0])),
            lambda a:a.update(excluded={'not-a-case'})]
        for mutate in mutations:
            args=fixture();mutate(args)
            with self.assertRaises(ValueError):assemble_split(**args)

    def test_reviewed_table_context_and_proofs_are_required_and_cells_preserved(self):
        # Retained public development fixture; never opens the private candidates.
        from .build_table_candidate import load_inputs
        annotations,sources,gold,_=load_inputs()
        case=deepcopy(next(c for c in gold['cases'] if c['number']==2))
        request={k:case[k] for k in ('case_id','document','format','question')}
        request.update(split='development',history=[],prose=False)
        args=dict(name='development', requests=[request], gold={'cases':[case]},
            families=[{**case,'family_key':'synthetic:table'}], sources=sources,
            source_texts={case['case_id']:sources[case['document']].decode('utf8')},
            annotations=annotations, proofs=[], excluded=set())
        with self.assertRaises(ValueError):assemble_split(**args)
        args['proofs']=[{'case_id':case['case_id'],'proof_sets':[]}]
        files,_=assemble_split(**args)
        before=json.loads(files['development/v1/documents/'+case['document']])
        after=json.loads(files['development/v2/documents/'+case['document']])
        self.assertNotEqual(before,after)
        for a,b in zip(before['records'],after['records']):
            if 'cells' in a:self.assertEqual(a['cells'],b['cells'])
            else:self.assertEqual(a,b)

    def test_paths_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('../escape',str(root.parent/'absolute')):
                with self.assertRaises(ValueError):safe_file(root,name)
            self.assertEqual(safe_file(root,'development/doc.txt'),root/'development/doc.txt')


if __name__=='__main__':unittest.main()
