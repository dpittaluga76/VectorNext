from copy import deepcopy
import json
import unittest

from .capture_grounding import aligned_span, cell_coordinate, prose_coordinates, table_coordinates
from .families import digest


def prose(text='The sample count is 23.'):
    document={'document_id':'d','revision':'r','blocks':[{'id':'b','text':text}]}
    evidence={'key':{'document_id':'d','revision':'r','chunk_id':'c'},'record':None,
        'text':text, 'sources':[{'revision':'r','locator':{'Pdf':{'page':1}}}],
        'spans':[{'block_id':'b','bytes':{'start':0,'end':len(text.encode())}}]}
    return document,evidence


class CaptureGroundingTests(unittest.TestCase):
    def test_whitespace_alignment_preserves_utf8_source_offsets(self):
        source='  Caf\u00e9\n count:  23. '
        bounds,gap=aligned_span(source,'Caf\u00e9 count: 23.')
        self.assertIsNone(gap)
        self.assertEqual(source.encode()[bounds[0]:bounds[1]].decode(),'Caf\u00e9\n count:  23.')

    def test_numbers_signs_and_symbols_are_not_normalized_into_matches(self):
        for source,visible in [('$12','$12$'),('22,880','22880'),('almost 2,000','2,000 exact'),
                               ('-23','\u221223'),('0.3','30%')]:
            with self.subTest(source=source):self.assertIsNone(aligned_span(source,visible)[0])

    def test_repeated_passages_stay_unresolved(self):
        self.assertEqual(aligned_span('Count 23. Count 23.','Count 23.'),
                         (None,'ambiguous_source_alignment'))

    def test_prose_proofs_come_from_visible_frozen_block(self):
        document,evidence=prose();text=document['blocks'][0]['text']
        result=prose_coordinates(text,digest(text.encode()),'a'*64,evidence,document,'d','r')
        self.assertEqual(result['proofs'],[{'document_sha256':'a'*64,'utf8_start':0,'utf8_end':len(text)}])
        self.assertEqual(result['alignment_gaps'],[])

    def test_stale_truncated_unseen_or_unknown_block_is_refused(self):
        for mutation in [lambda e:e['key'].update(revision='other'),
                         lambda e:e.update(text_truncated=True),lambda e:e.update(text='hidden'),
                         lambda e:e['spans'][0].update(block_id='not-captured')]:
            document,evidence=prose();text=document['blocks'][0]['text'];mutation(evidence)
            with self.assertRaises(ValueError):
                prose_coordinates(text,digest(text.encode()),'a'*64,evidence,document,'d','r')

    def test_clean_pdf_wrap_matches_but_unmapped_text_is_an_explicit_gap(self):
        source='The sample count is 23.';document,evidence=prose('The sample\ncount is 23.')
        result=prose_coordinates(source,digest(source.encode()),'a'*64,evidence,document,'d','r')
        self.assertTrue(result['proofs'])
        result=prose_coordinates('Another text.',digest(b'Another text.'),'a'*64,evidence,document,'d','r')
        self.assertEqual(result['proofs'],[])
        self.assertEqual(result['alignment_gaps'][0]['reason'],'source_alignment_missing')

    def test_table_coordinates_require_full_captured_representation(self):
        from .build_table_candidate import load_inputs
        from .table_adapter import adapt
        annotations,sources,_,_=load_inputs()
        name=next(iter(sources));source=sources[name];annotation=annotations[name]
        adapted,_=adapt(source,annotation)
        row=next(int(r) for r,k in annotation['row_kinds'].items() if k=='data')
        record=adapted['records'][row]
        evidence={'key':{'document_id':'d','revision':'r'},'record':record,
            'text':json.dumps(record), 'sources':[{'revision':'r','locator':{'Json':{'pointer':f'/records/{row}'}}}]}
        result=table_coordinates(source,annotation,'v2',evidence,'d','r')
        value=cell_coordinate(source,annotation,row,'/cells/1')
        self.assertIn(value,result['visible_coordinates'])
        bad=deepcopy(evidence);bad['text']='{}'
        with self.assertRaises(ValueError):table_coordinates(source,annotation,'v2',bad,'d','r')
        with self.assertRaises(ValueError):cell_coordinate(source,annotation,row,'/structural_context/1')

    def test_table_sidecar_is_not_credited_to_original_representation(self):
        from .build_table_candidate import load_inputs
        from .table_adapter import adapt
        annotations,sources,_,_=load_inputs()
        name=next(iter(sources));source=sources[name];annotation=annotations[name]
        adapted,_=adapt(source,annotation)
        row=next(int(r) for r,k in annotation['row_kinds'].items() if k=='data')
        record=adapted['records'][row]
        evidence={'key':{'document_id':'d','revision':'r'},'record':record,'text':json.dumps(record),
                  'sources':[{'revision':'r','locator':{'Json':{'pointer':f'/records/{row}'}}}]}
        with self.assertRaises(ValueError):table_coordinates(source,annotation,'v1',evidence,'d','r')


if __name__=='__main__':unittest.main()
