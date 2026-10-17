from copy import deepcopy
import json
import unittest

from .capture_projection import exact_json, project
from .families import digest, encoded


def fixture():
    text='The sample count is 23.'
    evidence={'id':'E1','key':{'document_id':'d','revision':'r','chunk_id':'c'},'record':None,
        'text':text,'sources':[{'revision':'r','locator':{'Text':{}}}],
        'spans':[{'block_id':'b','bytes':{'start':0,'end':len(text)}}]}
    fields={'answer':{'value':'23','evidence_id':'E1','quote':'23','pointer':None}}
    report={'request':{'question':'How many?'},'answer':{'status':'supported','fields':fields},'evidence':[evidence]}
    view={'outcome':'supported','fields':[{'name':'answer','kind':'string','value_text':'23',
        'evidence_id':'E1','quote':'23','pointer':None}], 'raw_report':json.dumps(report)}
    job={'terminal':True,'mode':'nuextract','state':'completed','result':view}
    context={'binding':{'state':'committed','document_id':'d','revision':'r'},
        'descriptor':{'format':'txt','original_sha256':digest(text.encode()),
            'review_text_sha256':digest(text.encode()),'representations':{'v2':{'sha256':digest(text.encode())}}},
        'snapshot':{'document_id':'d','revision':'r','original':{'sha256':digest(text.encode())},
                    'chunks':[{'id':'c'}],'blocks':[{'id':'b','text':text}]},
        'original':text.encode(),'text':text,'representation':'v2'}
    return job,context


class CaptureProjectionTests(unittest.TestCase):
    def test_supported_value_and_verified_location_reach_scorer(self):
        job,context=fixture();capture=project(encoded(job),'How many?',context)
        self.assertEqual(capture['status'],'supported')
        self.assertEqual(capture['fields'][0]['value_text'],'23')
        self.assertEqual(capture['fields'][0]['proofs'][0]['utf8_end'],len(context['text']))

    def test_rejected_draft_never_becomes_final_fields(self):
        job,context=fixture()
        job['result']={'outcome':'rejected','fields':[],
            'raw_report':json.dumps({'unvalidated_draft':{'fields':{'answer':{'value':'23'}}}})}
        capture=project(encoded(job),'How many?',context)
        self.assertEqual(capture['status'],'rejected');self.assertEqual(capture['fields'],[])

    def test_model_or_source_revision_change_refused(self):
        for mutation in [lambda j,c:j.update(mode='gemma'),lambda j,c:j.update(terminal=False),
                         lambda j,c:c['binding'].update(revision='other'),
                         lambda j,c:c['snapshot']['original'].update(sha256='other'),
                         lambda j,c:c.update(text='changed')]:
            job,context=fixture();mutation(job,context)
            with self.assertRaises(ValueError):project(encoded(job),'How many?',context)

    def test_application_errors_are_failures_not_negative_successes(self):
        job,context=fixture();job.update(status_code=400,result={'code':'invalid','message':'plan rejected'})
        capture=project(encoded(job),'How many?',context)
        self.assertEqual(capture['status'],'error')
        self.assertEqual(capture['failure_stage'],'planning_or_application')

    def test_wrong_question_or_rounded_view_rejected(self):
        job,context=fixture()
        with self.assertRaises(ValueError):project(encoded(job),'Other question',context)
        job['result']['fields'][0]['value_text']='24'
        with self.assertRaises(ValueError):project(encoded(job),'How many?',context)

    def test_exact_parser_retains_large_integer_decimal_and_refuses_duplicates(self):
        value=exact_json(b'{"integer":9007199254740993,"decimal":1234567890.123456789012345}')
        self.assertEqual(value['integer'],9007199254740993)
        self.assertEqual(str(value['decimal']),'1234567890.123456789012345')
        for bad in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):exact_json(bad)

    def test_equal_table_value_wrong_cell_stays_a_grounding_failure(self):
        from .build_table_candidate import build, load_inputs
        from .table_grounding import score_case
        annotations,sources,gold,_=load_inputs()
        adapted,_,proofs,_=build()
        case=next(c for c in gold['cases'] if c['number']==2)
        proof=next(c for c in proofs['cases'] if c['number']==2)
        name=case['document'];annotation=annotations[name];source=sources[name]
        locations={(p['value']['row'],p['value']['col']) for p in proof['proof_sets']}
        value=case['roles'][0]['value_string']
        other=next((int(r),col) for r,kind in annotation['row_kinds'].items() if kind=='data'
                   for col,cell in enumerate(json.loads(source)['records'][int(r)]['cells'])
                   if cell==value and (int(r),col) not in locations)
        def capture_cell(row,col):
            job,context=fixture();record=adapted[name]['records'][row]
            pointer=f'/cells/{col}'
            report={'request':{'question':case['question']},
                'answer':{'status':'supported','fields':{'answer':{'value':value,'evidence_id':'E1',
                    'quote':value,'pointer':pointer}}},
                'evidence':[{'id':'E1','key':{'document_id':'d','revision':'r','chunk_id':'c'},
                    'record':record,'text':json.dumps(record),
                    'sources':[{'revision':'r','locator':{'Json':{'pointer':f'/records/{row}'}}}]}]}
            job['result'].update(raw_report=json.dumps(report),fields=[{'name':'answer','kind':'string',
                'value_text':value,'evidence_id':'E1','quote':value,'pointer':pointer}])
            context.update(original=source,text=source.decode(),annotation=annotation)
            context['descriptor'].update(format='json',original_sha256=digest(source),
                review_text_sha256=digest(source),representations={'v2':{'sha256':digest(encoded(adapted[name]))}})
            context['snapshot']['original']['sha256']=digest(encoded(adapted[name]))
            return project(encoded(job),case['question'],context)
        right=score_case(case,capture_cell(*next(iter(locations))),proof)
        wrong=score_case(case,capture_cell(*other),proof)
        self.assertTrue(right['correct']);self.assertTrue(right['evidence_correct'])
        self.assertTrue(wrong['correct']);self.assertFalse(wrong['evidence_correct'])
        self.assertTrue(wrong['correct_answer_wrong_evidence'])


if __name__=='__main__':unittest.main()
